"""P7 R0 — cap.research-retrieval capsule exists and is wired.

Design: run-archive/p2-runbook/P7-RESEARCH-GROUNDING-DESIGN-DRAFT.md §3a
(decisions locked 2026-07-12). The retrieval capsule generalizes
cap.requirement-research-scout from requirement-compilation to any
research prompt. Its REQUIRED outputs are the closeout evaluator's real
wire format (sources.jsonl + evidence.jsonl + extracts/) so the
artifact-triggered research quality gate and the MISSING_DECLARED_OUTPUT
proof gate govern retrieval output without any new enforcement code.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

_HARNESS = Path(__file__).resolve().parents[2]
_HARNESS_LIB = str(_HARNESS / "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

import capability_capsules as cc  # noqa: E402
import plan_validator as pv  # noqa: E402
import workflow_contract as wc  # noqa: E402

CONFIG_DIR = _HARNESS / "config"
MANIFEST_PATH = CONFIG_DIR / "capability-capsules" / "cap.research-retrieval.yaml"
REGISTRY_PATH = CONFIG_DIR / "capability-capsules.registry.yaml"
CAPSULE_ID = "cap.research-retrieval"


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_registry_loader_exposes_research_retrieval():
    registry = wc.load_capsule_registry(CONFIG_DIR)
    assert CAPSULE_ID in registry, "cap.research-retrieval missing from capsule registry"
    entry = registry[CAPSULE_ID]
    assert entry["task_type_in"] == ["knowledge-extraction", "research"]
    assert entry["produces_patch"] is False


def test_manifest_validates_clean():
    errors = cc.validate_capability_capsule(_manifest())
    assert errors == []


def test_manifest_declares_evaluator_wire_format_outputs():
    contract = _manifest()["contract"]
    required = {str(o["name"]) for o in contract["outputs"]["required"]}
    assert required == {"sources_jsonl", "evidence_jsonl", "extracts_dir"}
    post_fields = {
        str(cond.get("field"))
        for cond in contract["postconditions"]
        if cond.get("check") == "output_present"
    }
    assert {"sources_jsonl", "evidence_jsonl"} <= post_fields


def test_manifest_keeps_planner_shape_free():
    # NO fixed research DAG (owner decision): the capsule must not chain a
    # mandatory successor the way the scout chains the synthesizer.
    composition = _manifest()["composition"]
    assert composition.get("requires_after") in (None, [])


def test_manifest_requires_secret_leak_guard():
    bindings = _manifest()["bindings"]
    assert "guard.secret-leak-guard" in (bindings.get("required_guard_capsules") or [])


def test_registry_yaml_lists_capsule_as_stable():
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    entries = {
        e["capability_capsule_id"]: e
        for e in (registry.get("capsules") or {}).get("capability") or []
    }
    assert CAPSULE_ID in entries
    entry = entries[CAPSULE_ID]
    assert entry["status"] == "stable"
    assert entry["manifest_path"] == "capability-capsules/cap.research-retrieval.yaml"


def test_planner_policy_block_offers_capsule(monkeypatch):
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    block = pv.planner_compile_policy_block(config_dir=CONFIG_DIR)
    assert f"- {CAPSULE_ID}:" in block
    assert "knowledge-extraction" in block
