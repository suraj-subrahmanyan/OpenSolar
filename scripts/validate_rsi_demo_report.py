#!/usr/bin/env python3
"""Copied-workspace validator for the RSI deep-research demo report.

Runs with cwd == the copied sandbox workspace (the live wrapper copies the
workspace into a temp dir and runs this via shell=True). Enforces the artifact
CONTENT contract for rsi-deep-research-report/. Route-proof ok=true and provider
policy live outside the workspace (harness sprints dir) and are enforced by the
wrapper's artifact-validation route-proof gate + the demo driver, not here.

Exit 0 == all content checks pass. Non-zero == a specific, classifiable failure.
"""
import json
import os
import pathlib
import re

ROOT = pathlib.Path("rsi-deep-research-report")
MIN_SOURCES = int(os.environ.get("SOLAR_DEMO_MIN_SOURCES", "5"))
MIN_CLAIMS = int(os.environ.get("SOLAR_DEMO_MIN_CLAIMS", "10"))

REQUIRED = [
    "report.html",
    "report.md",
    "sources.json",
    "claims.json",
    "evaluation-checklist.md",
]

# Unfinished-stub markers that must not appear in a finished demo report.
# NOTE: the bare word "placeholder" is intentionally NOT flagged -- a finished
# report can legitimately say "No placeholder text remains" / "placeholder check
# passed". Only stub TOKENS (bracketed/delimited placeholders, insert-here stubs,
# TODO/FIXME/etc.) count as unfinished content.
PLACEHOLDER_PATTERNS = [
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bTBD\b",
    r"\bXXX\b",
    r"lorem ipsum",
    # Bracketed/delimited placeholder tokens: [placeholder] <placeholder> {{placeholder}} [PLACEHOLDER]
    r"[\[<{]{1,2}\s*placeholder[^\]}>\n]*[\]}>]{1,2}",
    r"\bINSERT_HERE\b",
    r"\breplace me\b",
    r"\binsert\b[^.\n<>]{0,24}\bhere\b",   # "insert your text here"
    r"<\s*insert\b[^>\n]*>",               # "<insert ...>"
]


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    raise SystemExit(f"DEMO_VALIDATION_FAIL: {msg}")


def _as_list(data, *keys):
    """Accept a bare JSON list, or a dict wrapping the list under one of keys."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in keys:
            if isinstance(data.get(k), list):
                return data[k]
    return None


def main() -> None:
    # 1. required files exist
    missing = [p for p in REQUIRED if not (ROOT / p).is_file()]
    if missing:
        fail(f"ARTIFACT_MISSING: {missing}")

    # 2. report.html is real HTML
    html = (ROOT / "report.html").read_text(encoding="utf-8", errors="replace")
    if "<html" not in html.lower():
        fail("HTML_INVALID: report.html does not contain '<html'")
    if len(html.strip()) < 500:
        fail("HTML_INVALID: report.html is implausibly small (<500 chars)")

    md = (ROOT / "report.md").read_text(encoding="utf-8", errors="replace")
    if len(md.strip()) < 300:
        fail("REPORT_MD_TOO_SMALL: report.md is implausibly small (<300 chars)")

    # 3. JSON files parse
    parsed = {}
    for name in ["sources.json", "claims.json"]:
        try:
            parsed[name] = json.loads((ROOT / name).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            fail(f"JSON_INVALID: {name}: {type(exc).__name__}: {exc}")

    sources = _as_list(parsed["sources.json"], "sources")
    claims = _as_list(parsed["claims.json"], "claims")
    if sources is None:
        fail("SCHEMA: sources.json is not a list (nor {sources:[...]})")
    if claims is None:
        fail("SCHEMA: claims.json is not a list (nor {claims:[...]})")

    # 5/6. counts
    if len(sources) < MIN_SOURCES:
        fail(f"TOO_FEW_SOURCES: {len(sources)} < {MIN_SOURCES}")
    if len(claims) < MIN_CLAIMS:
        fail(f"TOO_FEW_CLAIMS: {len(claims)} < {MIN_CLAIMS}")

    # source ids
    source_ids = {
        str(s.get("id")) for s in sources if isinstance(s, dict) and s.get("id") is not None
    }
    if not source_ids:
        fail("SCHEMA: no source objects with an 'id' field")

    # 4. every claim links to a valid source_id (+ has non-empty claim text)
    bad_link = []
    empty_text = []
    for c in claims:
        if not isinstance(c, dict):
            bad_link.append(c)
            continue
        if str(c.get("source_id")) not in source_ids:
            bad_link.append({k: c.get(k) for k in ("claim_id", "source_id")})
        if not str(c.get("claim_text") or "").strip():
            empty_text.append(c.get("claim_id"))
    if bad_link:
        fail(f"LINKAGE: claims with invalid/missing source_id: {bad_link[:3]}")
    if empty_text:
        fail(f"EMPTY_CLAIM_TEXT: claims with no claim_text: {empty_text[:3]}")

    # 7. no TODO / lorem ipsum / placeholder markers in the human-facing report
    haystack = f"{html}\n{md}"
    for pat in PLACEHOLDER_PATTERNS:
        m = re.search(pat, haystack, flags=re.IGNORECASE)
        if m:
            fail(f"PLACEHOLDER_CONTENT: found '{m.group(0)}' in report.html/report.md")

    print(
        "RSI demo report validated: "
        f"{len(sources)} sources, {len(claims)} claims, all source_id links valid, "
        "report.html is HTML, no placeholder content"
    )


if __name__ == "__main__":
    main()
