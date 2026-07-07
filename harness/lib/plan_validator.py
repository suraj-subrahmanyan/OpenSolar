#!/usr/bin/env python3
"""Plan validator for the generic path (Lane 1, design §1.3).

Applies the same compile-check core as workflow_contract — task_type admission
(R2a), obligation legality by node_kind (R2b), normalize-then-check artifact
root containment (R2c, the pm.generic.v1 root policy), and route resolvability
(R2d) — to planner-emitted task graphs. Error codes and the node-kind legality
table are imported from workflow_contract (single source), never redefined.

The bounce-to-planner loop and the PLAN_COMPILE_FAILED terminal live at the
call site (coordinator/pm path, env gate SOLAR_PLAN_VALIDATOR); this module is
pure validation plus the errors-artifact writer that call site uses.

No runtime imports.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_contract as wc  # noqa: E402

GENERIC_CONTRACT_ID = "pm.generic.v1"

# Mirrors pm.generic.v1.workflow.json artifact_roots; used only when the
# contract file is unavailable so validation stays runnable standalone.
FALLBACK_ARTIFACT_ROOTS: Dict[str, Any] = {
    "canonical": "workspace/",
    "aliases": ["sprints/<sid>/workdir/", "workdir/"],
    "root_policy": "normalize_then_check",
}

ERRORS_ARTIFACT_SUFFIX = ".plan-compile-errors.json"


def _generic_contract(workflows_dir: Optional[os.PathLike] = None) -> Optional[Dict[str, Any]]:
    try:
        return wc.find_contract(GENERIC_CONTRACT_ID, workflows_dir)
    except wc.ContractSchemaError:
        return None


def _node_task_type(node: Dict[str, Any]) -> str:
    for key in ("dispatch_task_type", "task_type", "type"):
        value = str(node.get(key) or "").strip()
        if value:
            return value
    return ""


def _node_role(node: Dict[str, Any]) -> str:
    allowed = node.get("allowed_operators") or {}
    for value in (allowed.get("role"), node.get("role")):
        text = str(value or "").strip()
        if text:
            return text
    return "builder"


def validate_plan(
    task_graph: Dict[str, Any],
    capsule_registry: Optional[Dict[str, Dict[str, Any]]],
    operator_registry: Optional[Dict[str, Dict[str, Any]]],
    provider_policy: Optional[Dict[str, Any]] = None,
    contract: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Compile-check a planner-emitted task graph. Empty list = plan compiles.

    Registry arguments set to None skip their check family (admission needs
    capsule_registry; routes need operator_registry) so callers can validate
    incrementally; the product call site passes both.
    """
    if contract is None:
        contract = _generic_contract()
    artifact_roots = dict((contract or {}).get("artifact_roots") or FALLBACK_ARTIFACT_ROOTS)
    policy = provider_policy
    if policy is None:
        policy = (contract or {}).get("provider_policy")

    errors: List[Dict[str, Any]] = []
    for node in task_graph.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "?")
        task_type = _node_task_type(node)

        # R2(a): task_type admitted by the node's resolved capsule — the four
        # historical shapes (analysis / tests / implementationworker /
        # logical-op-map-vs-audit-capsule) all fail here (AC-R2.3).
        capsule_id = str(node.get("capability_capsule_id") or "").strip()
        capsule = capsule_registry.get(capsule_id) if (capsule_registry and capsule_id) else None
        # F2: the bound capsule is the node-kind authority. produces_patch tells
        # classify_node_kind whether the node is even allowed to be code; None
        # (no registry / unknown capsule) falls back to shape + declared narrowing.
        capsule_is_code = capsule.get("produces_patch") if capsule else None
        if capsule_registry is not None and capsule_id:
            if capsule is None:
                errors.append(wc.compile_error(
                    wc.ERROR_CAPSULE_NOT_REGISTERED, node_id,
                    f"node {node_id} references capsule {capsule_id} which is not in the capsule registry",
                    declared=capsule_id,
                ))
            else:
                admitted = sorted(capsule.get("task_type_in") or [])
                if task_type not in admitted:
                    errors.append(wc.compile_error(
                        wc.ERROR_TASK_TYPE_NOT_ADMITTED, node_id,
                        f"node {node_id}: task_type {task_type!r} is not admitted by capsule "
                        f"{capsule_id} (admitted: {admitted})",
                        declared=task_type, admitted=admitted,
                    ))

        # R2(b): obligation legality for the node's (derived) node_kind — the
        # v7 shape: patch_diff obligations on an artifact-authoring node
        # (AC-R2.1, corpus F-049). node_kind is capsule-anchored (F2): a decoy
        # code file or declared node_kind:"code" cannot re-legalize patch proofs.
        node_kind = wc.classify_node_kind(node, capsule_is_code=capsule_is_code)
        legal = wc.legal_proof_kinds(node_kind)
        for obligation in node.get("proof_obligations", []) or []:
            if not isinstance(obligation, dict):
                continue
            proof_kind = wc.classify_obligation(obligation)
            if proof_kind not in legal:
                errors.append(wc.compile_error(
                    wc.ERROR_OBLIGATION_UNSATISFIABLE, node_id,
                    f"node {node_id}: obligation "
                    f"{obligation.get('field') or obligation.get('requirement')!r} classifies as "
                    f"{proof_kind} which is unsatisfiable for node_kind={node_kind!r} "
                    f"(legal: {sorted(legal)}; write_scope has no code targets)",
                    declared=proof_kind, admitted=sorted(legal),
                ))

        # R2(c): normalize-then-check root containment — the v9 shape:
        # write_scope without any declared root prefix (AC-R2.2, corpus F-051).
        for scope_entry in node.get("write_scope", []) or []:
            resolved = wc.resolve_scope_path(str(scope_entry), artifact_roots)
            if resolved is None:
                errors.append(wc.compile_error(
                    wc.ERROR_ARTIFACT_ROOT_UNRESOLVED, node_id,
                    f"node {node_id}: write_scope entry {scope_entry!r} resolves to no declared "
                    f"artifact root (canonical: {artifact_roots.get('canonical')!r}, aliases: "
                    f"{artifact_roots.get('aliases')!r}); a bare relative path is the v9 "
                    f"nondeterminism shape and is rejected, not guessed",
                    declared=str(scope_entry),
                ))

        # R2(d): the node's role resolves under the provider policy.
        if operator_registry is not None:
            role = _node_role(node)
            providers = (node.get("allowed_operators") or {}).get("providers")
            if not wc.resolve_role_operators(role, providers, operator_registry, policy):
                errors.append(wc.compile_error(
                    wc.ERROR_ROUTE_UNRESOLVABLE, node_id,
                    f"node {node_id}: no enabled, healthy, non-deprecated operator resolves for "
                    f"role={role!r} under the provider policy. Remediation: enable a matching "
                    f"operator in harness/config/physical-operators.json or widen "
                    f"provider_policy.allowed_providers.",
                    resolved=[], declared=role,
                ))

    return errors


def write_errors_artifact(
    sprints_dir: os.PathLike,
    sid: str,
    errors: List[Dict[str, Any]],
) -> Path:
    """Write <sid>.plan-compile-errors.json atomically (design §1.3); the
    caller appends these to the planner re-dispatch prompt."""
    sprints = Path(sprints_dir)
    sprints.mkdir(parents=True, exist_ok=True)
    target = sprints / f"{sid}{ERRORS_ARTIFACT_SUFFIX}"
    payload = {
        "sid": sid,
        "error_count": len(errors),
        "errors": errors,
        "terminal_state_on_exhaustion": "PLAN_COMPILE_FAILED",
    }
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def validate_plan_file(
    graph_path: os.PathLike,
    config_dir: Optional[os.PathLike] = None,
    workflows_dir: Optional[os.PathLike] = None,
) -> List[Dict[str, Any]]:
    task_graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    directory = Path(config_dir) if config_dir else wc.default_config_dir()
    capsules = wc.load_capsule_registry(directory)
    operators = wc.load_operator_registry(directory / "physical-operators.json")
    contract = _generic_contract(workflows_dir)
    return validate_plan(task_graph, capsules, operators, contract=contract)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="plan_validator", description=__doc__)
    parser.add_argument("task_graph", help="path to a <sid>.task_graph.json")
    parser.add_argument("--config-dir", default=None)
    parser.add_argument("--workflows-dir", default=None)
    args = parser.parse_args(argv)
    try:
        errors = validate_plan_file(args.task_graph, args.config_dir, args.workflows_dir)
    except Exception as exc:
        print(f"plan_validator: {exc}", file=sys.stderr)
        return 2
    if errors:
        json.dump({"errors": errors}, sys.stdout, indent=2)
        print()
        return 3
    print("plan compiles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
