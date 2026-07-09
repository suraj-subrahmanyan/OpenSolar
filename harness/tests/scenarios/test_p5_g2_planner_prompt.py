"""P5 G2 follow-up: the planner dispatch prompt must teach the compile policy.

The G2 live battery (p5-g2-battery-20260708T205146Z) measured compile_rate
0.0 — 0 compiled / 5 rejected, CAPSULE_UNBOUND x20, PLAN_REPAIR_BUDGET_MISSING
x3. The planner objective told the planner to write task_graph.json but never
said what a compilable node must contain, so the live planner emitted bare
nodes (no capsule binding, no evaluator gate, no repair budget).

Fix under test: plan_validator.planner_compile_policy_block() — a single-
source, env-gated, registry-driven prompt block appended by BOTH planner
objective builders (lib/intent_consumer.py and tools/pm_dispatch.py), with
previous compile errors included on re-dispatch so a bounced planner repairs
instead of re-guessing.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_HARNESS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_HARNESS / "lib"))

import plan_validator as pv  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture(autouse=True)
def _anchor_env(monkeypatch):
    monkeypatch.delenv("SOLAR_PLAN_VALIDATOR", raising=False)
    # Anchor registry/contract lookups to the repo harness, not ~/.solar.
    monkeypatch.setenv("HARNESS_DIR", str(_HARNESS))


def test_policy_block_is_empty_when_env_off():
    assert pv.planner_compile_policy_block() == ""


def test_policy_block_teaches_the_compile_rules_when_env_on(monkeypatch):
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")

    block = pv.planner_compile_policy_block()

    # The two live failure classes from the G2 battery, by name:
    assert "capability_capsule_id" in block
    assert "CAPSULE_UNBOUND" in block
    assert "max_repair_attempts" in block
    assert "PLAN_REPAIR_BUDGET_MISSING" in block
    # Registry-driven capsule list (not hardcoded): a shipped capsule id with
    # its admitted task types must be present.
    assert "cap.requirement-compiler-implementation" in block
    assert "implementation" in block
    # Gate policy: llm_eval default, allowlisted deterministic commands only.
    assert "llm_eval" in block
    assert "python3 -m pytest" in block
    # Artifact-root containment and the graph size bound.
    assert "workspace/" in block
    assert str(pv.DEFAULT_MAX_NODES) in block


def test_policy_block_appends_previous_compile_errors_on_bounce(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    sid = "sprint-g2-bounce"
    sprints = tmp_path / "sprints"
    pv.write_errors_artifact(
        sprints,
        sid,
        [
            {
                "code": "CAPSULE_UNBOUND",
                "node_id": "S1",
                "message": "node S1 has no capability_capsule_id",
            }
        ],
        bounce_count=1,
        graph_hash="abc123",
        exhausted=False,
        terminal=False,
    )

    block = pv.planner_compile_policy_block(sprints, sid)

    assert "CAPSULE_UNBOUND" in block
    assert "S1" in block
    assert "node S1 has no capability_capsule_id" in block
    assert "bounce" in block.lower()


def test_policy_block_without_bounce_artifact_has_no_error_section(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    block = pv.planner_compile_policy_block(tmp_path / "sprints", "sprint-g2-clean")
    assert "previous compile errors" not in block.lower()


def test_intent_consumer_objective_includes_policy_only_when_env_on(tmp_path, monkeypatch):
    import intent_consumer as ic

    monkeypatch.setattr(ic, "SPRINTS_DIR", tmp_path / "sprints")

    off = ic.planner_objective_for_compiled_sprint("sprint-g2-ic")
    assert "capability_capsule_id" not in off

    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    on = ic.planner_objective_for_compiled_sprint("sprint-g2-ic")
    assert "capability_capsule_id" in on
    assert "CAPSULE_UNBOUND" in on
    # The legacy objective text is preserved, the block is appended.
    assert on.startswith(off)


def test_pm_dispatch_objective_includes_policy_only_when_env_on(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "pm_dispatch_under_test", _HARNESS / "tools" / "pm_dispatch.py"
    )
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)
    monkeypatch.setattr(pm, "SPRINTS_DIR", tmp_path / "sprints")

    off = pm._planner_objective_for_compiled_sprint("sprint-g2-pm")
    assert "capability_capsule_id" not in off

    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    on = pm._planner_objective_for_compiled_sprint("sprint-g2-pm")
    assert "capability_capsule_id" in on
    assert "CAPSULE_UNBOUND" in on
    assert on.startswith(off)
