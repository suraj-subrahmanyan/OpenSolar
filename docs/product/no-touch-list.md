# No-Touch List — What NOT to Change Yet, and Why

**Date:** 2026-07-06. Scope: the workflow-contract refactor (Phases 0–6 of
`workflow-contract-unification-plan.md`). Each entry cites the corpus evidence for why touching it now
would repeat a known failure pattern.

## 1. No massive dispatcher/scheduler rewrite
`graph_node_dispatcher.py` and `graph_scheduler.py` absorbed ~20 hard-won, live-informed fixes between
06-28 and 07-03 (generation fencing, dependency terminalization, patch-proof pipeline, PM-task
correlation, sticky guards). Most are deterministic-test-locked but several are **not live-revalidated**
(live repair loop, sticky path `8f05dfb7`). A rewrite would discard exactly the knowledge this corpus
exists to preserve and reset every "yes" in the commit-fix map's revalidation column to "unknown."
The contract compiler *emits into* the existing graph format; it does not replace the executors.

## 2. No provider-routing changes unless the contract requires them
The route chain (`94922d9a` → `8ad8cfb2` fail-closed → `154a1d48` aliases → route proof `2db50662`) just
reached its first green states (`a8203924` clean run, `cd528d0a` smoke, and separately the RSI v4/v9
OpenAI-only runs). Memory `project-goals-v1-release-scope` also marks provider plumbing as
release-scope, not refactor-scope. The contract layer *consumes* `provider_policy`; it must not alter
selector logic. Known residuals (plan-artifact route lies F-031, `host_type` label, N/A attribution
F-033) are observability cleanups scheduled after the contract lands, not prerequisites.

## 3. No setup-wizard merge into the runtime branch yet
`feature/setup-wizard` is **10 commits behind upstream with 0 ahead** and its diff "removes or changes
parts of desktop bootstrap tests/main/dashboard assets" (branch-regression-matrix). The smoke review's
own recommendation: rebase/replay it in a separate worktree and add a server-side setup gate first.
Entangling it with the contract work would couple the two highest-churn surfaces in the repo.

## 4. No dashboard redesign before the workflow contract exists
The overhaul (`feat/dashboard-overhaul`, 8 commits, gates green) already fixed legibility. The
remaining dashboard problems are **truth** problems (stale parent status F-032, usage=0 F-016,
operator split-brain P0-4), and their correct fix is "render the contract/ledger" — which cannot be
built before the contract exists. A redesign now would encode a third generation of guesses.
Owner memory is explicit: "Do NOT edit dashboard" on the runtime lanes.

## 5. No full epic runs before a bounded workflow lock is green
Every epic attempt on record wedged or misdecomposed (paperfilter, local-research-report S01, the
06-30 live web epic). Epics multiply each unresolved class by the child count and burn 30+ minutes per
sample. Ladder order is P3 (bounded contract) → P5 (epic). The S01 wedge fix (`8341fc5a`) is
deterministic-only; its first live exercise should happen *inside* a contracted run, not another
uncontracted epic.

## 6. No live web before the Resource Radar contract
The one live-web attempt (2026-06-30) never reached a single web fetch — it died in decomposition.
Live web adds network nondeterminism and fabrication risk on top of every unresolved class; the
Resource Radar contract's P6 rung (fetch log + citation-existence validator + honest blocker mode) is
the only sanctioned entry. Until then, seed packs only.

## 7. No edits to the installed `~/.solar/harness` as part of this refactor
The installed copy is live product state (owner cockpit) and has repeatedly contaminated proofs
(F-029) and been clobbered by sync scripts (memory: `sync-harness-runtime.sh` clobbers model config).
Contract work happens in worktrees; installation of contract-bearing builds is a release action, not a
refactor side effect.

## 8. No registry/model surgery beyond what preflight needs
`physical-operators.json` hygiene (mislabeled providers, enabled-deprecated entries, dead
`operator-model-selections.json`) is a real problem (G7/G8) but it is **runtime-state-entangled** —
the file is listed among "generated dirt do not stage" in the RC8 handoffs, and cooldown state lives
in it. Fixing it mid-refactor risks exactly the "manual config edit to rush a test" the 06-30 session
explicitly refused. Separate track, with the health-is-source-of-truth design from the gap register.

## 9. No new demo-mode conditionals in engine code
The bounded-demo fixes accumulated 6 `SOLAR_DEMO_REPORT_MODE` gates inside dispatcher/capsule code.
They were the right emergency move; they are also exactly the per-site patching the contract replaces.
Freeze the count: new behavior differences must come from contract fields, not new env-flag branches.

## 10. No cleanup "while we're here" of runtime dirt in working trees
`.pm/*`, coordinator markers, generated task files (`uniqwords.py`, `countletters.py`, `utils.py`,
`special_breakdown_document.md`) are evidence and/or live state. The SessionEnd auto-commit hook plus
a broad cleanup is how work has been destroyed before (memory:
`no-destructive-git-with-uncommitted-work`). Contamination gets fixed by the run-scoped process
registry and root-containment preflight (contract Phase 3/4), not by ad-hoc deletion.

## Explicitly IN scope (for contrast)
New, additive, test-first code only: `workflow_contract.py` (schema + compiler + preflight checks),
contract JSON files, the DeepDive router port, the artifact adapter, `validate_resource_radar.py`,
and wrapper `--contract` consumption. Everything else waits for its phase.
