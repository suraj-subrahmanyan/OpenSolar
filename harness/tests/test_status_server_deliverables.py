from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path


HARNESS_ROOT = Path(__file__).resolve().parents[1]
STATUS_SERVER = HARNESS_ROOT / "lib" / "symphony" / "status-server.py"


def _load_status_server(tmp_path: Path):
    harness = tmp_path / "harness"
    sprints = harness / "sprints"
    reports = harness / "reports"
    sprints.mkdir(parents=True)
    reports.mkdir(parents=True)

    spec = importlib.util.spec_from_file_location(
        f"status_server_deliverables_{time.time_ns()}", STATUS_SERVER
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HARNESS_DIR = harness
    module.SPRINTS_DIR = sprints
    module.REPORTS_DIR = reports
    return module, harness, sprints


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_canonical_workdir_outputs_are_visible_without_exposing_cache_or_symlink_escape(
    tmp_path: Path,
) -> None:
    module, harness, sprints = _load_status_server(tmp_path)
    sid = "sprint-deliverables"
    workdir = sprints / sid / "workdir"
    output = _write(workdir / "workspace" / "wrapcol.py", "print('wrapped')\n")
    _write(workdir / ".pytest_cache" / "README.md", "pytest cache internals\n")

    cross_sprint_secret = _write(
        sprints / "sprint-other" / "secret.txt",
        "must never be served through this sprint\n",
    )
    escape = workdir / "workspace" / "escape.txt"
    symlink_created = False
    try:
        escape.symlink_to(cross_sprint_secret)
        symlink_created = True
    except OSError:
        # Windows CI may deny unprivileged symlink creation. Linux still exercises
        # the containment assertion, while the core visibility assertions remain
        # portable.
        pass

    items = module._discover_sprint_deliverables(sid)
    names = {item["name"] for item in items}

    assert "wrapcol.py" in names
    assert "README.md" not in names
    if symlink_created:
        assert "escape.txt" not in names
        assert "secret.txt" not in names

    wrapcol = next(item for item in items if item["name"] == "wrapcol.py")
    assert wrapcol["source"] == "output"
    assert wrapcol["stage"] == "source"
    assert module._resolve_sprint_deliverable(sid, wrapcol["rel_path"]) == output.resolve()
    assert module._is_within(output.resolve(), harness)


def test_recorded_external_workdir_remains_supported(tmp_path: Path) -> None:
    module, _harness, sprints = _load_status_server(tmp_path)
    sid = "sprint-external-workdir"
    external = tmp_path / "external-workspace"
    output = _write(external / "result.py", "print('external')\n")
    _write(
        sprints / f"{sid}.raw_intent.json",
        json.dumps({"task": {"cwd": str(external)}}),
    )

    items = module._discover_sprint_deliverables(sid)
    result = next(item for item in items if item["name"] == "result.py")

    assert result["source"] == "output"
    assert module._resolve_sprint_deliverable(sid, result["rel_path"]) == output.resolve()
