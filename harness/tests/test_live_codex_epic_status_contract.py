from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT.parent / "scripts" / "live_codex_epic_status.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("live_codex_epic_status_contract_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _contract_path(workflow_id: str) -> Path:
    return ROOT / "config" / "workflows" / f"{workflow_id}.workflow.json"


def test_contract_options_derive_artifacts_roots_terminal_states_and_validator():
    mod = _load_module()

    rsi = mod.contract_artifact_options(_contract_path("research.deepdive.rsi_demo"), sid="sprint-rsi")
    assert rsi["workflow_id"] == "research.deepdive.rsi_demo"
    assert rsi["expected_artifacts"] == [
        "report.html",
        "report.md",
        "sources.json",
        "claims.json",
        "evaluation-checklist.md",
    ]
    assert rsi["terminal_states"]["D5"] == ["passed", "failed", "skipped", "cancelled", "skipped_parent_passed"]
    assert rsi["validator_command"] == "python3 scripts/validate_rsi_demo_report.py --workspace <resolved_root>"
    assert rsi["roots"][0]["type"] == "contract_canonical"
    assert rsi["roots"][0]["root"].as_posix().endswith("workspace/rsi-deep-research-report")
    assert rsi["roots"][1]["type"] == "contract_alias"
    assert rsi["roots"][1]["root"].as_posix().endswith("sprints/sprint-rsi/workdir/rsi-deep-research-report")

    code = mod.contract_artifact_options(_contract_path("code.cli_smoke"), sid="sprint-code", substitutions={"tool": "hello"})
    assert code["expected_artifacts"] == ["hello.py", "tests/test_hello.py", "sprint-code.review_decision.yaml"]
    assert code["validator_command"] == "python3 -m pytest sprints/sprint-code/workdir/tests -q"

    generic = mod.contract_artifact_options(_contract_path("pm.generic.v1"), sid="sprint-generic")
    assert generic["expected_artifacts"] == []
    assert generic["roots"][0]["root"].as_posix().endswith("workspace")
    assert [row["type"] for row in generic["roots"]] == ["contract_canonical", "contract_alias", "contract_alias"]

