#!/usr/bin/env python3
"""Deterministic planner-quality battery scorer for P5 G2 prep.

Given a directory of planner-emitted ``<case>.task_graph.json`` files, validate
each graph with the shipped ``plan_validator`` against the real capsule and
operator registries plus the ``pm.generic.v1`` workflow contract. The output is
a stable JSON scorecard for the live planner runbook to compare across models
without spending quota inside this deterministic step.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import plan_validator as pv
import workflow_contract as wc

SCORECARD_SCHEMA = "solar.planner_battery.scorecard.v1"
TASK_GRAPH_SUFFIX = ".task_graph.json"
DEFAULT_OUTPUT_NAME = "battery-scorecard.json"


def _case_id(path: Path) -> str:
    name = path.name
    if name.endswith(TASK_GRAPH_SUFFIX):
        return name[: -len(TASK_GRAPH_SUFFIX)]
    return path.stem


def discover_graphs(graphs_dir: os.PathLike) -> List[Path]:
    """Return planner-output graph files in deterministic case order."""
    directory = Path(graphs_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"graphs_dir is not a directory: {directory}")
    return sorted(directory.glob(f"*{TASK_GRAPH_SUFFIX}"), key=lambda path: path.name)


def _load_validator_inputs(
    config_dir: Optional[os.PathLike] = None,
    workflows_dir: Optional[os.PathLike] = None,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], Optional[Dict[str, Any]]]:
    config = Path(config_dir) if config_dir else wc.default_config_dir()
    workflows = Path(workflows_dir) if workflows_dir else config / "workflows"
    capsule_registry = wc.load_capsule_registry(config)
    operator_registry = wc.load_operator_registry(config / "physical-operators.json")
    contract = wc.find_contract(pv.GENERIC_CONTRACT_ID, workflows)
    return capsule_registry, operator_registry, contract


def _code_counts(errors: Iterable[Dict[str, Any]]) -> Counter:
    counts: Counter = Counter()
    for error in errors:
        counts[str(error.get("code") or "UNKNOWN")] += 1
    return counts


def score_directory(
    graphs_dir: os.PathLike,
    config_dir: Optional[os.PathLike] = None,
    workflows_dir: Optional[os.PathLike] = None,
) -> Dict[str, Any]:
    """Validate every graph in ``graphs_dir`` and return a deterministic scorecard."""
    capsule_registry, operator_registry, contract = _load_validator_inputs(
        config_dir=config_dir,
        workflows_dir=workflows_dir,
    )
    cases: Dict[str, Any] = {}
    total_reject_codes: Counter = Counter()

    for graph_path in discover_graphs(graphs_dir):
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        errors = pv.validate_plan(
            graph,
            capsule_registry,
            operator_registry,
            contract=contract,
        )
        counts = _code_counts(errors)
        total_reject_codes.update(counts)
        case_id = _case_id(graph_path)
        cases[case_id] = {
            "graph_file": graph_path.name,
            "compiled": not errors,
            "error_count": len(errors),
            "error_codes": sorted(counts),
            "code_counts": dict(sorted(counts.items())),
        }

    case_count = len(cases)
    compiled = sum(1 for row in cases.values() if row["compiled"])
    rejected = case_count - compiled
    compile_rate = compiled / case_count if case_count else 0.0
    top_reject_codes = [
        {"code": code, "count": count}
        for code, count in sorted(total_reject_codes.items(), key=lambda item: (-item[1], item[0]))
    ]

    return {
        "schema": SCORECARD_SCHEMA,
        "validator": "plan_validator",
        "workflow_contract_id": pv.GENERIC_CONTRACT_ID,
        "cases": cases,
        "totals": {
            "case_count": case_count,
            "compiled": compiled,
            "rejected": rejected,
            "compile_rate": compile_rate,
            "top_reject_codes": top_reject_codes,
        },
    }


def write_scorecard(scorecard: Dict[str, Any], out_path: os.PathLike) -> Path:
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(scorecard, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, target)
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="planner_battery", description=__doc__)
    parser.add_argument("graphs_dir", help="directory containing <case>.task_graph.json files")
    parser.add_argument("--out", default=None, help="scorecard output path")
    parser.add_argument("--config-dir", default=None, help="harness config directory")
    parser.add_argument("--workflows-dir", default=None, help="workflow contract directory")
    args = parser.parse_args(argv)

    try:
        scorecard = score_directory(
            args.graphs_dir,
            config_dir=args.config_dir,
            workflows_dir=args.workflows_dir,
        )
        out_path = Path(args.out) if args.out else Path(args.graphs_dir) / DEFAULT_OUTPUT_NAME
        write_scorecard(scorecard, out_path)
    except Exception as exc:
        print(f"planner_battery: {exc}", file=sys.stderr)
        return 2

    print(f"battery scorecard: {out_path}")
    return 3 if scorecard["totals"]["rejected"] else 0


if __name__ == "__main__":
    sys.exit(main())
