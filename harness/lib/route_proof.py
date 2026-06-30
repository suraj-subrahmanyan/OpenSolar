#!/usr/bin/env python3
"""Durable provider route proof for graph/runtime sprints."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any


TERMINAL_TASK_STATUSES = {
    "completed",
    "failed",
    "failed_missing_handoff",
    "failed_stale_handoff",
    "cancelled",
    "error",
}

RUNTIME_DEFAULT_ALLOWED_PROVIDERS = {
    "codex": {"openai"},
    "claude": {"anthropic"},
}


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalize_provider(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    aliases = {
        "openai": "openai",
        "codex": "openai",
        "gpt": "openai",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "claude-cli": "anthropic",
        "zhipu": "zhipu",
        "zhipuai": "zhipu",
        "glm": "zhipu",
        "google": "google",
        "gemini": "google",
    }
    return aliases.get(raw, raw)


def _provider_policy_values(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = str(value or "").replace(";", ",").split(",")
    for item in items:
        normalized = _normalize_provider(item)
        if normalized:
            out.add(normalized)
    return out


def _load_operator_registry(harness_dir: Path) -> dict[str, dict[str, Any]]:
    data = _read_json(harness_dir / "config" / "physical-operators.json")
    operators = data.get("operators")
    if isinstance(operators, dict):
        return {str(k): v for k, v in operators.items() if isinstance(v, dict)}
    if isinstance(operators, list):
        result: dict[str, dict[str, Any]] = {}
        for item in operators:
            if not isinstance(item, dict):
                continue
            op_id = str(item.get("id") or item.get("operator_id") or "").strip()
            if op_id:
                result[op_id] = item
        return result
    return {}


def _iter_pm_records(harness_dir: Path, sid: str) -> list[tuple[Path, dict[str, Any]]]:
    inbox = harness_dir / "run" / "pm-inbox"
    rows: list[tuple[Path, dict[str, Any]]] = []
    if not inbox.exists():
        return rows
    for path in sorted(inbox.glob("*.json")):
        data = _read_json(path)
        if str(data.get("sprint_id") or "") == sid or sid in str(data.get("task_id") or path.name):
            rows.append((path, data))
    return rows


def _iter_operator_results(harness_dir: Path, sid: str) -> list[tuple[Path, dict[str, Any]]]:
    root = harness_dir / "run" / "operator-results"
    rows: list[tuple[Path, dict[str, Any]]] = []
    if not root.exists():
        return rows
    for path in sorted(root.glob("*/*/result.json")):
        data = _read_json(path)
        if str(data.get("sprint_id") or "") == sid or sid in str(data.get("task_id") or path.parent.name):
            rows.append((path, data))
    return rows


def _stage_key(data: dict[str, Any], path: Path) -> str:
    task_id = str(data.get("task_id") or "").strip()
    if task_id:
        return task_id
    return str(path)


def _merge_stage(stage: dict[str, Any], data: dict[str, Any], *, source_path: Path, source: str) -> None:
    stage.setdefault("sources", [])
    stage["sources"].append({"source": source, "path": str(source_path)})

    for key in ("task_id", "sprint_id", "node_id", "operator_id"):
        value = str(data.get(key) or "").strip()
        if value and not stage.get(key):
            stage[key] = value
    role = str(data.get("requested_role") or data.get("role") or "").strip()
    if role and not stage.get("role"):
        stage["role"] = role

    if str(data.get("runtime_mode") or "").strip() and not stage.get("runtime_mode"):
        stage["runtime_mode"] = str(data["runtime_mode"]).strip()
    if str(data.get("provider_policy") or "").strip() and not stage.get("provider_policy"):
        stage["provider_policy"] = str(data["provider_policy"]).strip()

    status = str(data.get("status") or "").strip()
    if status:
        stage["status"] = status

    provider = (
        data.get("effective_provider")
        or data.get("operator_provider")
        or data.get("provider")
        or data.get("vendor")
    )
    normalized_provider = _normalize_provider(provider)
    if normalized_provider:
        stage["provider"] = normalized_provider
        stage["provider_raw"] = str(provider)

    model = data.get("effective_model") or data.get("operator_model") or data.get("model") or data.get("routing_model")
    if str(model or "").strip():
        stage["model"] = str(model).strip()
    requested_model = data.get("requested_model")
    if str(requested_model or "").strip():
        stage["requested_model"] = str(requested_model).strip()
    if source == "operator_result":
        stage["result_json"] = str(source_path)
        stage["exit_code"] = data.get("exit_code")


def build_route_proof(
    harness_dir: str | Path,
    sid: str,
    *,
    selected_runtime: str | None = None,
) -> dict[str, Any]:
    """Build a sprint route proof from PM records and operator result artifacts."""
    harness = Path(harness_dir)
    sid = str(sid or "").strip()
    operators = _load_operator_registry(harness)
    stages: dict[str, dict[str, Any]] = {}
    runtime_values: set[str] = set()
    provider_policy_values: set[str] = set()

    for path, data in _iter_pm_records(harness, sid):
        key = _stage_key(data, path)
        stage = stages.setdefault(key, {})
        _merge_stage(stage, data, source_path=path, source="pm_record")
        runtime = str(data.get("runtime_mode") or "").strip().lower()
        if runtime:
            runtime_values.add(runtime)
        provider_policy_values.update(_provider_policy_values(data.get("provider_policy")))

    for path, data in _iter_operator_results(harness, sid):
        key = _stage_key(data, path)
        stage = stages.setdefault(key, {})
        _merge_stage(stage, data, source_path=path, source="operator_result")

    for stage in stages.values():
        op_id = str(stage.get("operator_id") or "").strip()
        op = operators.get(op_id, {})
        if not stage.get("provider"):
            provider = _normalize_provider(op.get("provider") or op.get("vendor") or op.get("backend"))
            if provider:
                stage["provider"] = provider
                stage["provider_raw"] = str(op.get("provider") or op.get("vendor") or op.get("backend") or "")
        if not stage.get("model") and str(op.get("model") or "").strip():
            stage["model"] = str(op["model"]).strip()
        if not stage.get("role") and str(op.get("role") or "").strip():
            stage["role"] = str(op["role"]).strip()

    runtime = str(selected_runtime or "").strip().lower()
    if not runtime and runtime_values:
        runtime = sorted(runtime_values)[0]
    allowed = set(provider_policy_values)
    if not allowed and runtime in RUNTIME_DEFAULT_ALLOWED_PROVIDERS:
        allowed = set(RUNTIME_DEFAULT_ALLOWED_PROVIDERS[runtime])

    violations: list[dict[str, Any]] = []
    enforce = bool(allowed)
    for stage in sorted(stages.values(), key=lambda item: str(item.get("task_id") or item.get("node_id") or "")):
        provider = _normalize_provider(stage.get("provider"))
        status = str(stage.get("status") or "").strip().lower()
        has_result = bool(stage.get("result_json"))
        should_check = enforce and (has_result or status in TERMINAL_TASK_STATUSES)
        if not should_check:
            continue
        if not provider:
            violations.append({
                "task_id": stage.get("task_id"),
                "node_id": stage.get("node_id"),
                "reason": "missing_provider",
            })
        elif provider not in allowed:
            violations.append({
                "task_id": stage.get("task_id"),
                "node_id": stage.get("node_id"),
                "provider": provider,
                "allowed_providers": sorted(allowed),
                "reason": "provider_policy_violation",
            })

    stage_list = sorted(
        stages.values(),
        key=lambda item: (str(item.get("node_id") or ""), str(item.get("task_id") or "")),
    )
    return {
        "ok": not violations,
        "generated_at": _utc_now(),
        "sprint_id": sid,
        "selected_runtime": runtime,
        "allowed_providers": sorted(allowed),
        "enforced": enforce,
        "violations": violations,
        "stage_count": len(stage_list),
        "stages": stage_list,
    }


def write_route_proof(
    harness_dir: str | Path,
    sid: str,
    *,
    selected_runtime: str | None = None,
    sprints_dir: str | Path | None = None,
) -> dict[str, Any]:
    proof = build_route_proof(harness_dir, sid, selected_runtime=selected_runtime)
    out_dir = Path(sprints_dir) if sprints_dir is not None else Path(harness_dir) / "sprints"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{sid}.route-proof.json"
    proof["path"] = str(out)
    out.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return proof
