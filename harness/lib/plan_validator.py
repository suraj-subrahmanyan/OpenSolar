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

# --- P5 G1: planner-graph policy (P5-RUNBOOK owner defaults) ----------------

# R2(e): gate kinds a PLANNER may author. Contracts may waive evaluation with
# "none"; a planner may not — every planner node gets evaluated (llm_eval is
# the default when the gate is absent) unless it runs an allowlisted
# deterministic command.
PLANNABLE_GATE_KINDS = {"llm_eval", "deterministic_command"}

# Launch allowlist (owner decision 2): matched as a TOKEN prefix, not a
# substring — "python3 -m pytest2" must not ride on "python3 -m pytest"
# (vacuous/lookalike-gate hazard, P3 run-2 D2).
GATE_COMMAND_ALLOWLIST = (
    ("python3", "-m", "pytest"),
    ("python3", "scripts/validate_rsi_demo_report.py"),
)

# R2(f): the repair-budget ceiling. instantiate stamps 0/1 from on_fail; 2 is
# headroom for future policies. Anything beyond is an unbounded repair loop.
MAX_REPAIR_ATTEMPTS_CEILING = 2

# on_fail -> budget, the workflow_contract.instantiate convention.
ON_FAIL_BUDGETS = {"fail": 0, "repair_once_then_fail": 1}

# R2(g): over-decomposition bound (epic-explosion hazard) when the contract
# does not carry plan_limits.max_nodes.
DEFAULT_MAX_NODES = 12

ERROR_PLAN_GATE_KIND_ILLEGAL = "PLAN_GATE_KIND_ILLEGAL"
ERROR_PLAN_GATE_COMMAND_NOT_ALLOWLISTED = "PLAN_GATE_COMMAND_NOT_ALLOWLISTED"
ERROR_PLAN_REPAIR_BUDGET_MISSING = "PLAN_REPAIR_BUDGET_MISSING"
ERROR_PLAN_GRAPH_EMPTY = "PLAN_GRAPH_EMPTY"
ERROR_PLAN_GRAPH_TOO_LARGE = "PLAN_GRAPH_TOO_LARGE"
ERROR_PLAN_CERTIFICATE_MISSING = "PLAN_CERTIFICATE_MISSING"
ERROR_PLAN_CERTIFICATE_NOT_PASS = "PLAN_CERTIFICATE_NOT_PASS"
ERROR_PLAN_CERTIFICATE_HASH_MISMATCH = "PLAN_CERTIFICATE_HASH_MISMATCH"

PLAN_CERTIFICATE_SCHEMA = "solar.plan_certificate.v1"

# The GOVERNED node subset the certificate hashes. Runtime fields (status,
# pane, dispatch_id, repair_attempts, ...) mutate on every tick and MUST stay
# outside the hash or dispatch would invalidate its own certificate.
CERTIFICATE_NODE_FIELDS = (
    "id",
    "depends_on",
    "task_type",
    "dispatch_task_type",
    "capability_capsule_id",
    "allowed_capsules",
    "allowed_operators",
    "evaluator_gate",
    "write_scope",
    "proof_obligations",
    "max_repair_attempts",
    "on_human_review",
)


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

        # R2(a) precondition (round-3 Finding A): when a capsule registry is
        # provided, every planner-emitted node MUST bind a capsule. An empty/
        # missing capability_capsule_id skips admission AND leaves capsule_is_code
        # =None below, so the F2 node-kind ceiling never fires — a node declaring
        # node_kind:"code" with a lone workdir/tool.py write_scope would re-legalize
        # patch_diff obligations and compile clean. Reject the unbound node HERE,
        # before classify_node_kind, so it can never reach that ceiling-skip.
        if capsule_registry is not None and not capsule_id:
            errors.append(wc.compile_error(
                wc.ERROR_CAPSULE_UNBOUND, node_id,
                f"node {node_id} has no capability_capsule_id; every planner-emitted "
                f"node must bind a capsule in the registry (an unbound node has no "
                f"task_type admission and no node-kind ceiling, so it cannot be "
                f"compile-checked). Remediation: set capability_capsule_id to a "
                f"registered capsule.",
            ))
            continue

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

        # R2(e): gate legality — a planner may not waive evaluation ("none")
        # or run an arbitrary command; deterministic gates come from the
        # launch allowlist only, everything else is llm_eval.
        gate = node.get("evaluator_gate") if isinstance(node.get("evaluator_gate"), dict) else {}
        gate_kind = str(gate.get("kind") or "llm_eval").strip()
        if gate_kind not in PLANNABLE_GATE_KINDS:
            errors.append(wc.compile_error(
                ERROR_PLAN_GATE_KIND_ILLEGAL, node_id,
                f"node {node_id}: evaluator_gate.kind {gate_kind!r} is not plannable "
                f"(plannable: {sorted(PLANNABLE_GATE_KINDS)}; contracts may waive "
                f"evaluation, a planner may not)",
                declared=gate_kind, admitted=sorted(PLANNABLE_GATE_KINDS),
            ))
        elif gate_kind == "deterministic_command":
            command_tokens = str(gate.get("command") or "").split()
            allowed = any(
                command_tokens[: len(prefix)] == list(prefix)
                for prefix in GATE_COMMAND_ALLOWLIST
            )
            if not allowed:
                errors.append(wc.compile_error(
                    ERROR_PLAN_GATE_COMMAND_NOT_ALLOWLISTED, node_id,
                    f"node {node_id}: deterministic_command {gate.get('command')!r} does not "
                    f"match the launch allowlist "
                    f"({[' '.join(p) for p in GATE_COMMAND_ALLOWLIST]}); use llm_eval or an "
                    f"allowlisted checker",
                    declared=str(gate.get("command") or ""),
                ))

        # R2(f): the repair budget is stamped at birth (contract-determined on
        # the fixed path; planner-declared here), never a runtime default.
        budget = node.get("max_repair_attempts")
        if budget is None:
            budget = ON_FAIL_BUDGETS.get(str(gate.get("on_fail") or ""))
        if not isinstance(budget, int) or not (0 <= budget <= MAX_REPAIR_ATTEMPTS_CEILING):
            errors.append(wc.compile_error(
                ERROR_PLAN_REPAIR_BUDGET_MISSING, node_id,
                f"node {node_id}: no stamped repair budget "
                f"(max_repair_attempts int in [0,{MAX_REPAIR_ATTEMPTS_CEILING}], or "
                f"evaluator_gate.on_fail in {sorted(ON_FAIL_BUDGETS)})",
                declared=repr(node.get("max_repair_attempts")),
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

    # F3: graph structure — depends_on existence + acyclicity on the planner
    # path (the schema path already had these for fixed contracts). A cyclic or
    # dangling-dep graph must reject at compile, never hang the scheduler.
    errors.extend(_validate_graph_structure(task_graph))

    # R2(g): size bound — an empty plan does nothing; an epic explosion
    # (corpus hazard) is rejected at compile, not discovered at dispatch.
    node_count = len([n for n in task_graph.get("nodes", []) or [] if isinstance(n, dict)])
    max_nodes = ((contract or {}).get("plan_limits") or {}).get("max_nodes") or DEFAULT_MAX_NODES
    if node_count == 0:
        errors.append(wc.compile_error(
            ERROR_PLAN_GRAPH_EMPTY, "?",
            "planner graph has no nodes",
        ))
    elif node_count > int(max_nodes):
        errors.append(wc.compile_error(
            ERROR_PLAN_GRAPH_TOO_LARGE, "?",
            f"planner graph has {node_count} nodes; the bound is {max_nodes} "
            f"(plan_limits.max_nodes / DEFAULT_MAX_NODES) — decompose into epics "
            f"or raise the contract limit deliberately",
            declared=node_count, admitted=int(max_nodes),
        ))

    return errors


# --- P5 G1: plan_certificate (governed graph birth) --------------------------

def plan_certificate_hash(task_graph: Dict[str, Any]) -> str:
    """sha256 over the governed subset — contract identity + per-node policy
    fields. Runtime fields (status/pane/dispatch_id/...) are excluded so
    dispatch cannot invalidate its own certificate."""
    import hashlib

    governed = {
        "workflow_contract_id": str(task_graph.get("workflow_contract_id") or ""),
        "workflow_contract_version": str(task_graph.get("workflow_contract_version") or ""),
        "nodes": [
            {field: node.get(field) for field in CERTIFICATE_NODE_FIELDS if field in node}
            for node in sorted(
                (n for n in task_graph.get("nodes", []) or [] if isinstance(n, dict)),
                key=lambda n: str(n.get("id") or ""),
            )
        ],
    }
    canonical = json.dumps(governed, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def stamp_plan_certificate(
    task_graph: Dict[str, Any],
    capsule_registry: Optional[Dict[str, Dict[str, Any]]] = None,
    operator_registry: Optional[Dict[str, Dict[str, Any]]] = None,
    contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate and stamp. Raises ValueError on a graph that does not compile —
    a certificate is a PASS verdict, never a participation trophy."""
    errors = validate_plan(task_graph, capsule_registry, operator_registry, contract=contract)
    if errors:
        raise ValueError(
            f"plan does not compile ({len(errors)} errors); refusing to stamp: "
            f"{[e.get('code') for e in errors]}"
        )
    import time

    certificate = {
        "schema": PLAN_CERTIFICATE_SCHEMA,
        "validator": "plan_validator",
        "verdict": "PASS",
        "graph_hash": plan_certificate_hash(task_graph),
        "validated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    task_graph["plan_certificate"] = certificate
    return certificate


def check_plan_certificate(task_graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Re-derive the governed hash and compare against the stamped verdict.
    Empty list = the graph is certificate-covered and untampered."""
    certificate = task_graph.get("plan_certificate")
    if not isinstance(certificate, dict) or not certificate:
        return [wc.compile_error(
            ERROR_PLAN_CERTIFICATE_MISSING, "?",
            "planner graph carries no plan_certificate; it was never validated "
            "(or the certificate was stripped)",
        )]
    if str(certificate.get("verdict") or "") != "PASS":
        return [wc.compile_error(
            ERROR_PLAN_CERTIFICATE_NOT_PASS, "?",
            f"plan_certificate verdict is {certificate.get('verdict')!r}, not PASS",
            declared=str(certificate.get("verdict") or ""),
        )]
    expected = plan_certificate_hash(task_graph)
    stamped = str(certificate.get("graph_hash") or "")
    if stamped != expected:
        return [wc.compile_error(
            ERROR_PLAN_CERTIFICATE_HASH_MISMATCH, "?",
            "plan_certificate.graph_hash does not match the governed graph "
            "content — a governed field changed after validation "
            f"(stamped {stamped[:12]}..., recomputed {expected[:12]}...)",
            declared=stamped, admitted=expected,
        )]
    return []


def _validate_graph_structure(task_graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes = [n for n in task_graph.get("nodes", []) or [] if isinstance(n, dict)]
    node_ids = {str(n.get("id")) for n in nodes if n.get("id") is not None}
    errors: List[Dict[str, Any]] = []
    deps_map: Dict[str, List[str]] = {}
    for node in nodes:
        if node.get("id") is None:
            continue
        node_id = str(node.get("id"))
        deps = [str(d) for d in (node.get("depends_on") or [])]
        deps_map[node_id] = deps
        for dep in deps:
            if dep not in node_ids:
                errors.append(wc.compile_error(
                    wc.ERROR_DEP_NOT_FOUND, node_id,
                    f"node {node_id} depends_on {dep!r} which is not a node in this graph",
                    declared=dep,
                ))
    cyclic = wc.first_cycle_node(deps_map)
    if cyclic is not None:
        errors.append(wc.compile_error(
            wc.ERROR_GRAPH_CYCLIC, cyclic,
            f"node {cyclic!r} is part of a depends_on cycle; the graph is not a DAG",
            declared=cyclic,
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
