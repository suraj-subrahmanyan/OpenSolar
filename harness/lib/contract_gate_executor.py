#!/usr/bin/env python3
"""contract_gate_executor — runs a contracted stage's non-LLM evaluator gate.

The workflow-contract schema admits evaluator_gate kinds none |
deterministic_command | llm_eval. The structure guard enforces them, but until
P3 nothing EXECUTED the first two — `evaluator_gate` was consumed only by the
guard, so any contracted stage without an llm_eval gate wedged in `reviewing`
(found by the P3 rehearsal; both P2 contracts are all-llm_eval, so latent).

Design: this executor is a DETERMINISTIC EVALUATOR. It produces the exact
sidecar pair a live evaluator produces ({sid}.{node}-eval.json + -eval.md,
stamped with the node's current generation), so the proven consume machinery
— sidecar reconcile -> mark_node_result -> ledger eval_verdict -> repair on
FAIL — runs unchanged. No new consumption path, no fabricated provenance:
generation_mode says exactly what produced the verdict.

Verdict mapping:
- exit 0            -> PASS, verdict_kind "content"
- nonzero exit      -> FAIL, verdict_kind "content" (a real content judgment)
- unrunnable/timeout-> FAIL, verdict_kind "infrastructure" (AC-R4.1 already
                       prevents infrastructure FAILs from flipping
                       policy-passed nodes)
- gate kind "none"  -> PASS, generation_mode "evaluator_gate_none" (records
                       that the contract declares no evaluator for the stage;
                       the proof gate still applies at mark time)

Command convention (commands arrive fully substituted from instantiate()):
- `research <args>`   -> [sys.executable, -m, research.cli, <args>]
- `python3 <x.py> ..` -> [sys.executable, <x.py>, ..]
- anything else       -> bash -lc <command>
CWD = HARNESS_DIR (the same anchor the artifact manifest uses, so relative
artifact roots like workspace/... and harness-shipped scripts/ resolve
identically in dev checkouts and installed/sandbox harnesses). Timeout:
SOLAR_CONTRACT_GATE_TIMEOUT_SEC (default 300s).
"""
from __future__ import annotations

import datetime
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

EXECUTABLE_GATE_KINDS = {"none", "deterministic_command"}
_OUTPUT_TAIL_CHARS = 4000


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _harness_dir() -> Path:
    return Path(
        os.environ.get("HARNESS_DIR")
        or os.environ.get("SOLAR_HARNESS_DIR")
        or Path.home() / ".solar" / "harness"
    )


def _timeout_seconds() -> float:
    try:
        return float(os.environ.get("SOLAR_CONTRACT_GATE_TIMEOUT_SEC", "300"))
    except Exception:
        return 300.0


def _gate_argv(command: str) -> list[str] | None:
    """Map a contract gate command string to argv; None means bash -lc."""
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if not argv:
        return None
    head = argv[0]
    if head == "research":
        return [sys.executable, "-m", "research.cli", *argv[1:]]
    if head in {"python3", "python"}:
        return [sys.executable, *argv[1:]]
    return None


def _node_generation(node: Dict[str, Any]) -> int:
    raw = node.get("repair_attempts")
    try:
        return max(0, int(raw or 0))
    except Exception:
        return 0


def execute_gate(
    sprints_dir: Any,
    sid: str,
    node: Dict[str, Any],
    gate: Dict[str, Any],
    *,
    harness_dir: Optional[os.PathLike] = None,
) -> Dict[str, Any]:
    """Execute a none/deterministic_command gate; write the eval sidecar pair.

    Returns {ok, verdict, verdict_kind, eval_json, eval_md, exit_code}.
    Never raises on gate failure — a failing gate is a verdict, not an error.
    """
    node_id = str(node.get("id") or "")
    kind = str(gate.get("kind") or "none")
    generation = _node_generation(node)
    sprints = Path(sprints_dir)
    sprints.mkdir(parents=True, exist_ok=True)
    eval_json_path = sprints / f"{sid}.{node_id}-eval.json"
    eval_md_path = sprints / f"{sid}.{node_id}-eval.md"

    if kind == "none":
        verdict, verdict_kind, exit_code = "PASS", "content", 0
        generation_mode = "evaluator_gate_none"
        command = ""
        summary = (
            "Contract declares no evaluator gate for this stage "
            "(evaluator_gate.kind=none); policy pass recorded. The proof gate "
            "(manifest/proof obligations) still applies at mark time."
        )
        output_tail = ""
        duration = 0.0
    else:
        command = str(gate.get("command") or "").strip()
        generation_mode = "deterministic_command"
        started = datetime.datetime.now(datetime.timezone.utc)
        argv = _gate_argv(command)
        popen_args: Any = argv if argv is not None else ["bash", "-lc", command]
        harness = Path(harness_dir) if harness_dir else _harness_dir()
        env = dict(os.environ)
        lib_dir = str(harness / "lib")
        env["PYTHONPATH"] = os.pathsep.join(
            [lib_dir, env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
        try:
            proc = subprocess.run(
                popen_args,
                cwd=str(harness),
                env=env,
                capture_output=True,
                text=True,
                timeout=_timeout_seconds(),
            )
            exit_code = int(proc.returncode)
            output_tail = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-_OUTPUT_TAIL_CHARS:]
            if exit_code == 0:
                verdict, verdict_kind = "PASS", "content"
                summary = f"Deterministic gate passed: `{command}` exit 0."
            elif exit_code == 2 or _looks_unrunnable(output_tail):
                # argparse usage errors / missing interpreter targets are
                # machinery failures, not content judgments
                verdict, verdict_kind = "FAIL", "infrastructure"
                summary = f"Deterministic gate could not run meaningfully: `{command}` exit {exit_code}."
            else:
                verdict, verdict_kind = "FAIL", "content"
                summary = f"Deterministic gate failed: `{command}` exit {exit_code}."
        except subprocess.TimeoutExpired:
            exit_code = -1
            output_tail = f"timeout after {_timeout_seconds()}s"
            verdict, verdict_kind = "FAIL", "infrastructure"
            summary = f"Deterministic gate timed out: `{command}`."
        except Exception as exc:
            exit_code = -1
            output_tail = f"{type(exc).__name__}: {exc}"
            verdict, verdict_kind = "FAIL", "infrastructure"
            summary = f"Deterministic gate unrunnable: `{command}` ({type(exc).__name__})."
        duration = (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()

    payload = {
        "node_id": node_id,
        "verdict": verdict,
        "verdict_kind": verdict_kind,
        "summary": summary,
        "eval_generation": generation,
        "repair_attempt": generation,
        "generation_mode": generation_mode,
        "gate_kind": kind,
        "command": command,
        "exit_code": exit_code,
        "duration_seconds": round(duration, 3),
        "evaluated_at": _utc_now(),
    }
    tmp = str(eval_json_path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    os.replace(tmp, str(eval_json_path))

    md_lines = [
        f"# {node_id} deterministic gate report",
        "",
        f"- verdict: **{verdict}** ({verdict_kind})",
        f"- gate kind: {kind}",
        f"- command: `{command}`" if command else "- command: (none — contract declares no evaluator gate)",
        f"- exit code: {exit_code}",
        f"- generation: {generation}",
        f"- evaluated at: {payload['evaluated_at']}",
        "",
        summary,
    ]
    if output_tail.strip():
        md_lines += ["", "## Output tail", "", "```", output_tail.strip(), "```"]
    eval_md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return {
        "ok": verdict == "PASS",
        "verdict": verdict,
        "verdict_kind": verdict_kind,
        "eval_json": str(eval_json_path),
        "eval_md": str(eval_md_path),
        "exit_code": exit_code,
    }


def _looks_unrunnable(output_tail: str) -> bool:
    markers = (
        "can't open file",
        "No such file or directory",
        "ModuleNotFoundError",
        "command not found",
    )
    return any(marker in output_tail for marker in markers)
