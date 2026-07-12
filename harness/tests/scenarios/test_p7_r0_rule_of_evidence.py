"""P7 R0 — planner rule-of-evidence paragraph at the G2b choke point.

Design: P7-RESEARCH-GROUNDING-DESIGN-DRAFT.md §3c — teach, never force.
The planner compile policy block (the single source both planner
objective builders append, plan_validator.planner_compile_policy_block)
gains a research rule of evidence: claims consume a source pack; declare
what you retrieve and what you claim. The planner keeps pm.generic.v1
graph freedom — no compile error enforces a research shape; the quality
gate judges the OUTCOME.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HARNESS = Path(__file__).resolve().parents[2]
_HARNESS_LIB = str(_HARNESS / "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

import plan_validator as pv  # noqa: E402

CONFIG_DIR = _HARNESS / "config"


def _block(monkeypatch, gate: str) -> str:
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", gate)
    return pv.planner_compile_policy_block(config_dir=CONFIG_DIR)


def test_policy_block_teaches_rule_of_evidence(monkeypatch):
    block = _block(monkeypatch, "1")
    assert "## Rule of evidence (research prompts)" in block
    assert "cap.research-retrieval" in block
    assert "sources.jsonl" in block and "evidence.jsonl" in block
    assert "claims.jsonl" in block
    assert "[cite:ev_*]" in block


def test_rule_of_evidence_teaches_never_forces(monkeypatch):
    block = _block(monkeypatch, "1")
    assert "Any graph shape is fine" in block
    assert "no error code enforces a graph shape" in block


def test_rule_of_evidence_respects_kill_switch(monkeypatch):
    assert _block(monkeypatch, "0") == ""
