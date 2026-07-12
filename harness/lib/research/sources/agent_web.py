"""Agent-mode web retrieval connector for DeepResearch.

Third BaseSourceConnector implementation (after internal_mirage and the
registry-backed providers). AGENT-ONLY retrieval (owner decision
2026-07-12): this connector never touches the network itself — it writes
a dispatch packet for a web-capable operator pane (the survey backends
pane-packet shape), optionally sends it via tmux, and consumes the
response files the agent lands on disk. No HTTP imports, per base.py.

Wire format: write_source_pack() emits sources.jsonl + evidence.jsonl +
extracts/ — the exact files research.evaluator.audit_sources and the
artifact-triggered research quality gate already consume.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

from research.hashing import content_hash
from research.ids import evidence_id
from .base import BaseSourceConnector, FetchResult, SearchResult

_KEY_HEX_LEN = 16
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class AgentRetrievalPendingError(RuntimeError):
    """A dispatch packet exists but the agent has not written its response yet."""

    def __init__(self, response_path: str, dispatch_path: str, pane_target: str = "", submitted: bool = False) -> None:
        super().__init__(f"agent_retrieval_response_missing:{response_path}")
        self.response_path = response_path
        self.dispatch_path = dispatch_path
        self.pane_target = pane_target
        self.submitted = submitted


class AgentRetrievalDispatchError(RuntimeError):
    """Pane dispatch failed (missing/forbidden pane target, tmux error)."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"agent_retrieval_dispatch_failed:{reason}")
        self.reason = reason


def _key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_KEY_HEX_LEN]


def _safe_name(source_id: str) -> str:
    return _SAFE_NAME_RE.sub("_", source_id) or "source"


def _utc_now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class AgentWebConnector(BaseSourceConnector):
    """Dispatches a web-capable operator to search/fetch and reads its responses."""

    connector_id = "agent_web"
    connector_type = "agent_web"
    source_tier = "external"
    display_name = "Agent Web Retrieval"

    def __init__(
        self,
        work_dir: Path | str,
        pane_target: str = "",
        send: bool = False,
        timeout_seconds: int = 120,
    ) -> None:
        self.work_dir = Path(work_dir).expanduser()
        self.pane_target = pane_target
        self.send = send
        self.timeout_seconds = timeout_seconds

    # -- response/dispatch paths (stable per query/source, resumable) -------

    def search_response_path(self, query: str) -> Path:
        return self.work_dir / "responses" / f"search-{_key(query)}.jsonl"

    def fetch_response_path(self, source_id: str) -> Path:
        return self.work_dir / "responses" / f"fetch-{_key(source_id)}.json"

    def _dispatch_path(self, response: Path) -> Path:
        return self.work_dir / "dispatch" / f"{response.stem}.dispatch.md"

    # -- BaseSourceConnector contract ---------------------------------------

    def search(self, query: str, max_hits: int = 10, **kwargs: Any) -> list[SearchResult]:
        response = self.search_response_path(query)
        if response.exists() and response.read_text(encoding="utf-8").strip():
            return self._parse_search_response(response, max_hits)
        dispatch = self._write_search_dispatch(query, max_hits, response)
        submitted = self._maybe_send(dispatch, response)
        raise AgentRetrievalPendingError(str(response), str(dispatch), self.pane_target, submitted)

    def fetch(self, source_id: str) -> FetchResult:
        response = self.fetch_response_path(source_id)
        if response.exists() and response.read_text(encoding="utf-8").strip():
            return self._parse_fetch_response(source_id, response)
        dispatch = self._write_fetch_dispatch(source_id, response)
        submitted = self._maybe_send(dispatch, response)
        raise AgentRetrievalPendingError(str(response), str(dispatch), self.pane_target, submitted)

    # -- response parsing ----------------------------------------------------

    def _parse_search_response(self, response: Path, max_hits: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        for line in response.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "")
            source_id = str(row.get("source_id") or "") or f"web_{_key(url or str(row.get('title') or ''))}"
            results.append(SearchResult(
                source_id=source_id,
                connector_id=self.connector_id,
                title=str(row.get("title") or source_id),
                url=url or None,
                snippet=str(row.get("snippet") or "")[:500] or None,
                metadata=row,
                score=float(row.get("score") or 0.0),
            ))
            if len(results) >= max_hits:
                break
        return results

    def _parse_fetch_response(self, source_id: str, response: Path) -> FetchResult:
        try:
            row = json.loads(response.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return FetchResult(
                source_id=source_id,
                connector_id=self.connector_id,
                title="",
                raw_text="",
                fetch_status="failed",
                fetch_error=f"invalid_fetch_response_json:{exc}",
            )
        row = row if isinstance(row, dict) else {}
        raw_text = str(row.get("raw_text") or row.get("content") or "")
        if not raw_text.strip():
            return FetchResult(
                source_id=source_id,
                connector_id=self.connector_id,
                title=str(row.get("title") or ""),
                raw_text="",
                fetch_status="failed",
                fetch_error="fetch_response_empty_raw_text",
            )
        return FetchResult(
            source_id=str(row.get("source_id") or source_id),
            connector_id=self.connector_id,
            title=str(row.get("title") or source_id),
            raw_text=raw_text,
            source_url=str(row.get("url") or "") or None,
            metadata=row,
        )

    # -- dispatch packets ------------------------------------------------------

    def _write_search_dispatch(self, query: str, max_hits: int, response: Path) -> Path:
        dispatch = self._dispatch_path(response)
        dispatch.parent.mkdir(parents=True, exist_ok=True)
        dispatch.write_text("\n".join([
            "# Agent Web Retrieval Dispatch: search",
            "",
            "## Research Query",
            "",
            query,
            "",
            "## Response Path",
            "",
            str(response),
            "",
            "## Rules",
            "",
            "- Search WIDE: many angles, many providers, primary sources first.",
            f"- Write up to {max_hits} hits as JSONL to the response path, one",
            "  object per line: {\"title\", \"url\", \"snippet\", \"source_type\"}.",
            "- Every hit must be a real page you actually saw.",
            "- Do not invent sources, URLs, papers, metrics, or benchmark results.",
        ]) + "\n", encoding="utf-8")
        return dispatch

    def _write_fetch_dispatch(self, source_id: str, response: Path) -> Path:
        dispatch = self._dispatch_path(response)
        dispatch.parent.mkdir(parents=True, exist_ok=True)
        dispatch.write_text("\n".join([
            "# Agent Web Retrieval Dispatch: fetch",
            "",
            "## Source",
            "",
            source_id,
            "",
            "## Response Path",
            "",
            str(response),
            "",
            "## Rules",
            "",
            "- Fetch the source content and write ONE JSON object to the response",
            "  path: {\"source_id\", \"title\", \"url\", \"raw_text\"}.",
            "- raw_text must be the fetched content, never your own prose.",
            "- Do not invent content; if the fetch fails, write nothing.",
        ]) + "\n", encoding="utf-8")
        return dispatch

    # -- pane send (survey backends idiom) -------------------------------------

    def _maybe_send(self, dispatch: Path, response: Path) -> bool:
        if not self.send:
            return False
        if not self.pane_target.strip():
            raise AgentRetrievalDispatchError("pane_target_missing")
        self._guard_pane_target()
        prompt = f"读取并执行 {dispatch}; 完成后只把检索结果写入 {response}"
        try:
            result = subprocess.run(
                ["tmux", "send-keys", "-t", self.pane_target, prompt, "Enter"],
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentRetrievalDispatchError(f"pane_send_timeout:{self.timeout_seconds}") from exc
        if result.returncode != 0:
            stderr = (result.stderr or "").strip().replace("\n", " ")[:500]
            raise AgentRetrievalDispatchError(f"pane_send_exit_{result.returncode}:{stderr}")
        return True

    def _guard_pane_target(self) -> None:
        if os.environ.get("SOLAR_ALLOW_MAIN_PANE_RETRIEVAL_SEND") == "1":
            return
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "-t", self.pane_target, "#{session_name}\t#{pane_title}"],
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentRetrievalDispatchError(f"pane_target_probe_timeout:{self.timeout_seconds}") from exc
        if result.returncode != 0:
            stderr = (result.stderr or "").strip().replace("\n", " ")[:500]
            raise AgentRetrievalDispatchError(f"pane_target_probe_exit_{result.returncode}:{stderr}")
        raw = (result.stdout or "").strip()
        session, _, title = raw.partition("\t")
        if session == "solar-harness" and not re.search(r"\b(lab-builder|Builder [1-4])\b", title.strip()):
            raise AgentRetrievalDispatchError(
                f"pane_target_role_forbidden:{self.pane_target}:"
                "retrieval pane-send must use lab-builder panes; "
                "set SOLAR_ALLOW_MAIN_PANE_RETRIEVAL_SEND=1 only for explicit manual override"
            )


def write_source_pack(
    output_dir: Path | str,
    fetches: list[FetchResult],
    provider: Optional[str] = None,
) -> dict[str, Any]:
    """Write fetched documents as the evaluator wire format.

    Emits sources.jsonl (one provenance row per fetched source),
    evidence.jsonl (one full-document evidence span per source; span-level
    extraction is the synthesis rung's business), and extracts/<id>.md
    (the fetched content itself). Failed or empty fetches are skipped and
    counted — never fabricated.
    """
    root = Path(output_dir).expanduser()
    extracts_dir = root / "extracts"
    extracts_dir.mkdir(parents=True, exist_ok=True)
    retrieved_at = _utc_now()

    source_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    skipped = 0
    for doc in fetches:
        if doc.fetch_status != "fetched" or not doc.raw_text.strip():
            skipped += 1
            continue
        digest = content_hash(doc.raw_text)
        extract_path = extracts_dir / f"{_safe_name(doc.source_id)}.md"
        extract_path.write_text(doc.raw_text, encoding="utf-8")
        source_rows.append({
            "id": doc.source_id,
            "source_id": doc.source_id,
            "source_type": str((doc.metadata or {}).get("source_type") or "web"),
            "title": doc.title,
            "url": doc.source_url or "",
            "retrieved_at": retrieved_at,
            "content_sha256": digest,
            "extract_path": str(extract_path.relative_to(root)),
            "provider": provider or doc.connector_id,
        })
        ev_id = evidence_id(doc.source_id, 0, len(doc.raw_text), digest)
        evidence_rows.append({
            "id": ev_id,
            "evidence_id": ev_id,
            "source_id": doc.source_id,
            "content": doc.raw_text,
            "content_hash": digest,
            "span_start": 0,
            "span_end": len(doc.raw_text),
        })

    sources_path = root / "sources.jsonl"
    evidence_path = root / "evidence.jsonl"
    sources_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in source_rows), encoding="utf-8")
    evidence_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in evidence_rows), encoding="utf-8")
    return {
        "source_count": len(source_rows),
        "evidence_count": len(evidence_rows),
        "skipped": skipped,
        "sources_path": str(sources_path),
        "evidence_path": str(evidence_path),
        "extracts_dir": str(extracts_dir),
    }
