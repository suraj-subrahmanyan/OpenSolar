"""P7 R1 — retrieval-only closeout gate: source-pack integrity, not report shape.

Design: P7-RESEARCH-GROUNDING-DESIGN-DRAFT.md §3a/§6a. A retrieval node
produces a source pack (sources.jsonl + evidence.jsonl + extracts/), not
a report — running evaluate_final_closeout on it hard-fails on
research_eval_json_missing, which would make every governed retrieval
node untruthfully unbuildable (R0 survey finding).

Gate under test: research.evaluator.evaluate_retrieval_closeout.
Verdict model mirrors the §6a integrity split:
- pass          — every source row has an on-disk extract whose
                  content_sha256 verifies; every evidence row resolves to
                  a known source.
- hard_fail     — the UNTRUTHFUL class, zero tolerance: extract-less
                  sources, hash mismatches, missing/blank hashes,
                  evidence rows citing unknown sources.
- repairable_fail — retrieval produced nothing (missing/empty pack
                  files): retry-able, escalates through the normal
                  repair/needs_human_review machinery.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HARNESS = Path(__file__).resolve().parents[2]
_HARNESS_LIB = str(_HARNESS / "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research.evaluator import evaluate_retrieval_closeout  # noqa: E402
from research.sources.agent_web import write_source_pack  # noqa: E402
from research.sources.base import FetchResult  # noqa: E402


def _valid_pack(tmp_path: Path) -> Path:
    out = tmp_path / "pack"
    fetches = [
        FetchResult(
            source_id="web_a",
            connector_id="agent_web",
            title="Paper A",
            raw_text="solar retrieval provenance lands on disk with hashes",
            source_url="https://example.org/a",
            metadata={"source_type": "paper"},
        ),
        FetchResult(
            source_id="web_b",
            connector_id="agent_web",
            title="Post B",
            raw_text="agent mode retrieval goes wide across many angles",
            source_url="https://example.org/b",
        ),
    ]
    write_source_pack(out, fetches)
    return out


def _rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _rewrite(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_valid_pack_passes(tmp_path):
    pack = _valid_pack(tmp_path)
    result = evaluate_retrieval_closeout(pack)
    assert result["verdict"] == "pass"
    assert result["ok"] is True
    assert result["retrieval_only"] is True
    assert result["issues"] == []
    assert result["metrics"]["source_count"] == 2
    assert result["metrics"]["evidence_count"] == 2
    # persisted for the audit trail
    persisted = json.loads((pack / "retrieval_closeout.json").read_text(encoding="utf-8"))
    assert persisted["verdict"] == "pass"


def test_hash_mismatch_is_hard_fail(tmp_path):
    pack = _valid_pack(tmp_path)
    sources = _rows(pack / "sources.jsonl")
    extract = pack / sources[0]["extract_path"]
    extract.write_text(extract.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    result = evaluate_retrieval_closeout(pack)
    assert result["verdict"] == "hard_fail"
    assert result["ok"] is False
    assert any(i.startswith("source_extract_hash_mismatch") and "web_a" in i for i in result["issues"])


def test_missing_extract_is_hard_fail(tmp_path):
    pack = _valid_pack(tmp_path)
    sources = _rows(pack / "sources.jsonl")
    (pack / sources[1]["extract_path"]).unlink()
    result = evaluate_retrieval_closeout(pack)
    assert result["verdict"] == "hard_fail"
    assert any(i.startswith("source_extract_missing") and "web_b" in i for i in result["issues"])


def test_hashless_source_row_is_hard_fail(tmp_path):
    # The capsule invariant says every row carries content_sha256; a row
    # without one is unverifiable provenance — same zero-tolerance class.
    pack = _valid_pack(tmp_path)
    sources = _rows(pack / "sources.jsonl")
    del sources[0]["content_sha256"]
    _rewrite(pack / "sources.jsonl", sources)
    result = evaluate_retrieval_closeout(pack)
    assert result["verdict"] == "hard_fail"
    assert any(i.startswith("source_hash_missing") and "web_a" in i for i in result["issues"])


def test_evidence_citing_unknown_source_is_hard_fail(tmp_path):
    pack = _valid_pack(tmp_path)
    evidence = _rows(pack / "evidence.jsonl")
    evidence[0]["source_id"] = "web_phantom"
    _rewrite(pack / "evidence.jsonl", evidence)
    result = evaluate_retrieval_closeout(pack)
    assert result["verdict"] == "hard_fail"
    assert any(i.startswith("evidence_source_unknown") and "web_phantom" in i for i in result["issues"])


def test_empty_pack_is_repairable(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = evaluate_retrieval_closeout(empty)
    assert result["verdict"] == "repairable_fail"
    assert result["ok"] is False
    assert "sources_jsonl_missing" in result["issues"]
    assert "evidence_jsonl_missing" in result["issues"]


def test_empty_files_are_repairable(tmp_path):
    hollow = tmp_path / "hollow"
    hollow.mkdir()
    (hollow / "sources.jsonl").write_text("", encoding="utf-8")
    (hollow / "evidence.jsonl").write_text("", encoding="utf-8")
    result = evaluate_retrieval_closeout(hollow)
    assert result["verdict"] == "repairable_fail"
    assert "sources_jsonl_empty" in result["issues"]
    assert "evidence_jsonl_empty" in result["issues"]


def test_authority_audit_attaches_without_blocking(tmp_path):
    # Authority scoring is labels/warnings at R1 (audit_sources non-strict);
    # a low-authority pack still passes integrity.
    pack = _valid_pack(tmp_path)
    result = evaluate_retrieval_closeout(pack)
    assert result["verdict"] == "pass"
    assert "source_authority_average" in result["metrics"]
