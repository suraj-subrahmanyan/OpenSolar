"""P5 G2-prep: deterministic planner-quality battery scorer.

The scorer must exercise the real shipped plan_validator path with real
capsule/operator registries. These tests build only planner-output graph files
and then assert the emitted scorecard arithmetic and CLI exit codes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parents[2]
LIB_DIR = HARNESS_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import planner_battery as pb  # noqa: E402
import plan_validator as pv  # noqa: E402


def _node(node_id: str = "N1", **overrides) -> dict:
    node = {
        "id": node_id,
        "goal": f"{node_id} deterministic planner battery fixture",
        "depends_on": [],
        "task_type": "implementation",
        "dispatch_task_type": "implementation",
        "capability_capsule_id": "cap.requirement-compiler-implementation",
        "allowed_operators": {"role": "builder", "providers": ["openai"]},
        "write_scope": ["workspace/tools/example_tool.py", "workspace/tests/test_example_tool.py"],
        "proof_obligations": [],
        "evaluator_gate": {
            "kind": "deterministic_command",
            "command": "python3 -m pytest workspace/tests -q",
            "on_fail": "repair_once_then_fail",
        },
    }
    node.update(overrides)
    return node


def _graph(*nodes: dict) -> dict:
    return {
        "sprint_id": "sprint-p5-g2-battery-fixture",
        "workflow_contract_id": "pm.generic.v1",
        "workflow_contract_version": "1.0",
        "nodes": list(nodes) or [_node()],
    }


def _reject_graph() -> dict:
    return _graph(_node(
        "R1",
        evaluator_gate={"kind": "none", "on_fail": "fail"},
    ))


def _write_graph(directory: Path, case_id: str, graph: dict) -> Path:
    path = directory / f"{case_id}.task_graph.json"
    path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_scorecard_rows_and_totals_use_real_validator(tmp_path):
    graphs = tmp_path / "graphs"
    graphs.mkdir()
    _write_graph(graphs, "E1", _graph())
    _write_graph(graphs, "E5", _reject_graph())

    scorecard = pb.score_directory(graphs)

    assert scorecard["schema"] == pb.SCORECARD_SCHEMA
    assert scorecard["workflow_contract_id"] == pv.GENERIC_CONTRACT_ID
    assert list(scorecard["cases"]) == ["E1", "E5"]
    assert scorecard["cases"]["E1"] == {
        "graph_file": "E1.task_graph.json",
        "compiled": True,
        "error_count": 0,
        "error_codes": [],
        "code_counts": {},
    }
    assert scorecard["cases"]["E5"]["compiled"] is False
    assert scorecard["cases"]["E5"]["error_count"] == 1
    assert scorecard["cases"]["E5"]["error_codes"] == [pv.ERROR_PLAN_GATE_KIND_ILLEGAL]
    assert scorecard["cases"]["E5"]["code_counts"] == {pv.ERROR_PLAN_GATE_KIND_ILLEGAL: 1}
    assert scorecard["totals"] == {
        "case_count": 2,
        "compiled": 1,
        "rejected": 1,
        "compile_rate": 0.5,
        "top_reject_codes": [{"code": pv.ERROR_PLAN_GATE_KIND_ILLEGAL, "count": 1}],
    }


def test_cli_returns_zero_when_all_graphs_compile(tmp_path):
    graphs = tmp_path / "graphs"
    graphs.mkdir()
    out = tmp_path / "scorecard.json"
    _write_graph(graphs, "E1", _graph())

    result = _run_cli(graphs, out)

    assert result.returncode == 0, result.stderr
    assert "battery scorecard:" in result.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["totals"]["compile_rate"] == 1.0
    assert payload["totals"]["rejected"] == 0


def test_cli_returns_three_when_any_graph_rejects(tmp_path):
    graphs = tmp_path / "graphs"
    graphs.mkdir()
    out = tmp_path / "scorecard.json"
    _write_graph(graphs, "E1", _graph())
    _write_graph(graphs, "E5", _reject_graph())

    result = _run_cli(graphs, out)

    assert result.returncode == 3, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["totals"]["rejected"] == 1
    assert payload["totals"]["top_reject_codes"] == [
        {"code": pv.ERROR_PLAN_GATE_KIND_ILLEGAL, "count": 1}
    ]


def _run_cli(graphs_dir: Path, out: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(LIB_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "planner_battery", str(graphs_dir), "--out", str(out)],
        cwd=HARNESS_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
