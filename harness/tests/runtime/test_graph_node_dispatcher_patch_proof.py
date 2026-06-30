#!/usr/bin/env python3
"""Regression tests for graph-node patch proof sidecars."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _exercise_patch_proof(module, tmp_path: Path, monkeypatch) -> None:
    harness = tmp_path / "harness"
    sprints = harness / "sprints"
    sid = "sprint-patch-proof"
    workdir = sprints / sid / "workdir"
    workdir.mkdir(parents=True)
    target = workdir / "uniqwords.py"
    target.write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(module, "HARNESS_DIR", harness)
    monkeypatch.setattr(module, "SPRINTS_DIR", sprints)
    node = {
        "id": "S1",
        "write_scope": [f"harness/sprints/{sid}/workdir/uniqwords.py"],
        "proof_obligations": [
            {"kind": "pass_condition", "requirement": "patch_diff exists"},
            {"kind": "postcondition", "requirement": "output_present", "field": "patch_diff"},
        ],
    }

    emitted = module._emit_node_proof_sidecars(sid, node)
    patch_path = sprints / f"{sid}.S1-patch.diff"

    assert emitted["patch_diff"] == str(patch_path)
    assert patch_path.exists()
    patch = patch_path.read_text(encoding="utf-8")
    assert "diff --git a/harness/sprints/sprint-patch-proof/workdir/uniqwords.py" in patch
    assert "--- /dev/null" in patch
    assert "+print('ok')" in patch
    assert module._proof_artifact_presence(sid, node)["patch_diff"] is True
    assert module._evaluate_proof_obligations(sid, node)["ok"] is True


def test_lib_dispatcher_emits_patch_diff_from_write_scope(tmp_path, monkeypatch):
    monkeypatch.delenv("HARNESS_DIR", raising=False)
    monkeypatch.delitem(sys.modules, "graph_scheduler", raising=False)
    module = _load_module("graph_node_dispatcher_lib_patch_proof", ROOT / "lib" / "graph_node_dispatcher.py")
    _exercise_patch_proof(module, tmp_path, monkeypatch)


def test_tools_dispatcher_emits_patch_diff_from_write_scope(tmp_path, monkeypatch):
    monkeypatch.delenv("HARNESS_DIR", raising=False)
    monkeypatch.delitem(sys.modules, "graph_scheduler", raising=False)
    module = _load_module("graph_node_dispatcher_tools_patch_proof", ROOT / "tools" / "graph_node_dispatcher.py")
    _exercise_patch_proof(module, tmp_path, monkeypatch)
