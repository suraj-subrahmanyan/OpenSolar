#!/usr/bin/env python3
"""run_process_registry.py — Lane 0.5: run-scoped process registry (R7, design §1.9).

Every daemon started for a run registers (pid, role, run_id) here; teardown
kills by registry — watchdog-first — and verifies exit; a run-terminal marker
suppresses any respawn past teardown (AC-R7.4, fixes the F-043 class).

Storage (append-only JSONL, one file per run, crash-survivable):
    $HARNESS_DIR/run/process-registry/<run_id>.jsonl   — register/terminal/teardown events
    $HARNESS_DIR/run/process-registry/<run_id>.terminal — plain marker file so bash call
        sites can gate respawn with:  [[ -f "$HARNESS_DIR/run/process-registry/$rid.terminal" ]]

Python API:
    register(run_id, role, pid, meta=None)   -> record   (raises TerminalRunError post-terminal)
    mark_terminal(run_id, reason="")         -> marker path (idempotent)
    is_terminal(run_id)                      -> bool
    live_entries(run_id)                     -> registered entries whose process is still alive
    teardown(run_id, grace_s, kill_grace_s)  -> result dict; marks terminal FIRST, then kills
                                                watchdog-first with TERM→KILL escalation and
                                                re-reads the registry between rounds so children
                                                respawned mid-teardown are still reaped
    read_records(run_id)                     -> all events (torn trailing lines are skipped)

CLI (for bash call sites; exit codes: 0 ok, 1 failure/survivors, 2 usage, 3 terminal-refused):
    python3 run_process_registry.py register      --run-id RID --role ROLE --pid PID [--meta JSON]
    python3 run_process_registry.py mark-terminal --run-id RID [--reason WHY]
    python3 run_process_registry.py is-terminal   --run-id RID          # exit 0 iff terminal
    python3 run_process_registry.py teardown      --run-id RID [--grace S] [--kill-grace S]
    python3 run_process_registry.py status        --run-id RID          # JSON: records + live

Intended call sites (documented here per the Lane 0.5 plan; the hooks themselves
land via the Lane 0 serialized-files stub PR — this module must NOT be wired by
editing those files from this lane):
  * harness/solar-harness.sh — register the status-server / coordinator / watchdog
    pids at their spawn sites; call `teardown` from the stop path
    (stop_harness_background_processes) and expose `preflight-run`/`run-teardown`
    style subcommands as thin stubs.
  * harness/coordinator-watchdog.sh — before any respawn (do_check coordinator
    restart, check_panes pane respawn, ensure_tmux_sessions rebuild): check
    `is-terminal --run-id <active sid>` and skip respawn when terminal; register
    respawned coordinator pids. The watchdog daemon registers itself with role
    "watchdog" at run-daemon startup.
  * scripts/live-codex-e2e-isolated.sh — cleanup() calls `teardown --run-id <sid>`
    before its tmux kill-session lines, making zero-survivor teardown provable.
  * runtime-validation-ladder cleanup gates (P1.6 and every later rung) — call
    `status`/`teardown` to enforce the zero-surviving-processes gate (AC-R7.4).

Kill ordering: roles containing "watchdog" first (nothing may respawn what we
are about to kill), then "coordinator", then everything else newest-first.
A recorded cmdline snapshot guards against PID reuse: a pid whose current
cmdline no longer matches its registered cmdline is skipped, never signalled.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_POLL_INTERVAL_S = 0.05


class TerminalRunError(RuntimeError):
    """Raised when registering into a run that is already marked terminal."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _harness_dir(harness_dir: Optional[Path | str] = None) -> Path:
    if harness_dir:
        return Path(harness_dir)
    raw = os.environ.get("HARNESS_DIR") or os.environ.get("SOLAR_HARNESS_DIR")
    return Path(raw) if raw else Path.home() / ".solar" / "harness"


def _validate_run_id(run_id: str) -> str:
    value = str(run_id or "").strip()
    if not _RUN_ID_RE.fullmatch(value):
        raise ValueError(f"invalid run_id (path-safe [A-Za-z0-9._-] required): {run_id!r}")
    return value


def registry_dir(harness_dir: Optional[Path | str] = None) -> Path:
    return _harness_dir(harness_dir) / "run" / "process-registry"


def registry_path(run_id: str, harness_dir: Optional[Path | str] = None) -> Path:
    return registry_dir(harness_dir) / f"{_validate_run_id(run_id)}.jsonl"


def terminal_marker_path(run_id: str, harness_dir: Optional[Path | str] = None) -> Path:
    return registry_dir(harness_dir) / f"{_validate_run_id(run_id)}.terminal"


# --- process probes (injectable seams; monkeypatched by the P1.5 tests) --------


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _is_zombie(pid: int) -> bool:
    """A killed-but-unreaped child still answers kill(pid, 0); it is not a
    survivor (found at the P1.6 real-process tier: wrapper-registered children
    are zombies until their parent reaps them)."""
    try:
        stat_text = (Path("/proc") / str(pid) / "stat").read_text(encoding="ascii", errors="replace")
        return stat_text.rsplit(")", 1)[1].split()[0] == "Z"
    except (OSError, IndexError):
        pass
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "state="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.returncode == 0 and out.stdout.strip().upper().startswith("Z")
    except Exception:
        return False


def _running(pid: int) -> bool:
    """Alive in the registry's sense: exists and is not a zombie."""
    return _pid_exists(pid) and not _is_zombie(pid)


def _read_cmdline(pid: int) -> str:
    """Best-effort process identity snapshot; '' when unknown."""
    proc = Path("/proc") / str(pid) / "cmdline"
    try:
        raw = proc.read_bytes()
        if raw:
            return raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    except OSError:
        pass
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def _send_signal(pid: int, sig: int) -> None:
    os.kill(pid, sig)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


# --- storage -------------------------------------------------------------------


def _append(run_id: str, record: Dict[str, Any], harness_dir: Optional[Path | str] = None) -> None:
    path = registry_path(run_id, harness_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    # a crash mid-append can leave a torn line without a newline; never let the
    # next append concatenate onto it
    needs_newline = False
    try:
        with open(path, "rb") as existing:
            existing.seek(-1, os.SEEK_END)
            needs_newline = existing.read(1) != b"\n"
    except (OSError, ValueError):
        pass
    with open(path, "a", encoding="utf-8") as f:
        if needs_newline:
            f.write("\n")
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_records(run_id: str, harness_dir: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """All events for the run. Torn/partial trailing lines (crash mid-append)
    are skipped so a crash never poisons teardown."""
    path = registry_path(run_id, harness_dir)
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


# --- API -----------------------------------------------------------------------


def is_terminal(run_id: str, harness_dir: Optional[Path | str] = None) -> bool:
    return terminal_marker_path(run_id, harness_dir).exists()


def mark_terminal(
    run_id: str, reason: str = "", harness_dir: Optional[Path | str] = None
) -> Path:
    """Idempotent. Creates the shell-checkable marker, then records the event."""
    marker = terminal_marker_path(run_id, harness_dir)
    already = marker.exists()
    marker.parent.mkdir(parents=True, exist_ok=True)
    if not already:
        tmp = marker.with_suffix(".terminal.tmp")
        tmp.write_text(
            json.dumps({"run_id": run_id, "reason": reason, "marked_at": _now()}) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, marker)
        _append(
            run_id,
            {"event": "terminal", "run_id": run_id, "reason": reason, "marked_at": _now()},
            harness_dir,
        )
    return marker


def clear_terminal(
    run_id: str, reason: str = "new_run_start", harness_dir: Optional[Path | str] = None
) -> bool:
    """Idempotent. A terminal marker denotes the PREVIOUS run's end — a new
    run birth must clear it, or register() refuses the new daemons (start
    call sites swallow that refusal with `|| true`) and the watchdog exits
    on its first tick: an unsupervised harness with unregistered daemons
    after every kill+start cycle (G3 zombie-factory fix amplification,
    found in review prep 2026-07-09). Returns True when a marker was
    removed."""
    marker = terminal_marker_path(run_id, harness_dir)
    if not marker.exists():
        return False
    marker.unlink()
    _append(
        run_id,
        {"event": "terminal_cleared", "run_id": run_id, "reason": reason,
         "cleared_at": _now()},
        harness_dir,
    )
    return True


def register(
    run_id: str,
    role: str,
    pid: int,
    meta: Optional[Dict[str, Any]] = None,
    harness_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    run_id = _validate_run_id(run_id)
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        raise ValueError(f"pid must be an integer: {pid!r}")
    if pid <= 1:
        raise ValueError(f"refusing to register pid {pid}")
    if is_terminal(run_id, harness_dir):
        raise TerminalRunError(
            f"run {run_id} is marked terminal; registration refused (respawn past teardown?)"
        )
    record: Dict[str, Any] = {
        "event": "register",
        "run_id": run_id,
        "role": str(role or "").strip() or "unknown",
        "pid": pid,
        "cmdline": _read_cmdline(pid),
        "registered_at": _now(),
    }
    if meta:
        record["meta"] = meta
    _append(run_id, record, harness_dir)
    return record


def _registered_entries(
    run_id: str, harness_dir: Optional[Path | str] = None
) -> List[Dict[str, Any]]:
    """Register events deduplicated by pid (last registration wins), in order."""
    seen: Dict[int, Dict[str, Any]] = {}
    order: List[int] = []
    for index, record in enumerate(read_records(run_id, harness_dir)):
        if record.get("event") != "register":
            continue
        try:
            pid = int(record.get("pid"))
        except (TypeError, ValueError):
            continue
        if pid not in seen:
            order.append(pid)
        entry = dict(record)
        entry["_index"] = index
        seen[pid] = entry
    return [seen[pid] for pid in order]


def _identity_matches(entry: Dict[str, Any]) -> bool:
    recorded = str(entry.get("cmdline") or "")
    if not recorded:
        return True  # no snapshot -> cannot distinguish; treat as matching
    current = _read_cmdline(int(entry["pid"]))
    if not current:
        return True
    return current == recorded


def live_entries(run_id: str, harness_dir: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    live: List[Dict[str, Any]] = []
    for entry in _registered_entries(run_id, harness_dir):
        pid = int(entry["pid"])
        if not _running(pid):
            continue
        if not _identity_matches(entry):
            continue
        live.append({k: v for k, v in entry.items() if not k.startswith("_")})
    return live


def _role_rank(role: str) -> int:
    value = str(role or "").lower()
    if "watchdog" in value:
        return 0
    if "coordinator" in value:
        return 1
    return 2


def _wait_gone(pids: List[int], timeout_s: float) -> List[int]:
    """Poll until every pid is gone or the budget expires; returns survivors."""
    iterations = max(1, int(timeout_s / _POLL_INTERVAL_S))
    remaining = list(pids)
    for _ in range(iterations):
        remaining = [pid for pid in remaining if _running(pid)]
        if not remaining:
            break
        _sleep(_POLL_INTERVAL_S)
    return remaining


def teardown(
    run_id: str,
    grace_s: float = 5.0,
    kill_grace_s: float = 2.0,
    harness_dir: Optional[Path | str] = None,
    max_rounds: int = 3,
) -> Dict[str, Any]:
    """Kill every registered run-scoped process and verify exit (AC-R7.4).

    Marks the run terminal BEFORE the first signal so nothing can legally
    respawn or re-register during teardown, then kills watchdog-first with
    TERM -> KILL escalation. The registry is re-read between rounds to reap
    processes that were registered while the previous round was in flight.
    Idempotent: a second call finds nothing alive and still records its event.
    """
    run_id = _validate_run_id(run_id)
    mark_terminal(run_id, reason="teardown", harness_dir=harness_dir)

    self_pid = os.getpid()
    handled: set[int] = set()
    killed: List[int] = []
    sigkilled: List[int] = []
    already_gone: List[int] = []
    skipped: List[Dict[str, Any]] = []
    survivors: List[int] = []

    for _round in range(max(1, int(max_rounds))):
        entries = [
            e for e in _registered_entries(run_id, harness_dir) if int(e["pid"]) not in handled
        ]
        if not entries:
            break
        entries.sort(key=lambda e: (_role_rank(str(e.get("role"))), -int(e["_index"])))

        targets: List[Dict[str, Any]] = []
        for entry in entries:
            pid = int(entry["pid"])
            handled.add(pid)
            if pid == self_pid:
                skipped.append({"pid": pid, "why": "self"})
                continue
            if pid <= 1:
                skipped.append({"pid": pid, "why": "bad_pid"})
                continue
            if not _running(pid):
                already_gone.append(pid)
                continue
            if not _identity_matches(entry):
                skipped.append({"pid": pid, "why": "pid_reused"})
                continue
            targets.append(entry)

        if not targets:
            continue

        for entry in targets:
            try:
                _send_signal(int(entry["pid"]), signal.SIGTERM)
            except ProcessLookupError:
                pass
        stubborn = _wait_gone([int(e["pid"]) for e in targets], grace_s)
        for pid in stubborn:
            try:
                _send_signal(pid, signal.SIGKILL)
                sigkilled.append(pid)
            except ProcessLookupError:
                pass
        round_survivors = _wait_gone(stubborn, kill_grace_s)
        survivors.extend(round_survivors)
        killed.extend(
            int(e["pid"]) for e in targets if int(e["pid"]) not in round_survivors
        )

    result: Dict[str, Any] = {
        "event": "teardown",
        "run_id": run_id,
        "ok": not survivors,
        "killed": killed,
        "sigkilled": sigkilled,
        "already_gone": already_gone,
        "skipped": skipped,
        "survivors": survivors,
        "finished_at": _now(),
    }
    _append(run_id, result, harness_dir)
    return result


# --- CLI -------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run-scoped process registry (Lane 0.5, R7)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_register = sub.add_parser("register", help="register a daemon pid for a run")
    p_register.add_argument("--run-id", required=True)
    p_register.add_argument("--role", required=True)
    p_register.add_argument("--pid", required=True, type=int)
    p_register.add_argument("--meta", default=None, help="optional JSON object")

    p_terminal = sub.add_parser("mark-terminal", help="mark the run terminal (idempotent)")
    p_terminal.add_argument("--run-id", required=True)
    p_terminal.add_argument("--reason", default="")

    p_is = sub.add_parser("is-terminal", help="exit 0 iff the run is terminal")
    p_is.add_argument("--run-id", required=True)

    p_clear = sub.add_parser(
        "clear-terminal",
        help="clear the run-terminal marker (a new run birth reopens the lifecycle)",
    )
    p_clear.add_argument("--run-id", required=True)
    p_clear.add_argument("--reason", default="new_run_start")

    p_teardown = sub.add_parser("teardown", help="kill registered processes, watchdog-first")
    p_teardown.add_argument("--run-id", required=True)
    p_teardown.add_argument("--grace", type=float, default=5.0)
    p_teardown.add_argument("--kill-grace", type=float, default=2.0)

    p_status = sub.add_parser("status", help="print registry state as JSON")
    p_status.add_argument("--run-id", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "register":
            meta = json.loads(args.meta) if args.meta else None
            record = register(args.run_id, args.role, args.pid, meta=meta)
            print(json.dumps(record, ensure_ascii=False))
            return 0
        if args.command == "mark-terminal":
            mark_terminal(args.run_id, reason=args.reason)
            return 0
        if args.command == "is-terminal":
            return 0 if is_terminal(args.run_id) else 1
        if args.command == "clear-terminal":
            clear_terminal(args.run_id, reason=args.reason)
            return 0
        if args.command == "teardown":
            result = teardown(args.run_id, grace_s=args.grace, kill_grace_s=args.kill_grace)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["ok"] else 1
        if args.command == "status":
            payload = {
                "run_id": args.run_id,
                "terminal": is_terminal(args.run_id),
                "records": read_records(args.run_id),
                "live": live_entries(args.run_id),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
    except TerminalRunError as exc:
        print(f"terminal-refused: {exc}", file=sys.stderr)
        return 3
    except ValueError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
