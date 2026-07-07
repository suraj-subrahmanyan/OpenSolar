# Runtime Validation Ladder

**Date:** 2026-07-06. Rule extracted from ~25 live runs in the failure corpus: **live runs are the
most expensive and least informative way to find contract bugs** — every rung below P2 catches a class
that some live run in June/July 2026 burned hours (and quota) discovering. A workflow, fix, or release
claim is only allowed to cite the highest rung it has actually passed; each workflow contract declares
its `release_proof_level` = the rung it must pass before its capability is claimable.

## The levels

### P0 — Deterministic unit tests
Pure-code tests, no harness state, no processes, env pinned to the worktree
(`HARNESS_DIR`/`SPRINTS_DIR`/`PYTHONPATH` — unpinned tests imported the installed harness and produced
6 false failures; corpus F-029). Includes the contract compiler checks: task_type admission,
obligation satisfiability, root containment, byte-identical instantiation.
*Gate:* all new tests green; pre-existing reds identical with the change stashed (the "IDENTICAL
failing set stash-proven" discipline from the RSI chain).

### P1 — Preserved-evidence replay
The fix is run against **real preserved run artifacts**, not fixtures: Run-D graph replay proved the
eval escalation (`run-E`); v5's archived eval sidecar drives the mechanical-vs-content predicate;
v8's mid-draft workspace drives the timing gate; v9's workdir drives root resolution. New rule from
the /tmp wipe: preserved bundles **must live under `~/opensolar-state/`** (or another durable root),
never `/tmp` — every v1–v9 raw bundle was lost to a reboot; only committed diagnoses survived.
*Gate:* the failing run's evidence now produces the fixed behavior through the real code path.

### P1.5 — Fake-operator full-pipeline simulation (the primary testing engine)
**This rung is the answer to "how do we test without continuously running live runs."** A
deterministic `fake-operator` backend stands in for every LLM operator: given a dispatch for node X
it writes scripted artifacts, exit codes, delays, and eval verdicts from a scenario file. The ENTIRE
pipeline — intake → PM → planner-output injection → admission → dispatch → lease → build → eval →
repair → closeout → wrapper validation — executes in seconds, with zero quota, fully parallelizable
(the single-threaded rule binds LIVE runs, not simulations). A CI-safe fake-operator path already
exists in the rc6 install-matrix work — this rung generalizes it into a scenario harness.

**The taxonomy is the fault catalog.** Every failure class in
`opensolar-failure-taxonomy.json` gets at least one scenario that reproduces it deterministically:
zero evaluators (Run D's 246-retry), busy singleton evaluator (v2/v10 contention), late pre-repair
eval (stale-generation race), operator dies after transcript before result.json (stale lease),
duplicate repair dispatch, artifact written to workdir vs workspace (v9), admission rejection →
must NOT pane-fallback (v1), mechanical vs content eval FAIL (v5), mid-draft artifact while
producer active (v8), watchdog respawn during teardown. A fix is not done until its class's
scenario passes; a new class is not closed until it has a scenario.

Complementary offline layers at this rung:
- **Property/state-machine tests:** enumerate node statuses × events × generations and assert
  invariants (terminal states absorbing; no status downgrade without a ledger record; every active
  dispatch carries a live heartbeat; blocked ⇒ some dependency terminal). These catch the
  direct-write/race family wholesale instead of one instance at a time.
- **Recorded-LLM replay (VCR):** where realistic model output matters, replay captured operator
  transcripts/artifacts from archived runs instead of calling a model.
- **Auto-archival rule:** every live run (any rung) preserves a replayable bundle under
  `~/opensolar-state/run-archive/` at teardown — live runs continuously feed P1/P1.5 fixtures, so
  each expensive run makes future testing cheaper.

*Gate:* full taxonomy scenario suite green + property suite green, in CI, no network, no quota.

### P2 — Isolated smoke (single sprint, clean sandbox) — **once per shipped provider**
`scripts/live-codex-e2e-isolated.sh` style: fresh worktree/harness copy, no pre-existing task files,
auth preserved, bounded timeout, full teardown check. One small known-shape task (the
`code.cli_smoke` contract). Provider route proof required; "dirty worktree" runs count only as
diagnostic evidence, never as product proof (the `204f7cfd` lesson).
**The product ships two selectable runtimes (Claude CLI and Codex), so this rung runs twice: one
Codex-only pass (exists: `cd528d0a` smoke `c42d1e2f`, clean run `ab795810`) and one Claude-only
pass on the SAME runtime commit (does not exist yet — Run H was on the June-28 lane, stale for the
rc8 contract runtime; arch-audit P1-1).** Contracts are provider-parametric via `provider_policy`;
the same contract file must pass under both policies before either mode is claimable.
*Gate:* terminal `passed` (or clean classified failure), route-proof ok for the selected provider
with zero cross-provider records, no process residue, worktree clean.

### P3 — Bounded product workflow (the locked contract, offline)
One full contracted workflow (RSI DeepDive lock with seed pack) end-to-end with **zero manual
driving**: trigger → fixed DAG → gates → artifacts → publish → validator PASS. This is the rung the
RSI demo chain (v1–v10) was trying to reach through the generic path and never did; under the lock it
is the first live target.
*Gate:* all required artifacts present + valid, gate ledger complete, route proof complete,
self-terminalized, wrapper reports PASS from the contract.

### P4 — Dashboard-initiated workflow
Same as P3 but started from the dashboard intake (not the wrapper), with the UI showing contract
stages/gates truthfully and the parent status projection reaching terminal (the `a8203924` stale-parent
bug is a P4 blocker, not a P3 blocker).
*Gate:* dashboard shows the run start→terminal without contradiction; deliverable openable from the UI.

### P5 — Full epic / multi-sprint
Epic-shaped work (genuinely large tasks, or the `pm.generic.v1` contract) with child observation via
the epic-status wrapper. Only after at least one contract workflow holds at P3/P4 — the corpus shows
epics multiply every unresolved class by the child count (F-037, F-039).
*Gate:* epic self-advances children; wedges classify within their timeout budget; terminal epic status
is truthful.

### P6 — Live web / Resource Radar
Network-enabled research (`SOLAR_ALLOW_LIVE_WEB=1`) under the Resource Radar contract: real fetches,
fetch log as evidence, citation-existence validation, honest blocker reports when the web step fails.
This is deliberately the top rung: it compounds every lower-rung risk with network nondeterminism.
*Gate:* validator confirms every cited source was actually collected; no fabricated sources; route +
fetch evidence archived durably.

## Ladder discipline (from hard-won corpus lessons)

1. **One rung at a time, one new variable per live run.** The 06-29 chain ran live E2E after nearly
   every commit; the arch audit's own conclusion was "Stop running new prompts. Centralize contracts.
   Test contracts deterministically. Then run small live proofs."
2. **A failed rung stops the ladder** — record the first root cause, fix at P0/P1, re-climb. No
   "rerun and hope" (the no-rerun rule from the RSI chain).
3. **Claims cite rungs.** "Codex-only works" ⇒ P2 pass (`cd528d0a` smoke). "The demo works" ⇒ P3.
   "Users can run it" ⇒ P4. Nothing about P6 may be claimed from P3 evidence. The corpus's
   over-claiming incidents (pools "stopped" that weren't; "blocked" that was slow opus) all came from
   skipping this.
4. **Bounded waits with evidence, not impatience:** slow ≠ stuck (Run H's opus eval, ~8 min). Every
   wait has a budget and a classification marker when exceeded.
5. **Cleanup is part of the rung:** a rung does not pass if coordinator/watchdog/operator residue
   survives teardown (F-CLASS-22 — still the most chronic hygiene failure).
