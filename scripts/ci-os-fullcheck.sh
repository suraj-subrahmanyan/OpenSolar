#!/usr/bin/env bash
# ci-os-fullcheck.sh — run the REAL new-machine command battery on whatever OS this is.
#
# Why this exists: the functional check-suite historically ran ubuntu-only, so "CI green" meant
# "works on Ubuntu" while macOS / Windows-WSL (a real user's machine) silently broke on BSD-vs-GNU
# tools, bash 3.2, path and CRLF differences. Each sub-check below self-installs into a sandbox HOME
# and exercises the actual `solar` / status-server commands a fresh user runs, then cleans up — so a
# GREEN here means "a brand-new machine of THIS OS can install Solar and run the documented commands."
#
# NO live LLM: hosted runners have no Claude/Codex auth. This asserts the deterministic command surface
# and HTTP plumbing (doctor, harness front-door, status, dashboard backend contract, offline update,
# dashboard /intake record) — everything a new machine does up to the auth boundary.
set -uo pipefail
cd "$(dirname "$0")/.."
OS="$(uname -s)"
TASK="${INTAKE_TASK:-Write a one-line hello-world note.}"
fails=""

run() { # run <label> <script-under-scripts/>
  echo "::group::$1 ($OS)"
  if bash "scripts/$2"; then echo "PASS $1"; else echo "::error::FAIL $1 on $OS"; fails="$fails $1"; fi
  echo "::endgroup::"
}

# Real user-facing command checks (self-contained: sandbox HOME, real install, real commands, cleanup).
run "solar harness front-door" check-solar-harness-front-door.sh   # `solar harness ...`
run "solar status"             check-solar-status.sh               # `solar status` truthfulness
run "status-server e2e"        smoke-status-server-e2e.sh          # install->doctor->dashboard backend->uninstall
run "solar update (offline)"   check-update.sh                     # `solar update`

# Dashboard /intake path: install once into the real HOME, POST /intake, assert the sprint record.
echo "::group::dashboard intake ($OS)"
if bash install.sh --yes --components kernel,harness --fake-keys --skip-llm-cli >/tmp/solar-ci-install.log 2>&1 \
   && bash scripts/ci-os-smoke.sh "$TASK"; then
  echo "PASS dashboard intake"
else
  echo "::error::FAIL dashboard intake on $OS"; tail -30 /tmp/solar-ci-install.log 2>/dev/null; fails="$fails intake"
fi
echo "::endgroup::"

if [ -n "$fails" ]; then echo "RED on $OS — failed:$fails"; exit 1; fi
echo "GREEN on $OS — full new-machine command battery passed (live LLM not run)."
