"""P5 G3 live rung fix-round: regressions for the two live-run defects.

The G3 live rung (run-archive/p5-g3-live-rung-20260709T161420Z) failed before
builder execution:

1. The dispatch path's capability enrichment mutated the CERTIFIED graph:
   assign_ready -> auto_enrich_graph -> enrich_graph injected
   `required_capabilities: []` into every node whose planner omitted the
   field. required_capabilities is certificate-governed, so the write changed
   the governed hash and the dispatch guard refused the graph it had just
   admitted (PLAN_CERTIFICATE_HASH_MISMATCH; deletion sweep over the archived
   graph reproduces the stamped hash exactly when the injected fields are
   removed). Inference may run before stamping, never after.
2. The refusal then looped silently: the coordinator re-ticked, the guard
   re-refused, and the sprint sat drafting/spec for ~40 minutes until the
   run budget expired with no terminal state. A PASS-stamped graph whose
   governed content changed is unrecoverable at dispatch time (re-stamping
   would launder the edit), so the sprint must fail closed with a truthful
   terminal state — while an UNCERTIFIED refusal stays non-terminal (that is
   the normal pre-planner / bounce state; terminalizing it would recreate the
   E5 starvation class).

Same sandbox conventions as test_p5_g2b_review_fixes.py.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

_HARNESS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_HARNESS / "lib"))

import plan_validator as pv  # noqa: E402

WORKFLOWS_DIR = _HARNESS / "config" / "workflows"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_config(tmp_path: Path) -> tuple[Path, Path]:
    config = tmp_path / "config"
    capsules = config / "capability-capsules"
    workflows = config / "workflows"
    capsules.mkdir(parents=True)
    workflows.mkdir(parents=True)
    shutil.copy2(
        _HARNESS / "config" / "capability-capsules" / "cap.requirement-compiler-implementation.yaml",
        capsules / "cap.requirement-compiler-implementation.yaml",
    )
    shutil.copy2(
        WORKFLOWS_DIR / "pm.generic.v1.workflow.json",
        workflows / "pm.generic.v1.workflow.json",
    )
    _write_json(
        config / "physical-operators.json",
        {
            "version": 1,
            "operators": {
                "test-builder": {
                    "enabled": True,
                    "deprecated": False,
                    "health_status": "ok",
                    "role": "builder",
                    "roles": ["builder"],
                    "provider": "anthropic",
                }
            },
        },
    )
    return config, workflows


def _valid_node(**overrides) -> dict:
    node = {
        "id": "B1",
        "goal": "Implement the requested change.",
        "depends_on": [],
        "task_type": "implementation",
        "dispatch_task_type": "implementation",
        "capability_capsule_id": "cap.requirement-compiler-implementation",
        "allowed_operators": {"role": "builder", "providers": ["anthropic"]},
        "write_scope": ["workspace/harness/lib/example.py"],
        "proof_obligations": [{"proof_kind": "patch_proof", "field": "patch_diff"}],
        "evaluator_gate": {"kind": "llm_eval", "on_fail": "repair_once_then_fail"},
        "status": "pending",
    }
    node.update(overrides)
    return node


def _graph(sid: str, *, node: dict | None = None, **top) -> dict:
    graph = {"sprint_id": sid, "nodes": [node or _valid_node()]}
    graph.update(top)
    return graph


def _write_sprint(sprints: Path, sid: str, graph: dict) -> Path:
    _write_json(
        sprints / f"{sid}.status.json",
        {
            "id": sid,
            "sprint_id": sid,
            "status": "active",
            "phase": "planning_complete",
            "handoff_to": "builder_main",
            "target_role": "builder_main",
            "round": 0,
            "history": [],
        },
    )
    _write_json(sprints / f"{sid}.task_graph.json", graph)
    return sprints / f"{sid}.task_graph.json"


def _certified_sprint(tmp_path: Path, sid: str, monkeypatch) -> tuple[Path, dict]:
    sprints = tmp_path / "sprints"
    config, workflows = _fixture_config(tmp_path)
    graph_path = _write_sprint(sprints, sid, _graph(sid))
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    verdict = pv.compile_planner_graph(sprints, sid, config_dir=config, workflows_dir=workflows)
    assert verdict["stamped"] is True
    stamped = json.loads(graph_path.read_text(encoding="utf-8"))
    assert pv.check_plan_certificate(stamped) == []
    return graph_path, stamped


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("SOLAR_PLAN_VALIDATOR", raising=False)
    monkeypatch.delenv("SOLAR_GATE_LEDGER", raising=False)


# --- Finding 1: capability enrichment must not mutate a certified graph ------

_CAPINF_COPIES = {
    "lib": _HARNESS / "lib" / "capability_inference.py",
    "tools": _HARNESS / "tools" / "capability_inference.py",
}


def _load_capinf(name: str, monkeypatch):
    module_name = f"g3fix_capinf_{name}"
    spec = importlib.util.spec_from_file_location(module_name, _CAPINF_COPIES[name])
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, mod)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("copy_name", sorted(_CAPINF_COPIES))
def test_enrich_graph_leaves_certified_graph_governed_content_untouched(tmp_path, monkeypatch, copy_name):
    """The G3 defect: the planner omitted required_capabilities, enrichment
    injected an empty list into every node, and the governed hash no longer
    matched the PASS certificate."""
    capinf = _load_capinf(copy_name, monkeypatch)
    _, stamped = _certified_sprint(tmp_path, f"sprint-g3fix1-{copy_name}", monkeypatch)
    assert "required_capabilities" not in stamped["nodes"][0]

    enriched = capinf.enrich_graph(copy.deepcopy(stamped))

    assert "required_capabilities" not in enriched["nodes"][0], (
        "enrichment injected a governed field into a certified graph"
    )
    assert pv.check_plan_certificate(enriched) == [], (
        "enrichment invalidated the plan certificate"
    )


@pytest.mark.parametrize("copy_name", sorted(_CAPINF_COPIES))
def test_enrich_graph_still_enriches_uncertified_graphs(monkeypatch, copy_name):
    """Legacy behavior preserved: an uncertified graph still gets the field
    injected (empty or inferred) exactly as before."""
    capinf = _load_capinf(copy_name, monkeypatch)
    graph = _graph("sprint-g3fix1-legacy")
    assert "required_capabilities" not in graph["nodes"][0]

    enriched = capinf.enrich_graph(graph)

    assert "required_capabilities" in enriched["nodes"][0]


def test_auto_enrich_graph_skips_certified_graph(tmp_path, monkeypatch):
    """The live call site: assign_ready -> auto_enrich_graph (graph_scheduler)."""
    import graph_scheduler

    _, stamped = _certified_sprint(tmp_path, "sprint-g3fix1-auto", monkeypatch)

    enriched = graph_scheduler.auto_enrich_graph(copy.deepcopy(stamped))

    assert pv.check_plan_certificate(enriched) == []
    assert "required_capabilities" not in enriched["nodes"][0]


# --- Finding 2: mismatch refusal must terminalize truthfully -----------------


def _queue_dispatcher(monkeypatch, sprints: Path):
    import graph_node_dispatcher as gnd

    monkeypatch.setattr(gnd, "SPRINTS_DIR", sprints)
    monkeypatch.setattr(gnd, "_prepare_human_search_handoff", lambda *a, **k: None)
    monkeypatch.setattr(gnd, "_ensure_lease", lambda *a, **k: {"acquired": True, "reason": "test"})
    monkeypatch.setattr(gnd, "_pane_tui_busy", lambda *a, **k: False)
    monkeypatch.setattr(gnd, "_actorhost_bridge", lambda *a, **k: {})
    monkeypatch.setattr(gnd, "dispatch_policy_block", lambda n, g: "## Architecture Guard\n\n- test")
    monkeypatch.setattr(gnd, "_write_scope_preflight_block", lambda sid, n: "")
    monkeypatch.setattr(gnd, "_canonical_output_paths_block", lambda n: "")
    return gnd


def _queue_item(sid: str, graph_path: Path, node: dict) -> dict:
    return {
        "sprint_id": sid,
        "intent": "graph_node|node_id=B1",
        "priority": 80,
        "payload": {
            "sprint_id": sid,
            "node": copy.deepcopy(node),
            "graph": str(graph_path),
            "assignment": {"pane": "test-pane"},
            "pane": "test-pane",
            "dispatch_id": "test-dispatch",
        },
    }


def _status(sprints: Path, sid: str) -> dict:
    return json.loads((sprints / f"{sid}.status.json").read_text(encoding="utf-8"))


def _tamper(graph_path: Path, stamped: dict) -> dict:
    """The G3 shape: a governed field changes after PASS (here via direct
    edit; live it was the enrichment injection)."""
    tampered = copy.deepcopy(stamped)
    tampered["nodes"][0]["required_capabilities"] = []
    graph_path.write_text(json.dumps(tampered, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert [e["code"] for e in pv.check_plan_certificate(tampered)] == ["PLAN_CERTIFICATE_HASH_MISMATCH"]
    return tampered


def test_dispatch_queue_item_mismatch_terminalizes_sprint(tmp_path, monkeypatch):
    sid = "sprint-g3fix2-queue"
    sprints = tmp_path / "sprints"
    graph_path, stamped = _certified_sprint(tmp_path, sid, monkeypatch)
    tampered = _tamper(graph_path, stamped)
    gnd = _queue_dispatcher(monkeypatch, sprints)

    result = gnd.dispatch_queue_item(_queue_item(sid, graph_path, tampered["nodes"][0]), dry_run=True)

    assert result.get("ok") is False, result
    assert result.get("reason") == "plan_validator_dispatch_refused"
    status = _status(sprints, sid)
    assert status.get("status") == "failed", status
    assert status.get("phase") == "plan_certificate_invalid", status


def test_dispatch_queue_item_uncertified_refusal_does_not_terminalize(tmp_path, monkeypatch):
    """The E5 guard: an uncertified generic graph refusal is a normal
    pre-planner/bounce state and must never terminalize the sprint."""
    sid = "sprint-g3fix2-uncert"
    sprints = tmp_path / "sprints"
    graph = _graph(sid, workflow_contract_id="pm.generic.v1", workflow_contract_version="test")
    graph_path = _write_sprint(sprints, sid, graph)
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    gnd = _queue_dispatcher(monkeypatch, sprints)

    result = gnd.dispatch_queue_item(_queue_item(sid, graph_path, graph["nodes"][0]), dry_run=True)

    assert result.get("ok") is False, result
    status = _status(sprints, sid)
    assert status.get("status") == "active", status
    assert status.get("phase") == "planning_complete", status


_RUNNER_COPIES = {
    "root": _HARNESS / "multi_task_runner.py",
    "tools": _HARNESS / "tools" / "multi_task_runner.py",
    "lib": _HARNESS / "lib" / "multi_task_runner.py",
}


def _load_runner_module(name: str, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("HARNESS_DIR", str(_HARNESS))
    monkeypatch.setenv("HARNESS_SPRINTS_DIR", str(tmp_path / "sprints"))
    module_name = f"g3fix_runner_{name}"
    spec = importlib.util.spec_from_file_location(module_name, _RUNNER_COPIES[name])
    assert spec is not None and spec.loader is not None
    mtr = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, mtr)
    spec.loader.exec_module(mtr)
    monkeypatch.setattr(mtr, "RUN_DIR", tmp_path / "run")
    monkeypatch.setattr(mtr, "SPRINTS_DIR", tmp_path / "sprints")
    return mtr


@pytest.mark.parametrize("copy_name", sorted(_RUNNER_COPIES))
def test_launch_node_mismatch_terminalizes_sprint(tmp_path, monkeypatch, copy_name):
    sid = f"sprint-g3fix2-mtr-{copy_name}"
    sprints = tmp_path / "sprints"
    graph_path, stamped = _certified_sprint(tmp_path, sid, monkeypatch)
    tampered = _tamper(graph_path, stamped)
    mtr = _load_runner_module(copy_name, monkeypatch, tmp_path)

    result = mtr.launch_node(
        graph_path, tampered, tampered["nodes"][0],
        argparse.Namespace(profile="", model="", backend=""), dry_run=True,
    )

    assert result.get("status") == "plan_validator_dispatch_refused", result
    status = _status(sprints, sid)
    assert status.get("status") == "failed", status
    assert status.get("phase") == "plan_certificate_invalid", status


def test_record_helper_only_fires_on_hash_mismatch(tmp_path, monkeypatch):
    """Unit seam: PLAN_CERTIFICATE_MISSING must not transition anything."""
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    sid = "sprint-g3fix2-unit"
    sprints = tmp_path / "sprints"
    _write_sprint(sprints, sid, _graph(sid))

    out = pv.record_certificate_mismatch_refusal(
        sprints, {"sprint_id": sid},
        [{"code": "PLAN_CERTIFICATE_MISSING", "message": "never validated"}],
    )
    assert out.get("attempted") is not True
    assert _status(sprints, sid)["status"] == "active"

    out = pv.record_certificate_mismatch_refusal(
        sprints, {"sprint_id": sid},
        [{"code": "PLAN_CERTIFICATE_HASH_MISMATCH", "message": "governed field changed"}],
    )
    assert out.get("attempted") is True, out
    final = _status(sprints, sid)
    assert final["status"] == "failed"
    assert final["phase"] == "plan_certificate_invalid"
