#!/usr/bin/env python3
"""F-CLASS-10 gate_replay driver — mechanical FAIL cannot flip a passed node.

The v5 replay at the node_verdict seam: a FAIL whose reason is in the gate
runner's mechanical vocabulary (research_eval_json_missing) must not flip a
policy-passed contracted node. Fault (SOLAR_GATE_LEDGER=0): legacy flips the
node to failed -> final_status "failed".
"""
import json
import os
from pathlib import Path

HARNESS_DIR = Path(os.environ["HARNESS_DIR"])
SPRINTS = HARNESS_DIR / "sprints"
SID = "f-class-10"

import graph_node_dispatcher as gnd  # noqa: E402

SPRINTS.mkdir(parents=True, exist_ok=True)
graph_path = SPRINTS / f"{SID}.task_graph.json"
graph_path.write_text(json.dumps({
    "sprint_id": SID,
    "workflow_contract_id": "research.deepdive.rsi_demo",
    "nodes": [{"id": "S1", "status": "passed", "depends_on": [],
               "updated_at": "2026-07-07T00:00:00Z"}],
    "node_results": {"S1": {"status": "passed", "updated_at": "2026-07-07T00:00:00Z"}},
    "gate_results": {},
}), encoding="utf-8")

result = gnd.node_verdict(str(graph_path), "S1", "fail",
                          reason="research_eval_json_missing", dry_run=True)

reloaded = json.loads(graph_path.read_text(encoding="utf-8"))
print(json.dumps({
    "final_status": reloaded["nodes"][0]["status"],
    "held_reason": str(result.get("reason") or ""),
}))
