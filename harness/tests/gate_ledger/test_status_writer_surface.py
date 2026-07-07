"""AC-R4.3 — the status-writer surface (review round-1 finding 3.1 / C4 list).

Two halves:

1. Source audit: every node-status assignment in graph_scheduler.py /
   graph_node_dispatcher.py must live inside an audited writer function, and every
   audited writer (except the state loader) must report through the gate ledger.
   A NEW direct write outside this surface fails the test.

2. Runtime property (SOLAR_GATE_LEDGER=1, sandboxed SPRINTS_DIR): no status
   transition without a ledger record; suppressed rank-guard writes record
   nothing; terminal statuses are absorbing in the projection; doctor_graph is
   neutralized on the contracted path (applied=false records, no direct status);
   flag-off writes leave no ledger file.
"""
from __future__ import annotations

import ast
import json
import re
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


# ---------------------------------------------------------------------------
# 1. Source audit — the C4 writer list is the complete surface
# ---------------------------------------------------------------------------

# The audited writer surface. "ledger" = the function must contain a
# _ledger_transition/_doctor_write_suppressed call; "loader" = rehydrates
# already-recorded state from disk on graph load (not a transition).
AUDITED_WRITERS = {
    "graph_scheduler.py": {
        "_attach_runtime_planes": "loader",
        "mark_node_result": "ledger",
        "set_node_status": "ledger",
        "doctor_graph": "ledger",
    },
    "graph_node_dispatcher.py": {
        "_prepare_human_search_handoff": "ledger",
        "_start_node_repair_from_eval_fail": "ledger",
        "_reconcile_existing_dispatches": "ledger",
        "_mark_graph_node": "ledger",
        "dispatch_node_evals": "ledger",
        "_account_eval_dispatch_failures": "ledger",
        # node_verdict's inline write repeats the status mark_node_result just
        # recorded (same-status force-write); the ledger record comes from
        # mark_node_result, so no separate call is required here.
        "node_verdict": "recorded_via_mark_node_result",
    },
}

_NODE_STATUS_WRITE = re.compile(
    r'(?:node|live|ids\[node_id\])\["status"\]\s*=[^=]'
)


def _status_writer_functions(path: Path) -> dict[str, list[int]]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    spans = [
        (fn.lineno, fn.end_lineno or fn.lineno, fn.name)
        for fn in ast.walk(tree)
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    writers: dict[str, list[int]] = {}
    for match in _NODE_STATUS_WRITE.finditer(src):
        lineno = src[: match.start()].count("\n") + 1
        enclosing = [name for (a, b, name) in spans if a <= lineno <= b]
        name = enclosing[-1] if enclosing else "<module>"
        writers.setdefault(name, []).append(lineno)
    return writers


def _function_source(path: Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name == name:
            return ast.get_source_segment(src, fn) or ""
    return ""


@pytest.mark.parametrize("filename", sorted(AUDITED_WRITERS))
def test_no_status_write_outside_audited_surface(filename):
    path = _HARNESS / "lib" / filename
    writers = _status_writer_functions(path)
    unaudited = {
        name: lines for name, lines in writers.items()
        if name not in AUDITED_WRITERS[filename]
    }
    assert not unaudited, (
        f"{filename}: node-status writes outside the audited C4 surface: {unaudited}. "
        "Route the write through set_node_status or add a _ledger_transition call "
        "and extend AUDITED_WRITERS deliberately."
    )


@pytest.mark.parametrize("filename", sorted(AUDITED_WRITERS))
def test_every_audited_writer_reports_to_the_ledger(filename):
    path = _HARNESS / "lib" / filename
    for name, mode in AUDITED_WRITERS[filename].items():
        if mode != "ledger":
            continue
        body = _function_source(path, name)
        assert body, f"{filename}: audited writer {name} not found"
        assert "_ledger_transition(" in body or "_doctor_write_suppressed(" in body, (
            f"{filename}:{name} writes node status but never reports to the gate ledger"
        )


def test_audited_surface_matches_reality():
    """The allowlist itself may not go stale: every listed writer must still write."""
    for filename, expected in AUDITED_WRITERS.items():
        writers = _status_writer_functions(_HARNESS / "lib" / filename)
        for name in expected:
            assert name in writers, (
                f"{filename}: {name} is allowlisted but no longer writes node status — prune it"
            )


# ---------------------------------------------------------------------------
# 2. Runtime property
# ---------------------------------------------------------------------------

SID = "lane3-property"


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLAR_GATE_LEDGER", "1")
    monkeypatch.setattr(gs, "SPRINTS_DIR", tmp_path)
    monkeypatch.setattr(gnd, "SPRINTS_DIR", tmp_path)
    return tmp_path


def _graph(contracted: bool = False) -> dict:
    graph = {
        "sprint_id": SID,
        "nodes": [
            {"id": "S1", "status": "pending", "depends_on": []},
            {"id": "S2", "status": "pending", "depends_on": ["S1"]},
        ],
        "node_results": {},
        "gate_results": {},
    }
    if contracted:
        graph["workflow_contract_id"] = "code.cli_smoke"
    return graph


def _transitions(tmp_path, node_id=None):
    return gl.read_records(tmp_path, SID, node_id=node_id, kind="status_transition")


def test_set_node_status_records_every_applied_write(sandbox):
    graph = _graph()
    gs.set_node_status(graph, "S1", "assigned")
    gs.set_node_status(graph, "S1", "running")
    rows = _transitions(sandbox, "S1")
    assert [(r["from_status"], r["to_status"]) for r in rows] == [
        ("pending", "assigned"), ("assigned", "running"),
    ]
    assert all(r["writer"] == "set_node_status" for r in rows)
    assert gl.project_node_status(sandbox, SID, "S1") == gs.node_status(graph, "S1") == "running"


def test_rank_guard_suppressed_write_records_nothing(sandbox):
    graph = _graph()
    gs.set_node_status(graph, "S1", "reviewing")
    before = len(_transitions(sandbox, "S1"))
    gs.set_node_status(graph, "S1", "queued")  # rank 1 < reviewing 4: refused
    assert gs.node_status(graph, "S1") == "reviewing"
    assert len(_transitions(sandbox, "S1")) == before


def test_mark_node_result_records_forced_write(sandbox):
    graph = _graph()
    gs.set_node_status(graph, "S1", "reviewing")
    gs.mark_node_result(graph, "S1", "failed", note="eval FAIL")
    rows = _transitions(sandbox, "S1")
    assert rows[-1]["writer"] == "mark_node_result"
    assert (rows[-1]["from_status"], rows[-1]["to_status"]) == ("reviewing", "failed")
    assert gl.project_node_status(sandbox, SID, "S1") == "failed"


def test_terminal_statuses_absorbing_in_projection(sandbox):
    """Absorbing = no exit from terminal without an APPLIED audited record
    (round-4 G6 semantics): unapplied would-be writes never project; a real
    applied record — scheduler or human — always does."""
    graph = _graph()
    gs.mark_node_result(graph, "S1", "failed")
    # A neutralized (applied=False) post-terminal write is recorded but not projected.
    gl.record_status_transition(sandbox, SID, "S1", from_status="failed", to_status="pending",
                                author_type="scheduler", writer="test_force", applied=False)
    assert gl.project_node_status(sandbox, SID, "S1") == "failed"
    # An APPLIED post-terminal record projects — the writer really performed it.
    gl.record_status_transition(sandbox, SID, "S1", from_status="failed", to_status="pending",
                                author_type="scheduler", writer="recover_quota_failed_nodes")
    assert gl.project_node_status(sandbox, SID, "S1") == "pending"
    # A human-authored reopen is projected.
    gl.record_status_transition(sandbox, SID, "S1", from_status="pending", to_status="reviewing",
                                author_type="human", writer="human_verdict")
    assert gl.project_node_status(sandbox, SID, "S1") == "reviewing"


def test_mark_graph_node_records_transition(sandbox, tmp_path):
    graph_path = tmp_path / f"{SID}.task_graph.json"
    graph_path.write_text(json.dumps(_graph()), encoding="utf-8")
    assert gnd._mark_graph_node(str(graph_path), "S1", "dispatched", pane="operator-pool:x", dispatch_id="d1")
    rows = _transitions(sandbox, "S1")
    assert rows and rows[-1]["writer"] == "_mark_graph_node"
    assert rows[-1]["to_status"] == "dispatched"


def test_doctor_neutralized_on_contracted_path(sandbox):
    graph = _graph(contracted=True)
    # Manufacture drift: inline passed vs node_results failed, no timestamps.
    graph["nodes"][0]["status"] = "passed"
    graph["node_results"]["S1"] = {"status": "failed", "updated_at": ""}
    report = gs.doctor_graph(graph, repair=True)
    # No direct status write happened...
    assert graph["nodes"][0]["status"] == "passed"
    assert graph["node_results"]["S1"]["status"] == "failed"
    assert not report["repairs"]
    assert report.get("suppressed"), "doctor would-be writes must surface as suppressed records"
    # ...and the would-be write exists as a non-applied doctor record.
    rows = [r for r in _transitions(sandbox, "S1") if r.get("applied") is False]
    assert rows and rows[-1]["author"]["type"] == "doctor"
    assert gl.is_gate_consumable(rows[-1]) is False


def test_doctor_still_repairs_off_contract_and_records(sandbox):
    graph = _graph(contracted=False)
    graph["nodes"][0]["status"] = "passed"
    graph["node_results"]["S1"] = {"status": "failed", "updated_at": ""}
    report = gs.doctor_graph(graph, repair=True)
    assert report["repairs"], "legacy (uncontracted) doctor repair must keep working"
    rows = _transitions(sandbox, "S1")
    assert rows and rows[-1]["author"]["type"] == "doctor"
    assert rows[-1].get("applied") is not False


def test_flag_off_writes_no_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLAR_GATE_LEDGER", "0")
    monkeypatch.setattr(gs, "SPRINTS_DIR", tmp_path)
    graph = _graph()
    gs.set_node_status(graph, "S1", "running")
    gs.mark_node_result(graph, "S1", "passed")
    assert gs.node_status(graph, "S1") == "passed"
    assert not list(Path(tmp_path).glob("*.gate-ledger.jsonl"))
