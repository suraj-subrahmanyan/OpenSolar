"""AC-R4.1 / R4.2 / R4.4 acceptance replays (requirements R4).

AC-R4.1  v5 replay — a mechanical FAIL (research_eval_json_missing) cannot flip
         a policy-passed node; verdict_kind is set by the gate runner.
AC-R4.2  LDES shape — a critic record verdict=block blocks the gate even when
         the critic NODE status is passed (locks 5fcff602/983ce35a).
AC-R4.4  stale-generation evidence is archived (non-consumable record), never
         applied (locks 714eb781); pm_task_id correlation preserved (2a8ab9db).

(AC-R4.3's property/audit suite lives in test_status_writer_surface.py and the
consumability unit tests in test_gate_ledger_module.py.)
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

import gate_ledger as gl  # noqa: E402
import graph_scheduler as gs  # noqa: E402
import graph_node_dispatcher as gnd  # noqa: E402


SID = "lane3-r4-sprint"


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLAR_GATE_LEDGER", "1")
    monkeypatch.setattr(gs, "SPRINTS_DIR", tmp_path)
    monkeypatch.setattr(gnd, "SPRINTS_DIR", tmp_path)
    return tmp_path


def _contracted_graph(nodes):
    return {
        "sprint_id": SID,
        "workflow_contract_id": "research.deepdive.rsi_demo",
        "nodes": nodes,
        "node_results": {},
        "gate_results": {},
    }


def _write_graph(tmp_path, graph):
    path = tmp_path / f"{SID}.task_graph.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# AC-R4.1 — v5 mechanical-FAIL replay
# ---------------------------------------------------------------------------

class TestMechanicalFailCannotFlipPassed:
    def test_v5_replay_runner_vocabulary(self, sandbox, tmp_path):
        graph = _contracted_graph([
            {"id": "S1", "status": "passed", "depends_on": []},
        ])
        graph["node_results"]["S1"] = {"status": "passed", "updated_at": "2026-07-07T00:00:00Z"}
        graph_path = _write_graph(tmp_path, graph)

        result = gnd.node_verdict(graph_path, "S1", "fail",
                                  reason="research_eval_json_missing", dry_run=True)
        assert result["ok"] is False
        assert result["reason"] == "mechanical_fail_cannot_flip_passed_node"
        assert result["verdict_kind"] == "mechanical"

        # The node did not flip.
        reloaded = json.loads(Path(graph_path).read_text(encoding="utf-8"))
        assert reloaded["nodes"][0]["status"] == "passed"

        # The verdict is archived, non-consumable; a gate_check hold explains why.
        verdicts = gl.read_records(sandbox, SID, node_id="S1", kind="eval_verdict")
        assert verdicts and verdicts[-1]["verdict"] == "FAIL"
        assert verdicts[-1]["verdict_kind"] == "mechanical"
        assert verdicts[-1]["archived"] is True
        assert gl.is_gate_consumable(verdicts[-1]) is False
        holds = gl.read_records(sandbox, SID, node_id="S1", kind="gate_check")
        assert holds and holds[-1]["note"] == "mechanical_fail_cannot_flip_passed_node"

    def test_explicit_infrastructure_kind_also_held(self, sandbox, tmp_path):
        graph = _contracted_graph([{"id": "S1", "status": "passed", "depends_on": []}])
        graph["node_results"]["S1"] = {"status": "passed", "updated_at": "2026-07-07T00:00:00Z"}
        graph_path = _write_graph(tmp_path, graph)
        result = gnd.node_verdict(graph_path, "S1", "fail",
                                  reason="operator pool restarted",
                                  verdict_kind="infrastructure", dry_run=True)
        assert result["reason"] == "mechanical_fail_cannot_flip_passed_node"

    def test_content_fail_still_flips(self, sandbox, tmp_path):
        """A real (content) evaluator FAIL keeps its legacy effect — only the
        mechanical/infrastructure kinds are held."""
        graph = _contracted_graph([{"id": "S1", "status": "passed", "depends_on": []}])
        graph["node_results"]["S1"] = {"status": "passed", "updated_at": "2026-07-07T00:00:00Z"}
        graph_path = _write_graph(tmp_path, graph)
        result = gnd.node_verdict(graph_path, "S1", "fail",
                                  reason="report contradicts sources", dry_run=True)
        assert result.get("reason") != "mechanical_fail_cannot_flip_passed_node"
        assert result.get("status") in {"failed", "failed_review"}

    def test_flag_off_keeps_legacy_flip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SOLAR_GATE_LEDGER", "0")
        monkeypatch.setattr(gs, "SPRINTS_DIR", tmp_path)
        monkeypatch.setattr(gnd, "SPRINTS_DIR", tmp_path)
        graph = _contracted_graph([{"id": "S1", "status": "passed", "depends_on": []}])
        graph["node_results"]["S1"] = {"status": "passed", "updated_at": "2026-07-07T00:00:00Z"}
        graph_path = _write_graph(tmp_path, graph)
        result = gnd.node_verdict(graph_path, "S1", "fail",
                                  reason="research_eval_json_missing", dry_run=True)
        assert result.get("reason") != "mechanical_fail_cannot_flip_passed_node"


# ---------------------------------------------------------------------------
# AC-R4.2 — LDES critic-block shape
# ---------------------------------------------------------------------------

class TestCriticBlockBlocksGate:
    def test_consumable_block_record_blocks_gate_despite_passed_node(self, sandbox):
        graph = _contracted_graph([
            {"id": "C1", "status": "passed", "depends_on": [], "gate": "G1"},
        ])
        gl.append_record(sandbox, SID, node_id="C1", kind="eval_verdict",
                         author={"type": "evaluator", "operator_id": "critic-1"},
                         verdict="block", verdict_kind="content")
        ok, blocking_node, detail = gs._gate_verdicts_ok(graph, ["C1"])
        assert ok is False
        assert blocking_node == "C1"
        assert detail.startswith("ledger_verdict_block:")

    def test_gate_result_blocked_through_mark_node_result(self, sandbox):
        graph = _contracted_graph([
            {"id": "C1", "status": "reviewing", "depends_on": [], "gate": "G1"},
        ])
        gl.append_record(sandbox, SID, node_id="C1", kind="eval_verdict",
                         author={"type": "evaluator", "operator_id": "critic-1"},
                         verdict="block", verdict_kind="content")
        gs.mark_node_result(graph, "C1", "passed")
        gate = graph["gate_results"]["G1"]
        assert gate["status"] == "blocked"
        assert "ledger_verdict_block" in str(gate.get("reason") or "")

    def test_non_consumable_block_does_not_block(self, sandbox):
        graph = _contracted_graph([
            {"id": "C1", "status": "passed", "depends_on": [], "gate": "G1"},
        ])
        gl.append_record(sandbox, SID, node_id="C1", kind="eval_verdict",
                         author={"type": "doctor"},
                         verdict="block", verdict_kind="content",
                         gate_consumable=False)
        ok, _, _ = gs._gate_verdicts_ok(graph, ["C1"])
        assert ok is True

    def test_uncontracted_graph_skips_ledger_consult(self, sandbox):
        graph = {"sprint_id": SID, "nodes": [{"id": "C1", "status": "passed", "gate": "G1"}],
                 "node_results": {}, "gate_results": {}}
        gl.append_record(sandbox, SID, node_id="C1", kind="eval_verdict",
                         author={"type": "evaluator", "operator_id": "critic-1"},
                         verdict="block", verdict_kind="content")
        ok, _, _ = gs._gate_verdicts_ok(graph, ["C1"])
        assert ok is True


# ---------------------------------------------------------------------------
# AC-R4.4 — stale-generation archive + PM-task correlation
# ---------------------------------------------------------------------------

class TestStaleGenerationAndCorrelation:
    def test_stale_generation_eval_archived_with_record_never_applied(self, sandbox, tmp_path):
        eval_json = tmp_path / f"{SID}.S1-eval.json"
        eval_json.write_text(json.dumps({
            "verdict": "PASS",
            "eval_generation": 0,
            "summary": "stale pre-repair pass",
        }), encoding="utf-8")
        graph = _contracted_graph([
            {
                "id": "S1", "status": "reviewing", "depends_on": [],
                "eval_json": str(eval_json),
                "repair_attempts": 1,
                "repair_context": {"attempt": 1, "created_at": "2026-07-07T00:00:00Z"},
            },
        ])
        graph_path = _write_graph(tmp_path, graph)
        loaded = gs.load_graph(graph_path)
        gnd._reconcile_existing_dispatches(loaded, graph_path)

        # Never applied: the stale PASS did not close the node.
        assert gs.node_status(loaded, "S1") != "passed"
        # Archived + recorded as non-consumable.
        verdicts = gl.read_records(sandbox, SID, node_id="S1", kind="eval_verdict")
        assert verdicts, "stale-generation archive must leave a ledger record"
        row = verdicts[-1]
        assert row["archived"] is True
        assert row["stale_reason"], "the archive record must name why the evidence was stale"
        assert gl.is_gate_consumable(row, current_generation=1) is False

    def test_pm_task_id_correlation_preserved_on_verdict_records(self, sandbox, tmp_path):
        graph = _contracted_graph([
            {
                "id": "S1", "status": "reviewing", "depends_on": [],
                "eval_assignments": [
                    {"role": "evaluator", "pane": "operator-pool:mini-codex-eval-1",
                     "dispatch_id": "d-77", "pm_task_id": "pm-42"},
                ],
            },
        ])
        graph_path = _write_graph(tmp_path, graph)
        result = gnd.node_verdict(graph_path, "S1", "fail",
                                  reason="weak evidence", dry_run=True)
        assert result.get("reason") != "mechanical_fail_cannot_flip_passed_node"
        verdicts = gl.read_records(sandbox, SID, node_id="S1", kind="eval_verdict")
        assert verdicts and verdicts[-1]["pm_task_id"] == "pm-42"
        assert verdicts[-1]["verdict"] == "FAIL"
        assert verdicts[-1]["verdict_kind"] == "content"
