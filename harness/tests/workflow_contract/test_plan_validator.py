"""The two mandatory rejection replays (AC-R2.1/AC-R2.2) + the four historical
admission shapes (AC-R2.3) + true-negatives, all against the REAL shipped
capsule/operator registries:

- preserved v7 graph (artifact node bound to the implementation capsule with
  patch_diff obligations, corpus F-049) => OBLIGATION_UNSATISFIABLE_FOR_NODE_KIND
- preserved v9 graph (write_scope without the workspace/ prefix, corpus F-051)
  => ARTIFACT_ROOT_UNRESOLVED
- analysis / tests / implementationworker / logical-op-map-vs-audit-capsule
  => TASK_TYPE_NOT_ADMITTED with the offending node id + admitted set
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import plan_validator as pv
import workflow_contract as wc

HARNESS_DIR = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

V7_FIXTURE = FIXTURES_DIR / "v7-rsi-demo-bf66d46b.task_graph.json"
V9_FIXTURE = FIXTURES_DIR / "v9-rsi-demo-fbce668c.task_graph.json"


def test_module_imports_from_this_checkout():
    """No installed-harness imports (R9)."""
    assert Path(pv.__file__).resolve().is_relative_to(HARNESS_DIR.resolve()), pv.__file__


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(graph, capsule_registry, operator_registry, shipped_contracts):
    return pv.validate_plan(
        graph, capsule_registry, operator_registry,
        contract=shipped_contracts["pm.generic.v1"],
    )


# ---------------------------------------------------------------------------
# AC-R2.1: the v7 replay
# ---------------------------------------------------------------------------

def test_v7_graph_rejected_with_obligation_unsatisfiable(
    capsule_registry, operator_registry, shipped_contracts
):
    errors = _validate(_load(V7_FIXTURE), capsule_registry, operator_registry, shipped_contracts)
    unsat = [e for e in errors if e["code"] == wc.ERROR_OBLIGATION_UNSATISFIABLE]
    # three patch-proof obligations on S1: field=patch_diff, check.patch_within_scope,
    # and the "patch_diff exists" pass_condition
    assert len(unsat) == 3, errors
    assert all(e["stage_id"] == "S1" for e in unsat)
    assert all(e["declared"] == wc.PROOF_KIND_PATCH_PROOF for e in unsat)


def test_v7_rejection_is_exactly_the_proof_contract_defect(
    capsule_registry, operator_registry, shipped_contracts
):
    """v7's S1 passed admission live (implementation IS admitted by the
    implementation capsule) and wrote workspace-prefixed paths — the ONLY
    compile defect is the unsatisfiable proof contract."""
    errors = _validate(_load(V7_FIXTURE), capsule_registry, operator_registry, shipped_contracts)
    codes = {e["code"] for e in errors}
    assert codes == {wc.ERROR_OBLIGATION_UNSATISFIABLE}, errors


def test_v7_s1_derives_artifact_node_kind():
    graph = _load(V7_FIXTURE)
    s1 = next(node for node in graph["nodes"] if node["id"] == "S1")
    assert wc.classify_node_kind(s1) == "artifact"


# ---------------------------------------------------------------------------
# AC-R2.2: the v9 replay
# ---------------------------------------------------------------------------

def test_v9_graph_rejected_with_artifact_root_unresolved(
    capsule_registry, operator_registry, shipped_contracts
):
    errors = _validate(_load(V9_FIXTURE), capsule_registry, operator_registry, shipped_contracts)
    unresolved = [e for e in errors if e["code"] == wc.ERROR_ARTIFACT_ROOT_UNRESOLVED]
    # S1 has one bare-relative write_scope entry, S2 has four
    assert len(unresolved) == 5, errors
    assert {e["stage_id"] for e in unresolved} == {"S1", "S2"}
    assert all("rsi-deep-research-report/" in e["declared"] for e in unresolved)


def test_v9_rejection_is_exactly_the_root_defect(
    capsule_registry, operator_registry, shipped_contracts
):
    """v9 ran green node-wise (audit capsule, admitted task types, no patch
    obligations) — the ONLY compile defect is the unresolved artifact root."""
    errors = _validate(_load(V9_FIXTURE), capsule_registry, operator_registry, shipped_contracts)
    codes = {e["code"] for e in errors}
    assert codes == {wc.ERROR_ARTIFACT_ROOT_UNRESOLVED}, errors


def test_workspace_prefixed_scope_resolves_canonical_and_workdir_resolves_alias(shipped_contracts):
    roots = shipped_contracts["pm.generic.v1"]["artifact_roots"]
    assert wc.resolve_scope_path("workspace/rsi-deep-research-report/report.md", roots) == "canonical"
    assert wc.resolve_scope_path("sprints/sprint-x-123/workdir/foo/report.md", roots) == "sprints/<sid>/workdir/"
    assert wc.resolve_scope_path("workdir/foo.py", roots) == "workdir/"
    assert wc.resolve_scope_path("rsi-deep-research-report/report.md", roots) is None
    assert wc.resolve_scope_path("/tmp/escape.md", roots) is None
    assert wc.resolve_scope_path("workspace/../escape.md", roots) is None


# ---------------------------------------------------------------------------
# AC-R2.3: the four historical admission shapes
# ---------------------------------------------------------------------------

def _graph_with(node: dict) -> dict:
    return {"sprint_id": "sprint-admission-shapes", "nodes": [node], "node_results": {}, "gate_results": {}}


_ADMISSION_SHAPES = {
    # F-019: audit/scope node persisted dispatch_task_type=analysis; the audit
    # capsule admits only its canonical read-only types
    "analysis": {
        "id": "A1",
        "goal": "Inventory packaging readiness (F-019 shape).",
        "capability_capsule_id": "cap.requirement-compiler-audit",
        "dispatch_task_type": "analysis",
        "write_scope": ["workspace/audit/readiness-report.md"],
        "depends_on": [],
    },
    # F-030: task_type=tests rejected by the implementation capsule
    "tests": {
        "id": "T1",
        "goal": "Author the test suite (F-030 shape).",
        "capability_capsule_id": "cap.requirement-compiler-implementation",
        "dispatch_task_type": "tests",
        "write_scope": ["workdir/tests/test_tool.py"],
        "depends_on": [],
    },
    # F-044: the logical-operator NAME leaked in as the task type
    "implementationworker": {
        "id": "B1",
        "goal": "Implement the tool (F-044 shape).",
        "logical_operator": "ImplementationWorker",
        "capability_capsule_id": "cap.requirement-compiler-implementation",
        "dispatch_task_type": "implementationworker",
        "write_scope": ["workdir/tool.py"],
        "depends_on": [],
    },
    # F-046 (v3): node resolved to the audit capsule but the logical-op map
    # produced implementation — non-admitted for the resolved capsule
    "logical-op-map-vs-audit-capsule": {
        "id": "S1",
        "goal": "Transform source-pack metadata into sources.json (F-046 shape).",
        "logical_operator": "ImplementationWorker",
        "capability_capsule_id": "cap.requirement-compiler-audit",
        "dispatch_task_type": "implementation",
        "write_scope": ["workspace/rsi-deep-research-report/sources.json"],
        "depends_on": [],
    },
}


def test_four_historical_admission_shapes_all_rejected(
    capsule_registry, operator_registry, shipped_contracts
):
    for label, node in _ADMISSION_SHAPES.items():
        errors = _validate(_graph_with(dict(node)), capsule_registry, operator_registry, shipped_contracts)
        hits = [e for e in errors if e["code"] == wc.ERROR_TASK_TYPE_NOT_ADMITTED]
        assert hits, f"{label}: expected TASK_TYPE_NOT_ADMITTED, got {errors}"
        err = hits[0]
        # AC-R2.3: the offending node id and the admitted set are in the message
        assert err["stage_id"] == node["id"], label
        assert node["id"] in err["message"], label
        assert err["admitted"], label
        assert all(str(t) in err["message"] for t in err["admitted"]), label


# ---------------------------------------------------------------------------
# True-negatives: valid generic plans must NOT be rejected
# ---------------------------------------------------------------------------

def test_v8_shaped_artifact_plan_compiles(capsule_registry, operator_registry, shipped_contracts):
    """The shape that went green live (v8): audit capsule + admitted task type
    + workspace-prefixed scope + presence obligations only."""
    graph = _graph_with({
        "id": "S1",
        "goal": "Transform the source pack into sources.json.",
        "capability_capsule_id": "cap.requirement-compiler-audit",
        "dispatch_task_type": "audit_inventory",
        "write_scope": ["workspace/rsi-deep-research-report/sources.json"],
        "proof_obligations": [
            {"kind": "postcondition", "requirement": "output_present", "field": "sources.json"},
            {"kind": "postcondition", "requirement": "output_present", "field": "handoff_md"},
        ],
        "depends_on": [],
    })
    assert _validate(graph, capsule_registry, operator_registry, shipped_contracts) == []


def test_real_code_node_keeps_patch_obligations(capsule_registry, operator_registry, shipped_contracts):
    """The fe2a7d69 safety net's other half: real code nodes KEEP patch proofs."""
    graph = _graph_with({
        "id": "C1",
        "goal": "Implement the CLI tool.",
        "capability_capsule_id": "cap.requirement-compiler-implementation",
        "dispatch_task_type": "implementation",
        "write_scope": ["workdir/tool.py", "workdir/README.md"],
        "proof_obligations": [
            {"kind": "postcondition", "requirement": "output_present", "field": "patch_diff"},
            {"kind": "self_check", "requirement": "check.patch_within_scope"},
        ],
        "depends_on": [],
    })
    assert _validate(graph, capsule_registry, operator_registry, shipped_contracts) == []


def test_route_unresolvable_for_plan_node(capsule_registry, shipped_contracts):
    graph = _graph_with({
        "id": "N1",
        "goal": "Any node under an empty operator registry.",
        "capability_capsule_id": "cap.requirement-compiler-audit",
        "dispatch_task_type": "audit_inventory",
        "write_scope": ["workspace/x/report.md"],
        "depends_on": [],
    })
    errors = pv.validate_plan(
        graph, capsule_registry, {}, contract=shipped_contracts["pm.generic.v1"]
    )
    assert [e["code"] for e in errors] == [wc.ERROR_ROUTE_UNRESOLVABLE]
    assert "Remediation" in errors[0]["message"]


# ---------------------------------------------------------------------------
# Errors artifact + standalone CLI
# ---------------------------------------------------------------------------

def test_write_errors_artifact(tmp_path):
    errors = [wc.compile_error(wc.ERROR_TASK_TYPE_NOT_ADMITTED, "S1", "msg", admitted=["evidence"])]
    target = pv.write_errors_artifact(tmp_path, "sprint-x", errors)
    assert target == tmp_path / "sprint-x.plan-compile-errors.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["error_count"] == 1
    assert payload["terminal_state_on_exhaustion"] == "PLAN_COMPILE_FAILED"
    assert payload["errors"][0]["code"] == wc.ERROR_TASK_TYPE_NOT_ADMITTED


def test_cli_rejects_v7_fixture_exit_3():
    import os
    env = dict(os.environ)
    env["HARNESS_DIR"] = str(HARNESS_DIR)
    env["PYTHONPATH"] = str(HARNESS_DIR / "lib")
    result = subprocess.run(
        [sys.executable, str(HARNESS_DIR / "lib" / "plan_validator.py"), str(V7_FIXTURE)],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert result.returncode == 3, (result.stdout, result.stderr)
    payload = json.loads(result.stdout)
    assert any(e["code"] == wc.ERROR_OBLIGATION_UNSATISFIABLE for e in payload["errors"])
