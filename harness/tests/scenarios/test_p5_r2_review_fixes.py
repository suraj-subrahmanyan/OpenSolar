"""P5 G2b fix-round 2 review: regressions for the confirmed findings.

Independent review of 5cee48a4..33071be3 (p2-runbook/REVIEW-FIXROUND2.md)
reported four failing invariants; triage confirmed three as real defects
(the certificate operator-selection-field gap is a design decision held for
the owner — the runtime legitimately mutates node.preferred_profile during
quota fallback, so hashing it without a re-certification story would let a
legitimate fallback invalidate a certified node). These tests are the review
probes (p2-runbook/g2b-review-probes/r2_*.py) converted to deterministic
regressions (red first):

1. launch_node() is a public dispatch surface in all three multi_task_runner
   copies. The G2b fix guarded schedule_once(), but a direct launch_node()
   call still wrote dispatch.md / runner.sh / status.json (lib: plus a node
   runstate record) for an uncertified generic graph with
   SOLAR_PLAN_VALIDATOR=1 — the write happened before any guard.
3. contract_gate_executor appended --noconftest but inherited the caller's
   environment, so PYTEST_ADDOPTS=-p <module> (or PYTEST_PLUGINS) loaded a
   caller-named plugin inside the gate process anyway.
6. --noconftest was appended unconditionally, changing validator-OFF
   fixed-contract pytest gates: a suite that keeps fixtures in a local
   conftest.py (e.g. code.cli_smoke's sprints/<sid>/workdir/tests) went from
   passing to failing. The pytest hardening must be scoped to the validator
   flag so the legacy path stays byte-identical.

Same sandbox conventions as test_p5_g2b_review_fixes.py: real validator,
registries, graph files under tmp_path; no tmux/pane is touched (launch_node
runs in-process with dry_run=True and the profile/capability seams stubbed,
exactly like the review probes).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

_HARNESS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_HARNESS / "lib"))

import plan_validator as pv  # noqa: E402

WORKFLOWS_DIR = _HARNESS / "config" / "workflows"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_config(tmp_path: Path) -> tuple[Path, Path]:
    config = tmp_path / "config"
    capsules = config / "capability-capsules"
    workflows = config / "workflows"
    capsules.mkdir(parents=True)
    workflows.mkdir(parents=True)
    shutil.copy2(
        _HARNESS / "config" / "capability-capsules" / "cap.requirement-compiler-implementation.yaml",
        capsules / "cap.requirement-compiler-implementation.yaml",
    )
    shutil.copy2(
        WORKFLOWS_DIR / "pm.generic.v1.workflow.json",
        workflows / "pm.generic.v1.workflow.json",
    )
    _write_json(
        config / "physical-operators.json",
        {
            "version": 1,
            "operators": {
                "test-builder": {
                    "enabled": True,
                    "deprecated": False,
                    "health_status": "ok",
                    "role": "builder",
                    "roles": ["builder"],
                    "provider": "anthropic",
                }
            },
        },
    )
    return config, workflows


def _valid_node(**overrides) -> dict:
    node = {
        "id": "B1",
        "goal": "Implement the requested change.",
        "depends_on": [],
        "task_type": "implementation",
        "dispatch_task_type": "implementation",
        "capability_capsule_id": "cap.requirement-compiler-implementation",
        "allowed_operators": {"role": "builder", "providers": ["anthropic"]},
        "write_scope": ["workspace/harness/lib/example.py"],
        "proof_obligations": [{"proof_kind": "patch_proof", "field": "patch_diff"}],
        "evaluator_gate": {"kind": "llm_eval", "on_fail": "repair_once_then_fail"},
        "status": "pending",
    }
    node.update(overrides)
    return node


def _graph(sid: str, *, node: dict | None = None, **top) -> dict:
    graph = {"sprint_id": sid, "nodes": [node or _valid_node()]}
    graph.update(top)
    return graph


def _write_sprint(sprints: Path, sid: str, graph: dict) -> Path:
    _write_json(
        sprints / f"{sid}.status.json",
        {
            "id": sid,
            "sprint_id": sid,
            "status": "active",
            "phase": "planning_complete",
            "handoff_to": "builder_main",
            "target_role": "builder_main",
            "round": 0,
            "history": [],
        },
    )
    _write_json(sprints / f"{sid}.task_graph.json", graph)
    return sprints / f"{sid}.task_graph.json"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("SOLAR_PLAN_VALIDATOR", raising=False)
    monkeypatch.delenv("SOLAR_GATE_LEDGER", raising=False)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("PYTEST_PLUGINS", raising=False)


# --- Finding 1: direct launch_node() must honor the dispatch guard -----------

_RUNNER_COPIES = {
    "root": _HARNESS / "multi_task_runner.py",
    "tools": _HARNESS / "tools" / "multi_task_runner.py",
    "lib": _HARNESS / "lib" / "multi_task_runner.py",
}


def _load_runner_module(name: str, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("HARNESS_DIR", str(_HARNESS))
    monkeypatch.setenv("HARNESS_SPRINTS_DIR", str(tmp_path / "sprints"))
    module_name = f"r2_review_runner_{name}"
    spec = importlib.util.spec_from_file_location(module_name, _RUNNER_COPIES[name])
    assert spec is not None and spec.loader is not None
    mtr = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, mtr)
    spec.loader.exec_module(mtr)

    profile = {
        "name": "test",
        "role": "builder",
        "persona": "builder",
        "backend": "test",
        "model": "noop",
        "command": "true",
        "approval_mode": "auto_edit",
    }
    monkeypatch.setattr(mtr, "RUN_DIR", tmp_path / "run")
    monkeypatch.setattr(mtr, "SPRINTS_DIR", tmp_path / "sprints")
    monkeypatch.setattr(mtr, "select_profile", lambda node, p, m, b: profile)
    monkeypatch.setattr(
        mtr, "capability_for_profile",
        lambda selected: {
            "provider": "test",
            "status": "ok",
            "profile": selected.get("name"),
            "model": selected.get("model"),
            "backend": selected.get("backend"),
        },
    )
    return mtr


def _launch_args() -> argparse.Namespace:
    return argparse.Namespace(profile="", model="", backend="")


def _files_under(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("copy_name", sorted(_RUNNER_COPIES))
def test_launch_node_refuses_uncertified_generic_graph(tmp_path, monkeypatch, copy_name):
    """A direct launch_node() call (skipping schedule_once and its guard) must
    refuse an uncertified generic graph BEFORE any dispatch/status/runstate
    write — the review probe showed all three copies wrote dispatch.md,
    runner.sh and status.json first."""
    sid = f"sprint-r2fix1-{copy_name}"
    sprints = tmp_path / "sprints"
    graph = _graph(sid, workflow_contract_id="pm.generic.v1", workflow_contract_version="test")
    graph_path = _write_sprint(sprints, sid, graph)
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    mtr = _load_runner_module(copy_name, monkeypatch, tmp_path)
    graph_bytes = graph_path.read_bytes()
    before = _files_under(tmp_path)

    result = mtr.launch_node(graph_path, graph, graph["nodes"][0], _launch_args(), dry_run=True)

    assert result.get("status") == "plan_validator_dispatch_refused", result
    assert result.get("reason") == "plan_validator_dispatch_refused", result
    assert result.get("errors"), result
    assert _files_under(tmp_path) == before, "refused launch must not write dispatch artifacts"
    assert graph_path.read_bytes() == graph_bytes, "refused launch must not mutate the graph"


@pytest.mark.parametrize("copy_name", sorted(_RUNNER_COPIES))
def test_launch_node_admits_certified_generic_graph(tmp_path, monkeypatch, copy_name):
    sid = f"sprint-r2fix1-ok-{copy_name}"
    sprints = tmp_path / "sprints"
    config, workflows = _fixture_config(tmp_path)
    graph_path = _write_sprint(sprints, sid, _graph(sid))
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    verdict = pv.compile_planner_graph(sprints, sid, config_dir=config, workflows_dir=workflows)
    assert verdict["stamped"] is True
    stamped = json.loads(graph_path.read_text(encoding="utf-8"))
    mtr = _load_runner_module(copy_name, monkeypatch, tmp_path)

    result = mtr.launch_node(graph_path, stamped, stamped["nodes"][0], _launch_args(), dry_run=True)

    assert result.get("status") == "dry_run", result
    assert result.get("dispatch_file") and Path(result["dispatch_file"]).exists()


@pytest.mark.parametrize("copy_name", sorted(_RUNNER_COPIES))
def test_launch_node_untouched_when_validator_off(tmp_path, monkeypatch, copy_name):
    """Flag-off inertness: with the validator off, a direct launch_node() on
    the same uncertified generic graph keeps the legacy behavior."""
    sid = f"sprint-r2fix1-off-{copy_name}"
    sprints = tmp_path / "sprints"
    graph = _graph(sid, workflow_contract_id="pm.generic.v1", workflow_contract_version="test")
    graph_path = _write_sprint(sprints, sid, graph)
    mtr = _load_runner_module(copy_name, monkeypatch, tmp_path)

    result = mtr.launch_node(graph_path, graph, graph["nodes"][0], _launch_args(), dry_run=True)

    assert result.get("status") == "dry_run", result
    assert result.get("dispatch_file") and Path(result["dispatch_file"]).exists()


# --- Finding 3: gate process must not load plugins from inherited env --------


def _gate_harness(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A tmp harness with one passing test file plus an env-injectable plugin
    that writes a marker on load (the review probe's shape)."""
    harness = tmp_path / "harness"
    sprints = tmp_path / "sprints"
    plugin_dir = tmp_path / "plugins"
    (harness / "tests").mkdir(parents=True)
    (harness / "lib").mkdir()
    plugin_dir.mkdir()
    sprints.mkdir()
    marker = tmp_path / "plugin-loaded.txt"
    (harness / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    (plugin_dir / "r2_extra_plugin.py").write_text(
        "from pathlib import Path\n"
        f"MARKER = Path({str(marker)!r})\n"
        "def pytest_configure(config):\n"
        "    MARKER.write_text('loaded\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    return harness, sprints, marker


def _run_env_plugin_gate(tmp_path, monkeypatch, env_var: str, env_value: str) -> tuple[dict, Path]:
    import contract_gate_executor

    harness, sprints, marker = _gate_harness(tmp_path)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "plugins"))
    monkeypatch.setenv(env_var, env_value)
    result = contract_gate_executor.execute_gate(
        sprints,
        "sprint-r2fix3",
        {"id": "N1"},
        {"kind": "deterministic_command", "command": "python3 -m pytest tests/test_ok.py -q"},
        harness_dir=harness,
    )
    return result, marker


def test_gate_ignores_inherited_pytest_addopts_when_validator_on(tmp_path, monkeypatch):
    """The review probe: PYTEST_ADDOPTS=-p <module> in the parent environment
    loaded a caller-named plugin inside the gate process, overriding the
    isolation --noconftest establishes."""
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    result, marker = _run_env_plugin_gate(tmp_path, monkeypatch, "PYTEST_ADDOPTS", "-p r2_extra_plugin")

    assert result.get("exit_code") == 0, result
    assert not marker.exists(), "inherited PYTEST_ADDOPTS loaded a plugin in the gate process"


def test_gate_ignores_inherited_pytest_plugins_when_validator_on(tmp_path, monkeypatch):
    """PYTEST_PLUGINS is the same injection channel by another name."""
    monkeypatch.setenv("SOLAR_PLAN_VALIDATOR", "1")
    result, marker = _run_env_plugin_gate(tmp_path, monkeypatch, "PYTEST_PLUGINS", "r2_extra_plugin")

    assert result.get("exit_code") == 0, result
    assert not marker.exists(), "inherited PYTEST_PLUGINS loaded a plugin in the gate process"
