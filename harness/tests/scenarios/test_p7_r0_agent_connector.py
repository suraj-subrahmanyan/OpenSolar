"""P7 R0 — agent-mode retrieval connector behind BaseSourceConnector.

Design: P7-RESEARCH-GROUNDING-DESIGN-DRAFT.md §3a (AGENT-ONLY retrieval,
owner decision 2026-07-12). The connector is the third implementation of
sources/base.py::BaseSourceConnector: it never fetches the web itself —
it dispatches a web-capable operator pane (the survey backends pane-packet
shape) and consumes the response files the agent lands on disk. Its
write_source_pack helper emits the closeout evaluator's wire format
(sources.jsonl + evidence.jsonl + extracts/) so retrieval output is
consumable by audit_sources and the research quality gate unchanged.

Deterministic only: every test stages or omits response files; no tmux,
no live agent, no network.
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

from research.evaluator import audit_sources  # noqa: E402
from research.hashing import content_hash  # noqa: E402
from research.sources.agent_web import (  # noqa: E402
    AgentRetrievalPendingError,
    AgentWebConnector,
    write_source_pack,
)
from research.sources.base import BaseSourceConnector, FetchResult  # noqa: E402


def _no_subprocess(monkeypatch):
    import research.sources.agent_web as aw

    def _forbidden(*args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("subprocess must not run in deterministic tests")

    monkeypatch.setattr(aw.subprocess, "run", _forbidden)


def test_connector_declares_base_contract():
    assert issubclass(AgentWebConnector, BaseSourceConnector)
    assert AgentWebConnector.connector_id == "agent_web"
    assert AgentWebConnector.source_tier == "external"


def test_search_returns_staged_response_without_dispatch(tmp_path, monkeypatch):
    _no_subprocess(monkeypatch)
    connector = AgentWebConnector(work_dir=tmp_path)
    query = "solar governance provenance"
    response = connector.search_response_path(query)
    response.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"title": "Paper A", "url": "https://example.org/a", "snippet": "alpha"},
        {"source_id": "web_custom", "title": "Post B", "url": "https://example.org/b"},
        {"title": "Doc C", "url": "https://example.org/c"},
    ]
    response.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    hits = connector.search(query, max_hits=2)
    assert len(hits) == 2
    assert all(h.connector_id == "agent_web" for h in hits)
    assert hits[0].title == "Paper A" and hits[0].url == "https://example.org/a"
    assert hits[1].source_id == "web_custom"
    assert hits[0].source_id.startswith("web_")


def test_search_without_response_writes_dispatch_and_raises_pending(tmp_path, monkeypatch):
    _no_subprocess(monkeypatch)
    connector = AgentWebConnector(work_dir=tmp_path)
    query = "battery prompt diversity"
    with pytest.raises(AgentRetrievalPendingError) as excinfo:
        connector.search(query)
    dispatch = Path(excinfo.value.dispatch_path)
    assert dispatch.exists()
    packet = dispatch.read_text(encoding="utf-8")
    assert query in packet
    assert excinfo.value.response_path in packet
    assert "Do not invent" in packet
    assert excinfo.value.submitted is False


def test_fetch_returns_staged_document(tmp_path, monkeypatch):
    _no_subprocess(monkeypatch)
    connector = AgentWebConnector(work_dir=tmp_path)
    source_id = "web_deadbeef00000001"
    response = connector.fetch_response_path(source_id)
    response.parent.mkdir(parents=True, exist_ok=True)
    response.write_text(
        json.dumps({
            "source_id": source_id,
            "title": "Paper A",
            "url": "https://example.org/a",
            "raw_text": "governed retrieval writes provenance to disk",
        }),
        encoding="utf-8",
    )
    doc = connector.fetch(source_id)
    assert doc.fetch_status == "fetched"
    assert doc.raw_text.startswith("governed retrieval")
    assert doc.content_length == len(doc.raw_text)
    assert doc.source_url == "https://example.org/a"


def test_fetch_without_response_raises_pending(tmp_path, monkeypatch):
    _no_subprocess(monkeypatch)
    connector = AgentWebConnector(work_dir=tmp_path)
    with pytest.raises(AgentRetrievalPendingError) as excinfo:
        connector.fetch("web_0000000000000000")
    assert Path(excinfo.value.dispatch_path).exists()


def test_write_source_pack_emits_evaluator_wire_format(tmp_path):
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
        FetchResult(
            source_id="web_bad",
            connector_id="agent_web",
            title="Broken",
            raw_text="",
            fetch_status="failed",
            fetch_error="timeout",
        ),
    ]
    out = tmp_path / "pack"
    summary = write_source_pack(out, fetches)
    assert summary["source_count"] == 2
    assert summary["evidence_count"] == 2
    assert summary["skipped"] == 1

    sources = [json.loads(l) for l in (out / "sources.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(sources) == 2
    for row in sources:
        for field in ("url", "title", "retrieved_at", "content_sha256", "extract_path", "provider"):
            assert row.get(field), f"sources.jsonl row missing {field}"
        extract = out / row["extract_path"]
        assert extract.is_file()
        assert content_hash(extract.read_text(encoding="utf-8")) == row["content_sha256"]
    assert sources[0]["source_type"] == "paper"
    assert sources[1]["source_type"] == "web"

    evidence = [json.loads(l) for l in (out / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(evidence) == 2
    for row in evidence:
        assert row["id"].startswith("ev_")
        assert row["source_id"] in {"web_a", "web_b"}
        assert row["content"]

    audit = audit_sources(out)
    assert audit["source_count"] == 2
    assert audit["source_type_counts"] == {"paper": 1, "web": 1}


def test_send_guard_forbids_main_pane(tmp_path, monkeypatch):
    import research.sources.agent_web as aw

    def _fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = "solar-harness\tmain"
            stderr = ""
        assert cmd[:2] == ["tmux", "display-message"]
        return R()

    monkeypatch.setattr(aw.subprocess, "run", _fake_run)
    monkeypatch.delenv("SOLAR_ALLOW_MAIN_PANE_RETRIEVAL_SEND", raising=False)
    connector = AgentWebConnector(work_dir=tmp_path, pane_target="solar-harness:0.0", send=True)
    with pytest.raises(aw.AgentRetrievalDispatchError, match="pane_target_role_forbidden"):
        connector.search("guarded query")
