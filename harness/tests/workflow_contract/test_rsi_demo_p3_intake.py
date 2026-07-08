#!/usr/bin/env python3
"""P3 pre-live blocker replays — rsi_demo must be intakeable and its gate
commands fully specified (found by the P3 deterministic rehearsal, 2026-07-08).

Blocker 1: contracted intake of research.deepdive.rsi_demo failed closed with
UNRESOLVED_PLACEHOLDERS ['resolved_root'] — the contract's validator_command
carries `<resolved_root>` and nothing supplied it. Author intent (readable
from `validate_rsi_demo_report.py`, whose ROOT constant is the artifact dir
basename and which checks `rsi-deep-research-report/` under --workspace):
resolved_root = the RESOLVED WORKSPACE dir that CONTAINS the canonical
artifact dir, i.e. the canonical root's parent. instantiate() now derives it
from artifact_roots.canonical and adds it to the substitution table.

Blocker 2 (contract v1.0 -> v1.1): the D2 gate command named a flag that does
not exist (`research eval-artifacts --sources` — argparse would exit 2), D3's
eval-artifacts had no --eval-json (a REQUIRED flag), and D6's stage command
diverged from the top-level validator_command (no --workspace). v1.1 pins:
D2 -> `research source-audit --output-dir ... --json`, D3 -> eval-artifacts
with an explicit --eval-json under the canonical root, D6 -> the
validator_command form. The executor that RUNS these gates is a separate
seam; these tests pin the contract/instantiation layer only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_HARNESS = Path(__file__).resolve().parents[2]
_HARNESS_LIB = str(_HARNESS / "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

import workflow_contract as wc  # noqa: E402
import workflow_intake as wi  # noqa: E402

WORKFLOWS_DIR = _HARNESS / "config" / "workflows"
WF = "research.deepdive.rsi_demo"


@pytest.fixture()
def contract():
    found = wc.find_contract(WF, WORKFLOWS_DIR)
    assert found is not None
    return found


def test_contracted_intake_succeeds(tmp_path):
    """The rehearsal's exact red: UNRESOLVED_PLACEHOLDERS ['resolved_root']."""
    res = wi.create_contract_sprint(
        workflow_id=WF,
        request="Bounded RSI demo: reliability of LLM-based code review",
        workspace_root=str(tmp_path / "ws"),
        sprints_dir=tmp_path / "sprints",
        workflows_dir=WORKFLOWS_DIR,
    )
    sid = str(res.get("sprint_id") or res.get("sid") or "")
    assert sid, res
    graph_path = tmp_path / "sprints" / f"{sid}.task_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    assert graph.get("workflow_contract_id") == WF
    assert [n["id"] for n in graph["nodes"]] == ["D1", "D2", "D3", "D4", "D5", "D6"]
    leftover = sorted(set(__import__("re").findall(r"<([a-z_][a-z0-9_]*)>", json.dumps(graph))))
    assert leftover == [], f"unresolved placeholders in instantiated graph: {leftover}"


def test_resolved_root_is_canonical_parent(contract):
    graph = wc.instantiate(contract, {"sprint_id": "p3-sub-probe"})
    # canonical: workspace/rsi-deep-research-report/ -> resolved_root: workspace
    cmd = str(graph.get("validator_command") or "")
    assert "<resolved_root>" not in cmd
    assert "--workspace workspace" in cmd, cmd


def test_gate_commands_are_executable_shapes(contract):
    """v1.1 contract: every deterministic gate command must name real flags."""
    graph = wc.instantiate(contract, {"sprint_id": "p3-cmd-probe"})
    gates = {n["id"]: (n.get("evaluator_gate") or {}) for n in graph["nodes"]}
    d2 = str(gates["D2"].get("command") or "")
    assert d2.startswith("research source-audit "), d2
    assert "--output-dir workspace/rsi-deep-research-report" in d2, d2
    assert "--sources" not in d2  # the flag that never existed
    d3 = str(gates["D3"].get("command") or "")
    assert d3.startswith("research eval-artifacts "), d3
    assert "--eval-json workspace/rsi-deep-research-report/research_eval.json" in d3, d3
    d6 = str(gates["D6"].get("command") or "")
    assert d6 == str(graph.get("validator_command") or ""), (
        "D6 stage gate must match the contract-level validator_command"
    )
    for nid in ("D2", "D3", "D6"):
        assert "<" not in str(gates[nid].get("command") or "")


def test_gate_kinds_unchanged_by_amendment(contract):
    kinds = {s["id"]: (s.get("evaluator_gate") or {}).get("kind", "none") for s in contract["stages"]}
    assert kinds == {
        "D1": "none",
        "D2": "deterministic_command",
        "D3": "deterministic_command",
        "D4": "none",
        "D5": "llm_eval",
        "D6": "deterministic_command",
    }


def test_forbidden_block_survives_amendment(contract):
    forbidden = contract.get("forbidden") or {}
    assert "cap.requirement-compiler-implementation" in (forbidden.get("capsules") or [])


def test_cli_smoke_goldens_unaffected_by_resolved_root():
    """resolved_root is derived for every contract; the P2 contracts must
    instantiate byte-identically (they never reference the token)."""
    goldens = Path(__file__).resolve().parent / "goldens"
    inputs = {"sid": "golden-sid", "sprint_id": "sprint-golden", "tool": "wordfreq"}
    for wf_id in ("code.cli_smoke", "code.cli_smoke_anthropic"):
        contract = wc.find_contract(wf_id, WORKFLOWS_DIR)
        produced = wc.canonical_graph_json(wc.instantiate(contract, dict(inputs)))
        golden = (goldens / f"{wf_id}.instantiated.golden.json").read_text(encoding="utf-8")
        assert produced == golden, f"{wf_id} drifted — resolved_root must be inert for P2 contracts"
