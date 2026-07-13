"""P7 R1 hardening — the retrieval gate must judge the sprint's OWN pack.

Deep-review finding (2026-07-13, HIGH): _retrieval_pack_dir accepted
absolute (and traversing) artifact declarations verbatim, so a retrieval
node could declare artifacts pointing at a pre-staged pack OUTSIDE its
sprint — with an empty write_scope the proof gate demands nothing and
the quality gate passes on work the node never did. The §6a truthfulness
model requires gates to be satisfied by the node's own outputs, so pack
resolution must be contained to the sprint's own bases (workdir, sprint
dir, the eval json's directory).
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

SID = "sprint-p7-r1-containment"


def _pack(where: Path) -> Path:
    write_source_pack(where, [
        FetchResult(
            source_id="web_a",
            connector_id="agent_web",
            title="Paper A",
            raw_text="solar retrieval provenance lands on disk with hashes",
            source_url="https://example.org/a",
        ),
    ])
    return where


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    sprints = tmp_path / "sprints"
    (sprints / SID / "workdir").mkdir(parents=True)
    monkeypatch.setattr(gnd, "SPRINTS_DIR", sprints)
    eval_json = sprints / f"{SID}.s2-eval.json"
    eval_json.write_text(json.dumps({"node_id": "s2", "verdict": "PASS"}), encoding="utf-8")
    return tmp_path, sprints, eval_json


def test_absolute_outside_pack_is_not_used(sandbox):
    outside_root, sprints, eval_json = sandbox
    foreign = _pack(outside_root / "prestaged")
    node = {
        "id": "s2",
        "goal": "retrieve sources",
        "write_scope": [],
        "artifacts": {
            "sources": str(foreign / "sources.jsonl"),
            "evidence": str(foreign / "evidence.jsonl"),
        },
    }
    res = gnd._deepresearch_quality_gate_auto_run(SID, node, eval_json)
    assert res["ok"] is False, "gate must not pass on a pack outside the sprint"
    assert res["gate"]["closeout_verdict"] == "repairable_fail"
    assert "sources_jsonl_missing" in res["gate"]["errors"]


def test_traversal_outside_pack_is_not_used(sandbox):
    outside_root, sprints, eval_json = sandbox
    _pack(outside_root / "prestaged2")
    node = {
        "id": "s2",
        "goal": "retrieve sources",
        "write_scope": ["../../../prestaged2/sources.jsonl", "../../../prestaged2/evidence.jsonl"],
        "artifacts": {},
    }
    res = gnd._deepresearch_quality_gate_auto_run(SID, node, eval_json)
    assert res["ok"] is False
    assert res["gate"]["closeout_verdict"] == "repairable_fail"


def test_sprint_workdir_pack_still_resolves(sandbox):
    _, sprints, eval_json = sandbox
    _pack(sprints / SID / "workdir" / "workspace" / "research")
    node = {
        "id": "s2",
        "goal": "retrieve sources",
        "write_scope": ["workspace/research/sources.jsonl", "workspace/research/evidence.jsonl"],
        "artifacts": {"sources": "workspace/research/sources.jsonl"},
    }
    res = gnd._deepresearch_quality_gate_auto_run(SID, node, eval_json)
    assert res["ok"] is True
    assert res["gate"]["closeout_verdict"] == "pass"
