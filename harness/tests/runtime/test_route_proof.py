import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(ROOT / "lib"))

import graph_scheduler  # noqa: E402
import route_proof  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _seed_registry(harness: Path) -> None:
    _write_json(
        harness / "config" / "physical-operators.json",
        {
            "version": 1,
            "operators": {
                "codex-builder": {
                    "role": "builder",
                    "provider": "openai",
                    "backend": "command",
                    "model": "gpt-5.3-codex-spark",
                    "enabled": True,
                },
                "claude-evaluator": {
                    "role": "evaluator",
                    "provider": "anthropic",
                    "backend": "claude-cli",
                    "model": "sonnet",
                    "enabled": True,
                },
            },
        },
    )


def _seed_pm_record(
    harness: Path,
    sid: str,
    task_id: str,
    *,
    node_id: str,
    role: str,
    operator_id: str,
    runtime_mode: str = "codex",
    provider_policy: str = "openai",
    status: str = "completed",
) -> None:
    _write_json(
        harness / "run" / "pm-inbox" / f"{task_id}.json",
        {
            "task_id": task_id,
            "sprint_id": sid,
            "node_id": node_id,
            "requested_role": role,
            "runtime_mode": runtime_mode,
            "provider_policy": provider_policy,
            "operator_id": operator_id,
            "status": status,
        },
    )


def _seed_result(
    harness: Path,
    sid: str,
    task_id: str,
    *,
    node_id: str,
    operator_id: str,
    provider: str,
    model: str = "gpt-5.5",
) -> None:
    _write_json(
        harness / "run" / "operator-results" / operator_id / task_id / "result.json",
        {
            "task_id": task_id,
            "sprint_id": sid,
            "node_id": node_id,
            "operator_id": operator_id,
            "status": "completed",
            "exit_code": 0,
            "effective_provider": provider,
            "effective_model": model,
        },
    )


def test_codex_route_proof_accepts_openai_only(tmp_path):
    harness = tmp_path / "harness"
    sid = "sprint-route-ok"
    _seed_registry(harness)
    _seed_pm_record(harness, sid, "task-builder", node_id="S1", role="builder", operator_id="codex-builder")
    _seed_result(harness, sid, "task-builder", node_id="S1", operator_id="codex-builder", provider="openai")

    proof = route_proof.write_route_proof(harness, sid)

    assert proof["ok"] is True
    assert proof["enforced"] is True
    assert proof["allowed_providers"] == ["openai"]
    assert proof["violations"] == []
    assert (harness / "sprints" / f"{sid}.route-proof.json").exists()


def test_codex_route_proof_flags_anthropic_violation(tmp_path):
    harness = tmp_path / "harness"
    sid = "sprint-route-bad"
    _seed_registry(harness)
    _seed_pm_record(harness, sid, "task-eval", node_id="S1", role="evaluator", operator_id="claude-evaluator")
    _seed_result(harness, sid, "task-eval", node_id="S1", operator_id="claude-evaluator", provider="anthropic", model="sonnet")

    proof = route_proof.write_route_proof(harness, sid)

    assert proof["ok"] is False
    assert proof["violations"] == [
        {
            "task_id": "task-eval",
            "node_id": "S1",
            "provider": "anthropic",
            "allowed_providers": ["openai"],
            "reason": "provider_policy_violation",
        }
    ]


def test_scheduler_closeout_blocks_route_proof_violation(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    sprints = harness / "sprints"
    sid = "sprint-route-closeout"
    _seed_registry(harness)
    _seed_pm_record(harness, sid, "task-eval", node_id="S1", role="evaluator", operator_id="claude-evaluator")
    _seed_result(harness, sid, "task-eval", node_id="S1", operator_id="claude-evaluator", provider="anthropic", model="sonnet")
    _write_json(
        sprints / f"{sid}.status.json",
        {
            "sprint_id": sid,
            "status": "active",
            "phase": "planning_complete",
        },
    )
    graph_path = sprints / f"{sid}.task_graph.json"
    graph = {
        "sprint_id": sid,
        "nodes": [{"id": "S1", "status": "passed"}],
        "required_gates": [],
        "node_results": {"S1": {"status": "passed"}},
    }
    _write_json(graph_path, graph)

    monkeypatch.setattr(graph_scheduler, "HARNESS_DIR", harness)
    monkeypatch.setattr(graph_scheduler, "SPRINTS_DIR", sprints)

    result = graph_scheduler.sync_status_cache_from_graph(graph, graph_path)

    assert result["ok"] is False
    assert result["reason"] == "route_proof_violation"
    assert result["route_proof"]["violations"][0]["provider"] == "anthropic"
    status = json.loads((sprints / f"{sid}.status.json").read_text(encoding="utf-8"))
    assert status["status"] == "active"


def test_stale_physical_plan_operator_does_not_override_route_proof(tmp_path):
    harness = tmp_path / "harness"
    sprints = harness / "sprints"
    sid = "sprint-stale-physical-plan"
    _seed_registry(harness)
    _seed_pm_record(harness, sid, "task-builder", node_id="S1", role="builder", operator_id="codex-builder")
    _seed_result(harness, sid, "task-builder", node_id="S1", operator_id="codex-builder", provider="openai")
    physical_plan = sprints / f"{sid}.S1-physical-plan.json"
    _write_json(physical_plan, {"selected_operator_id": "mini-claude-sonnet-builder"})
    _write_json(
        sprints / f"{sid}.task_graph.json",
        {
            "sprint_id": sid,
            "nodes": [
                {
                    "id": "S1",
                    "artifacts": {
                        "selected_operator_id": "mini-claude-sonnet-builder",
                        "physical_plan_ir": str(physical_plan),
                    },
                }
            ],
        },
    )

    proof = route_proof.write_route_proof(harness, sid)

    assert proof["ok"] is True
    assert proof["violations"] == []
    assert proof["stages"][0]["operator_id"] == "codex-builder"
    assert proof["stages"][0]["provider"] == "openai"
    warnings = proof["diagnostics"]["attribution_warnings"]
    assert warnings
    assert warnings[0]["reason"] == "stale_physical_plan_selected_operator"
    assert warnings[0]["selected_operator_id"] == "mini-claude-sonnet-builder"
    assert warnings[0]["actual_operator_ids"] == ["codex-builder"]
    assert warnings[0]["diagnostic"] == "physical_plan_selected_operator_untrusted_for_route_proof"
