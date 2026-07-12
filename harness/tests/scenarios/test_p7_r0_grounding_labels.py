"""P7 R0 — grounding severity remap: labels PASS, integrity blocks.

Design: P7-RESEARCH-GROUNDING-DESIGN-DRAFT.md §6a (owner decision 2:
grounding strictness = PASS with a visible label, never ratio-block;
integrity violations always block). The token-overlap check is a Jaccard
heuristic that legitimately misses paraphrase — treating every miss as an
error failed honest reports and taught agents to quote instead of
synthesize.

Remap under test, in research.evaluator._citation_grounding_metrics:
- citation_context_not_grounded moves from error to the three label bands
  computed from the EXISTING grounded/ungrounded citation counters
  (>=0.90 grounded / >=0.60 partially_grounded / else weakly_grounded —
  PROVISIONAL until R6 calibration).
- Integrity failures stay hard errors: dangling cite ids
  (final_md_missing_cited_evidence) and extract-less evidence rows
  (evidence_span_text_missing) are the UNTRUTHFUL class, zero tolerance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HARNESS = Path(__file__).resolve().parents[2]
_HARNESS_LIB = str(_HARNESS / "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research import evaluator as ev  # noqa: E402


def _run(tmp_path, evidence_rows, final_lines):
    (tmp_path / "evidence.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in evidence_rows), encoding="utf-8"
    )
    return ev._citation_grounding_metrics("\n".join(final_lines), tmp_path)


def _grounded_pair(idx: int):
    ev_id = f"ev_g{idx}"
    words = f"solar governance retrieval provenance manifest{idx}"
    line = f"The solar governance retrieval layer writes provenance [cite:{ev_id}]"
    return {"id": ev_id, "content": words}, line


def _ungrounded_pair(idx: int):
    ev_id = f"ev_u{idx}"
    return (
        {"id": ev_id, "content": f"quantum flux capacitor axis rotation{idx}"},
        f"Completely unrelated narrative sentence here [cite:{ev_id}]",
    )


def test_overlap_failures_become_label_not_error(tmp_path):
    row, line = _ungrounded_pair(0)
    metrics, errors, warnings = _run(tmp_path, [row], [line])
    assert not any(e.startswith("final_md_ungrounded_evidence_citations") for e in errors)
    assert metrics["final_md_grounding_label"] == "weakly_grounded"
    assert metrics["final_md_grounding_ratio"] == 0.0
    assert any(w.startswith("final_md_grounding_label:weakly_grounded") for w in warnings)


def test_fully_grounded_report_labels_grounded(tmp_path):
    rows_lines = [_grounded_pair(i) for i in range(2)]
    metrics, errors, warnings = _run(
        tmp_path, [r for r, _ in rows_lines], [l for _, l in rows_lines]
    )
    assert errors == []
    assert metrics["final_md_grounding_label"] == "grounded"
    assert metrics["final_md_grounding_ratio"] == 1.0
    assert not any(w.startswith("final_md_grounding_label") for w in warnings)


def test_band_grounded_at_point_nine(tmp_path):
    pairs = [_grounded_pair(i) for i in range(9)] + [_ungrounded_pair(0)]
    metrics, errors, _ = _run(tmp_path, [r for r, _ in pairs], [l for _, l in pairs])
    assert not any(e.startswith("final_md_ungrounded_evidence_citations") for e in errors)
    assert metrics["final_md_grounding_ratio"] == 0.9
    assert metrics["final_md_grounding_label"] == "grounded"


def test_band_partially_grounded(tmp_path):
    pairs = [_grounded_pair(i) for i in range(7)] + [_ungrounded_pair(i) for i in range(3)]
    metrics, errors, _ = _run(tmp_path, [r for r, _ in pairs], [l for _, l in pairs])
    assert not any(e.startswith("final_md_ungrounded_evidence_citations") for e in errors)
    assert metrics["final_md_grounding_ratio"] == 0.7
    assert metrics["final_md_grounding_label"] == "partially_grounded"


def test_dangling_citation_stays_hard_error(tmp_path):
    row, line = _grounded_pair(0)
    metrics, errors, _ = _run(
        tmp_path, [row], [line, "Phantom claim with no evidence row [cite:ev_phantom]"]
    )
    assert any(e.startswith("final_md_missing_cited_evidence:ev_phantom") for e in errors)


def test_extractless_evidence_stays_error(tmp_path):
    # A cited evidence row with no span text is the extract-less integrity
    # class (§6a always-block), NOT a paraphrase miss — it must stay an error.
    row, line = _grounded_pair(0)
    empty = {"id": "ev_empty", "content": ""}
    empty_line = "This cites an evidence row that has no text [cite:ev_empty]"
    metrics, errors, _ = _run(tmp_path, [row, empty], [line, empty_line])
    assert any(
        e.startswith("final_md_ungrounded_evidence_citations") and "ev_empty" in e
        for e in errors
    )
