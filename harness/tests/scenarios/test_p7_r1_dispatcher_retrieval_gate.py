"""P7 R1 — dispatcher routes retrieval-only nodes to the retrieval closeout.

R0 survey finding: a retrieval node declaring sources.jsonl/evidence.jsonl
trips DEEPRESEARCH_GATE_ARTIFACT_RE, and the quality-gate auto-run then
demands a research_eval json the node was never supposed to produce —
present=False → review blocks with missing_deepresearch_quality_gate.
Every governed retrieval node would be untruthfully unbuildable.

Fix under test: _deepresearch_quality_gate_auto_run detects a node whose
DECLARED artifacts are retrieval-only (source-pack files, no report/claims
artifacts) and runs research.evaluator.evaluate_retrieval_closeout on the
declared pack instead of the final-report closeout. Claim-producing nodes
keep the report path unchanged (declaring final.md and not writing it
still fails). Detection keys off declarations, so a node cannot dodge the
report gate by writing files it never declared.
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

import graph_node_dispatcher as gnd  # noqa: E402
from research.sources.agent_web import write_source_pack  # noqa: E402
from research.sources.base import FetchResult  # noqa: E402

SID = "sprint-p7-r1-test"


def _retrieval_node() -> dict:
    return {
        "id": "s2",
        "goal": "retrieve sources for the research question",
        "write_scope": [
            "workspace/research/sources.jsonl",
            "workspace/research/evidence.jsonl",
            "workspace/research/extracts",
        ],
        "artifacts": {
            "sources": "workspace/research/sources.jsonl",
            "evidence": "workspace/research/evidence.jsonl",
        },
    }


def _claim_node() -> dict:
    return {
        "id": "s3",
        "goal": "write the grounded report",
        "write_scope": ["workspace/research/final.md", "workspace/research/claims.jsonl"],
        "artifacts": {"final_md": "workspace/research/final.md"},
    }


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    sprints = tmp_path / "sprints"
    (sprints / SID / "workdir").mkdir(parents=True)
    monkeypatch.setattr(gnd, "SPRINTS_DIR", sprints)
    eval_json = sprints / f"{SID}.s2-eval.json"
    eval_json.write_text(json.dumps({"node_id": "s2", "verdict": "PASS"}), encoding="utf-8")
    return sprints, eval_json


def _stage_pack(sprints: Path) -> Path:
    pack = sprints / SID / "workdir" / "workspace" / "research"
    write_source_pack(pack, [
        FetchResult(
            source_id="web_a",
            connector_id="agent_web",
            title="Paper A",
            raw_text="solar retrieval provenance lands on disk with hashes",
            source_url="https://example.org/a",
            metadata={"source_type": "paper"},
        ),
    ])
    return pack


def test_detection_is_declaration_keyed():
    assert gnd._node_declares_retrieval_only(_retrieval_node()) is True
    assert gnd._node_declares_retrieval_only(_claim_node()) is False
    mixed = _retrieval_node()
    mixed["artifacts"]["claims"] = "workspace/research/claims.jsonl"
    assert gnd._node_declares_retrieval_only(mixed) is False
    # the retrieval node still requires the research gate at all (pin)
    assert gnd._node_requires_deepresearch_quality_gate(_retrieval_node()) is True


def test_auto_run_passes_valid_retrieval_pack(sandbox):
    sprints, eval_json = sandbox
    _stage_pack(sprints)
    res = gnd._deepresearch_quality_gate_auto_run(SID, _retrieval_node(), eval_json)
    assert res["present"] is True
    assert res["ok"] is True
    assert res["auto_run"] is True
    assert res["gate"]["retrieval_only"] is True
    assert res["gate"]["closeout_verdict"] == "pass"


def test_auto_run_blocks_tampered_retrieval_pack(sandbox):
    sprints, eval_json = sandbox
    pack = _stage_pack(sprints)
    row = json.loads((pack / "sources.jsonl").read_text(encoding="utf-8").splitlines()[0])
    extract = pack / row["extract_path"]
    extract.write_text(extract.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    res = gnd._deepresearch_quality_gate_auto_run(SID, _retrieval_node(), eval_json)
    assert res["present"] is True
    assert res["ok"] is False
    assert res["gate"]["closeout_verdict"] == "hard_fail"
    assert any(e.startswith("source_extract_hash_mismatch") for e in res["gate"]["errors"])


def test_auto_run_reports_missing_pack_as_repairable(sandbox):
    sprints, eval_json = sandbox
    res = gnd._deepresearch_quality_gate_auto_run(SID, _retrieval_node(), eval_json)
    assert res["present"] is True
    assert res["ok"] is False
    assert res["gate"]["closeout_verdict"] == "repairable_fail"
    assert "sources_jsonl_missing" in res["gate"]["errors"]


def test_claim_node_keeps_report_path(sandbox):
    sprints, eval_json = sandbox
    res = gnd._deepresearch_quality_gate_auto_run(SID, _claim_node(), eval_json)
    assert res["present"] is False
    assert res["ok"] is False
    assert any(
        str(e).startswith("research_eval_artifact_missing") for e in res["gate"]["errors"]
    )


def test_eval_instruction_diverges_for_retrieval_only(sandbox):
    _, eval_json = sandbox
    retrieval_text = gnd._deepresearch_quality_gate_eval_instruction(_retrieval_node(), eval_json)
    assert "retrieval-only" in retrieval_text
    assert "eval-artifacts" in retrieval_text  # named so the evaluator knows NOT to run it
    assert "不要运行" in retrieval_text
    claim_text = gnd._deepresearch_quality_gate_eval_instruction(_claim_node(), eval_json)
    assert "必须先运行 deterministic artifact gate" in claim_text
