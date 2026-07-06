#!/usr/bin/env python3
"""test_lane2_scenarios.py — red-before-green gate for the Lane 2 fake-operator catalog.

Independence guard #1: a scenario proves nothing unless it has been demonstrated RED. For every
``verified_here`` scenario this test runs the real hermetic pipeline twice via
``run_scenario.run_scenario``:

* GREEN (real code, guard active)     -> all ``expect`` assertions satisfied -> report.passed
* RED   (scenario's ``fault`` injected) -> the class reproduces -> NOT report.passed

A scenario that passes both, or fails both, is not discriminating and fails this test. The pairing
IS the red-before-green evidence, executed in CI on every run (no network, no quota).

The catalog integrity test asserts every ``verified_here`` class points at a real scenario file and
every other class carries an honest pending/delegated status with a named missing seam — so the
30-class ledger cannot silently claim coverage it does not have.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = TESTS_DIR / "scenarios"
CATALOG = SCENARIOS_DIR / "catalog.json"

sys.path.insert(0, str(TESTS_DIR))
import run_scenario as rs  # noqa: E402 — after path setup


def _verified_scenario_files() -> list[Path]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    files = []
    for entry in catalog["classes"]:
        if entry["status"] == "verified_here":
            assert entry["scenario"], f"class {entry['class']} verified_here but no scenario file"
            files.append(SCENARIOS_DIR / entry["scenario"])
    return files


VERIFIED = _verified_scenario_files()


@pytest.mark.parametrize("scenario_path", VERIFIED, ids=[p.name for p in VERIFIED])
def test_scenario_green_passes(scenario_path: Path):
    scenario = rs.load_scenario(scenario_path)
    report = rs.run_scenario(scenario, red=False)
    assert report["passed"], (
        f"GREEN run of {scenario_path.name} should PASS but did not.\n"
        f"facts={json.dumps(report['facts'], indent=2, default=str)}\n"
        f"checks={json.dumps(report['checks'], indent=2, default=str)}"
    )


@pytest.mark.parametrize("scenario_path", VERIFIED, ids=[p.name for p in VERIFIED])
def test_scenario_red_fails(scenario_path: Path):
    scenario = rs.load_scenario(scenario_path)
    assert scenario.get("fault"), f"{scenario_path.name} has no fault block; cannot prove it is red-able"
    report = rs.run_scenario(scenario, red=True)
    assert not report["passed"], (
        f"RED run of {scenario_path.name} should FAIL (the class must reproduce when the fault is "
        f"injected) but every expect still passed — the scenario is not discriminating.\n"
        f"facts={json.dumps(report['facts'], indent=2, default=str)}\n"
        f"checks={json.dumps(report['checks'], indent=2, default=str)}"
    )


def test_catalog_is_complete_and_honest():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    classes = catalog["classes"]
    seen = {c["class"] for c in classes}
    assert seen == set(range(1, 31)), f"catalog must cover classes 1..30, missing/extra: {seen ^ set(range(1,31))}"

    valid_status = {
        "verified_here", "pending_lane_0", "pending_lane_1", "pending_lane_3",
        "pending_lane_5", "non_hermetic_p1_6", "delegated_lane_6",
    }
    for entry in classes:
        assert entry["status"] in valid_status, f"class {entry['class']} bad status {entry['status']}"
        if entry["status"] == "verified_here":
            path = SCENARIOS_DIR / entry["scenario"]
            assert path.exists(), f"class {entry['class']} scenario missing: {path}"
        else:
            # An honest pending row names the missing seam so it cannot masquerade as covered.
            assert entry.get("required_seam") or entry["status"] in {"delegated_lane_6", "non_hermetic_p1_6"}, (
                f"class {entry['class']} is {entry['status']} but names no required_seam"
            )


def test_summary_matches_rows():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_rows = sorted(c["class"] for c in catalog["classes"] if c["status"] == "verified_here")
    assert verified_rows == sorted(catalog["summary"]["verified_here"]), (
        "catalog.summary.verified_here is out of sync with the class rows"
    )
