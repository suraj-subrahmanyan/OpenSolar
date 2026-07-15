"""Artifact manifest — per-node artifact discovery authority (Lane 3, design §1.5 / R6).

After build/repair the dispatcher writes a manifest next to the sprint:

  <sid>.<safe_node>-manifest.json

Rows resolve each declared output against the contract's artifact roots
(canonical first, then aliases — the v9 workdir/workspace class), carrying
{declared, path, rel_path, resolved_root, exists, size, sha256, mtime}.
Sidecars (handoff/patch/guard/resource/eval[]) are keyed by KIND, never by
filename shape (AC-R6.2). Observed writes outside every declared root are
reported as ARTIFACT_ROOT_VIOLATION (AC-R6.3) and surface in presence_map so
the proof gate blocks.

Same discipline as gate_ledger/node_runstate: stdlib only, atomic writes,
best-effort (returns None on failure, never raises into the dispatch path).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

ARTIFACT_ROOT_VIOLATION = "ARTIFACT_ROOT_VIOLATION"

# Sidecar kinds whose presence the proof gate consumes; "eval" is a list.
SIDECAR_KINDS = ("handoff_md", "patch_diff", "guard_decision", "resource_binding", "eval", "test_log")


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_node_id(node_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(node_id or "")).strip("-") or "node"


def manifest_path(sprints_dir: Any, sid: str, node_id: str) -> Path:
    return Path(sprints_dir) / f"{sid}.{_safe_node_id(node_id)}-manifest.json"


def _file_row(declared: str, path: Path, resolved_root: str) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "declared": declared,
        "rel_path": declared,
        "path": str(path) if resolved_root else "",
        "resolved_root": resolved_root,
        "exists": False,
        "size": None,
        "sha256": None,
        "mtime": None,
    }
    try:
        if resolved_root and path.is_file():
            stat = path.stat()
            row["exists"] = True
            row["size"] = stat.st_size
            row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            row["mtime"] = datetime.datetime.fromtimestamp(
                stat.st_mtime, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    return row


def _default_base_dir() -> Path:
    """Anchor for RELATIVE roots/paths. P2 smoke 20260707T190540Z: resolving
    relative contract roots against the process CWD lost artifacts that
    existed on disk and failed a healthy stage."""
    harness_dir = os.environ.get("HARNESS_DIR") or os.environ.get("SOLAR_HARNESS_DIR")
    if harness_dir:
        return Path(harness_dir).expanduser()
    return Path.cwd()


def _anchor(path_text: str, base: Path) -> Path:
    path = Path(str(path_text)).expanduser()
    return path if path.is_absolute() else base / path


def _ordered_roots(roots: Dict[str, str], base: Path) -> List[tuple[str, Path]]:
    """Canonical first, then aliases in name order — deterministic resolution.
    Relative roots anchor at base (HARNESS_DIR), never the CWD."""
    items: List[tuple[str, Path]] = []
    if roots.get("canonical"):
        items.append(("canonical", _anchor(roots["canonical"], base)))
    for name in sorted(roots):
        if name == "canonical" or not roots.get(name):
            continue
        items.append((name, _anchor(roots[name], base)))
    return items


def _resolve_declared(declared: str, roots: Dict[str, str], base: Path) -> tuple[Path, str]:
    """Resolve a declared output path to (absolute path, owning root name).

    Resolution order: (1) absolute declared → owning root by prefix;
    (2) base-anchored declared that exists inside a root (contracts whose
    write_scope already carries the relative root prefix — the code.cli_smoke
    shape); (3) alias probing — declared joined under each root, canonical
    first (the v9 rule). Returns (anchored path, "") when nothing matches.
    """
    ordered = _ordered_roots(roots, base)
    raw = Path(str(declared)).expanduser()
    if raw.is_absolute():
        for name, root in ordered:
            try:
                raw.relative_to(root)
            except ValueError:
                continue
            return raw, name
        return raw, ""
    anchored = base / raw
    if anchored.exists():
        for name, root in ordered:
            try:
                anchored.relative_to(root)
            except ValueError:
                continue
            return anchored, name
    for name, root in ordered:
        candidate = root / raw
        if candidate.exists():
            return candidate, name
    return anchored, ""


def write_manifest(
    sprints_dir: Any,
    sid: str,
    node: Dict[str, Any],
    *,
    generation: int,
    roots: Optional[Dict[str, str]] = None,
    write_scope: Optional[List[str]] = None,
    sidecars: Optional[Dict[str, Any]] = None,
    observed: Optional[List[str]] = None,
    operator_result_ids: Optional[List[str]] = None,
    base_dir: Optional[os.PathLike] = None,
) -> Optional[Dict[str, Any]]:
    """Build + atomically persist the per-node manifest; returns it or None.

    ``write_scope`` defaults to the node's declared write_scope. ``observed``
    is the set of paths the node actually wrote (when the caller knows them);
    any observed path outside every declared root becomes an
    ARTIFACT_ROOT_VIOLATION entry. ``base_dir`` anchors RELATIVE roots and
    paths (defaults to HARNESS_DIR from env; never the raw CWD when a harness
    is resolvable).
    """
    try:
        sid = str(sid or "").strip()
        node_id = str((node or {}).get("id") or "").strip()
        if not sid or not node_id:
            return None
        base = Path(base_dir).expanduser() if base_dir else _default_base_dir()
        roots = {str(k): str(v) for k, v in (roots or {}).items() if str(v or "").strip()}
        declared_paths = list(write_scope if write_scope is not None else (node.get("write_scope") or []))

        rows: List[Dict[str, Any]] = []
        for declared in declared_paths:
            declared = str(declared or "").strip()
            if not declared:
                continue
            resolved, root_name = _resolve_declared(declared, roots, base)
            rows.append(_file_row(declared, resolved, root_name))

        violations: List[Dict[str, Any]] = []
        ordered = _ordered_roots(roots, base)
        for raw in observed or []:
            observed_path = _anchor(str(raw), base)
            inside = False
            for _name, root in ordered:
                try:
                    observed_path.relative_to(root)
                    inside = True
                    break
                except ValueError:
                    continue
            if not inside:
                violations.append({"code": ARTIFACT_ROOT_VIOLATION, "path": str(observed_path)})

        sidecar_map: Dict[str, Any] = {}
        for kind, value in (sidecars or {}).items():
            if isinstance(value, (list, tuple)):
                sidecar_map[kind] = [
                    {"path": str(item), "exists": Path(str(item)).expanduser().is_file()}
                    for item in value if str(item or "").strip()
                ]
            elif str(value or "").strip():
                path = Path(str(value)).expanduser()
                sidecar_map[kind] = {"path": str(value), "exists": path.is_file()}

        manifest: Dict[str, Any] = {
            "schema": "solar.artifact_manifest.v1",
            "sid": sid,
            "node_id": node_id,
            "generation": int(generation),
            "written_at": _utc_now(),
            # Store ANCHORED roots so consumers (publish, wrapper, dashboard)
            # never re-resolve relative paths against their own CWD.
            "roots": {name: str(path) for name, path in ordered},
            "rows": rows,
            "all_outputs_present": bool(rows) and all(row["exists"] for row in rows) if rows else True,
            "sidecars": sidecar_map,
            "violations": violations,
            "operator_result_ids": list(operator_result_ids or []),
        }

        sprints = Path(sprints_dir)
        sprints.mkdir(parents=True, exist_ok=True)
        target = manifest_path(sprints, sid, node_id)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, target)
        return manifest
    except Exception:
        return None


def read_manifest(sprints_dir: Any, sid: str, node_id: str) -> Dict[str, Any]:
    try:
        path = manifest_path(sprints_dir, sid, node_id)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def presence_map(manifest: Dict[str, Any]) -> Dict[str, bool]:
    """Proof-gate view of a manifest: sidecar kinds + outputs + root violations.

    ``eval`` maps to the gate's ``eval_json`` key; guard presence requires the
    sidecar to exist (decision semantics stay with the dispatcher's guard scan).
    """
    presence: Dict[str, bool] = {}
    sidecars = manifest.get("sidecars") if isinstance(manifest.get("sidecars"), dict) else {}
    for kind, value in sidecars.items():
        if isinstance(value, list):
            exists = any(bool(item.get("exists")) for item in value if isinstance(item, dict))
        else:
            exists = bool(isinstance(value, dict) and value.get("exists"))
        presence["eval_json" if kind == "eval" else kind] = exists
    for row in manifest.get("rows") or []:
        if isinstance(row, dict) and str(row.get("declared") or ""):
            present = bool(row.get("exists"))
            if not present:
                # Rows are hashed as files (exists=false for directories so
                # publish_canonical never copy2()s a dir), but for the proof
                # gate an existing DIRECTORY satisfies a declared scope.
                declared_path = str(row.get("path") or "")
                present = bool(declared_path) and Path(declared_path).is_dir()
            presence[f"output:{row['declared']}"] = present
    presence["all_outputs_present"] = bool(manifest.get("all_outputs_present"))
    presence["artifact_root_violation"] = bool(manifest.get("violations"))
    return presence


def publish_canonical(manifest: Dict[str, Any], canonical_root: Any) -> List[Dict[str, Any]]:
    """Copy every resolved, existing row into the canonical root (AC-R6.1).

    Rows already under canonical are untouched. Returns the copies performed."""
    copies: List[Dict[str, Any]] = []
    try:
        canonical = Path(str(canonical_root)).expanduser()
        for row in manifest.get("rows") or []:
            if not (isinstance(row, dict) and row.get("exists") and row.get("path")):
                continue
            source = Path(str(row["path"]))
            target = canonical / str(row.get("rel_path") or row.get("declared") or source.name)
            try:
                if source.resolve() == target.resolve():
                    continue
            except Exception:
                pass
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copies.append({"from": str(source), "to": str(target)})
    except Exception:
        pass
    return copies


def _workspace_relative_path(row: Dict[str, Any]) -> Path:
    """Map a staged ``workspace/...`` declaration into the user's root.

    The explicit prefix is an authority boundary, not a directory to recreate
    in the user's project.  Rejecting every ambiguous spelling keeps a
    manifest from turning into an arbitrary filesystem-copy instruction.
    """
    raw = str(row.get("rel_path") or row.get("declared") or "").strip()
    normalized = raw.replace("\\", "/").rstrip("/")
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise ValueError(f"output path must be relative: {raw!r}")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"output path contains an unsafe segment: {raw!r}")
    if parts[0] != "workspace" or len(parts) < 2:
        raise ValueError(f"output path must start with workspace/: {raw!r}")
    return Path(*parts[1:])


def _has_symlink_from(root: Path, path: Path) -> bool:
    """Return true when root or any lexical descendant component is a link."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    cursor = root
    if cursor.is_symlink():
        return True
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return True
    return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def publish_workspace_outputs(
    manifest: Dict[str, Any],
    workspace_root: Any,
) -> Dict[str, Any]:
    """Publish verified staging outputs once into the bound user workspace.

    This is deliberately stricter than the legacy ``publish_canonical`` helper:
    all rows are validated before the first copy, source and destination
    symlinks are refused, declarations must live below ``workspace/``, and each
    file is replaced atomically.  Existing staging evidence is never moved or
    deleted.  Directory declarations are expanded without following links.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "reason": "",
        "workspace_root": "",
        "published": [],
        "errors": [],
    }
    try:
        workspace = Path(str(workspace_root)).expanduser()
        if not workspace.is_absolute():
            raise ValueError("workspace root must be absolute")
        if workspace.is_symlink() or not workspace.is_dir():
            raise ValueError("workspace root must be an existing non-symlink directory")
        workspace = workspace.resolve(strict=True)
        result["workspace_root"] = str(workspace)

        roots_payload = manifest.get("roots") if isinstance(manifest.get("roots"), dict) else {}
        rows = manifest.get("rows") if isinstance(manifest.get("rows"), list) else []
        operations: dict[Path, Path] = {}
        directories: set[Path] = set()

        if not rows:
            raise ValueError("manifest has no output rows")

        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(f"manifest row {index} is not an object")
            root_name = str(row.get("resolved_root") or "").strip()
            source_text = str(row.get("path") or "").strip()
            if not root_name or not source_text:
                raise ValueError(f"manifest row {index} is unresolved")
            root_text = str(roots_payload.get(root_name) or "").strip()
            if not root_text:
                raise ValueError(f"manifest row {index} references unknown root {root_name!r}")

            source = Path(source_text).expanduser()
            root = Path(root_text).expanduser()
            if not source.is_absolute() or not root.is_absolute():
                raise ValueError(f"manifest row {index} uses a relative source/root")
            source_lexical = Path(os.path.abspath(source))
            root_lexical = Path(os.path.abspath(root))
            try:
                source_lexical.relative_to(root_lexical)
            except ValueError as exc:
                raise ValueError(f"manifest row {index} escapes its resolved root") from exc
            if _has_symlink_from(root_lexical, source_lexical):
                raise ValueError(f"manifest row {index} source traverses a symlink")
            try:
                source_resolved = source_lexical.resolve(strict=True)
                root_resolved = root_lexical.resolve(strict=True)
                source_resolved.relative_to(root_resolved)
            except (OSError, RuntimeError, ValueError) as exc:
                raise ValueError(f"manifest row {index} source is missing or outside its root") from exc

            destination_rel = _workspace_relative_path(row)
            destination = workspace / destination_rel
            if source_resolved.is_file():
                prior = operations.get(destination)
                if prior is not None and prior != source_resolved:
                    raise ValueError(f"multiple sources target {destination}")
                operations[destination] = source_resolved
                directories.add(destination.parent)
            elif source_resolved.is_dir():
                directories.add(destination)
                for current, dirnames, filenames in os.walk(source_resolved, followlinks=False):
                    current_path = Path(current)
                    for name in [*dirnames, *filenames]:
                        if (current_path / name).is_symlink():
                            raise ValueError(f"manifest row {index} directory contains a symlink")
                    relative_dir = current_path.relative_to(source_resolved)
                    target_dir = destination / relative_dir
                    directories.add(target_dir)
                    for name in filenames:
                        child_source = current_path / name
                        child_target = target_dir / name
                        prior = operations.get(child_target)
                        if prior is not None and prior != child_source:
                            raise ValueError(f"multiple sources target {child_target}")
                        operations[child_target] = child_source
            else:
                raise ValueError(f"manifest row {index} is not a regular file or directory")

        # Validate the complete destination set before mutating the workspace.
        for destination in [*directories, *operations]:
            try:
                destination.relative_to(workspace)
            except ValueError as exc:
                raise ValueError(f"publish destination escapes workspace: {destination}") from exc
            cursor = workspace
            for part in destination.relative_to(workspace).parts:
                cursor = cursor / part
                if cursor.exists() or cursor.is_symlink():
                    if cursor.is_symlink():
                        raise ValueError(f"publish destination traverses a symlink: {cursor}")
            if destination in operations and destination.exists() and not destination.is_file():
                raise ValueError(f"file destination is not a regular file: {destination}")

        for directory in sorted(directories, key=lambda path: (len(path.parts), str(path))):
            directory.mkdir(parents=True, exist_ok=True)

        published: List[Dict[str, Any]] = []
        for destination, source in sorted(operations.items(), key=lambda item: str(item[0])):
            fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
            os.close(fd)
            temporary = Path(temporary_name)
            try:
                shutil.copy2(source, temporary, follow_symlinks=False)
                with temporary.open("rb") as handle:
                    os.fsync(handle.fileno())
                digest = _sha256_file(temporary)
                os.replace(temporary, destination)
                published.append({"from": str(source), "to": str(destination), "sha256": digest})
            finally:
                temporary.unlink(missing_ok=True)

        result["ok"] = True
        result["published"] = published
        return result
    except Exception as exc:
        result["reason"] = "workspace_publish_validation_failed"
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        return result
