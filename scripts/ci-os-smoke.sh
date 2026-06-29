#!/usr/bin/env bash
# CI cross-OS smoke: boot the status-server, assert GET /status + POST /intake plumbing.
# Portable (no setsid -> works on macOS + Linux + WSL). NO live LLM: /intake only asserts the sprint
# RECORD (status.json) is written, never a plan/deliverable (runners have no Claude/Codex auth).
set -uo pipefail
TASK="${1:-Write a one-line hello-world note.}"
H="${HARNESS_DIR:-$HOME/.solar/harness}"
[ -d "$H" ] || { echo "::error::harness dir missing: $H"; ls -la "$HOME/.solar" 2>/dev/null; exit 1; }
( cd "$H" && nohup python3 lib/symphony/status-server.py >/tmp/solar-srv.log 2>&1 & )
for i in $(seq 1 80); do [ -s "$H/run/status-server.port" ] && break; sleep 0.5; done
if [ ! -s "$H/run/status-server.port" ]; then
  echo "::error::status-server never wrote a port file"
  echo "--- /tmp/solar-srv.log ---"; cat /tmp/solar-srv.log 2>/dev/null
  echo "--- ls $H/run ---"; ls -la "$H/run" 2>/dev/null
  exit 1
fi
PORT="$(cat "$H/run/status-server.port")"; echo "port=$PORT"
curl -fsS "http://127.0.0.1:$PORT/status" >/dev/null && echo "STATUS_OK"
RESP="$(curl -fsS -m 200 -X POST "http://127.0.0.1:$PORT/intake" -H 'Content-Type: application/json' \
        -d "$(python3 -c 'import json,sys;print(json.dumps({"task":sys.argv[1]}))' "$TASK")")"
printf '%s' "$RESP" | python3 -c 'import sys,json,os;d=json.load(sys.stdin);assert d.get("ok"),d;sid=d["sprint_id"];p=os.path.join(os.path.expanduser("~/.solar/harness/sprints"),sid+".status.json");assert os.path.exists(p),"no "+p;print("INTAKE_OK",sid)'
echo "SMOKE GREEN: install + status-server + /intake plumbing (live LLM NOT run)."
