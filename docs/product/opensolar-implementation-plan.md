# OpenSolar Implementation Plan — lanes, tests, gates

**Date:** 2026-07-06 · **Stage:** I of R→D→I→C · Executes `opensolar-target-design.md` against
`opensolar-requirements.md`. Planning assumptions per owner: implementation effort is cheap and
parallel (AI-speed dev); the plan optimizes **verification bandwidth, spec quality, owner attention,
and disjoint-files lane discipline** — no human-time estimates. Live runs are confirmation, never
discovery (`runtime-validation-ladder.md`).

## 0. Ground rules

- **Base branch:** `integration/rc8-runtime-mode-contract` (carries the hardened runtime the
  contracts run on). New branch per lane, e.g. `contract/lane1-compiler`. Local `pkg/migration` is
  stale — do not base on it.
- **Every PR = code + its deterministic tests + its taxonomy-scenario coverage.** A live failure is
  converted to a fixture before its fix merges (debug the recording, never the live system).
- **Lane discipline:** lanes touch disjoint files (listed per lane); my own sessions stay
  single-threaded on harness work; parallelism = the owner's Claude/Codex lanes.
- **Serialized-files rule (added per review 6.1):** three files are single-owner regardless of
  which lane's feature needs them: `harness/solar-harness.sh` edits land **once via Lane 0** as thin
  stubs calling lane-owned modules (product gate, registry teardown hook, intake-router hook);
  `harness/lib/graph_scheduler.py` and `harness/lib/graph_node_dispatcher.py` edits are **owned by
  Lane 3 exclusively** — Lane 1's `workflow_contract_id` guard and the per-node human-review policy
  consult are *scheduled as Lane 3 items* even though they serve Lanes 1/0.
- **Flags:** every behavior change behind its env gate (design §3), default-on only in product mode,
  so legacy behavior is bit-preserved until P2 passes.
- **Evidence:** all run bundles under `~/opensolar-state/run-archive/` — never `/tmp`.
- **No pushes/tags/releases** without explicit owner request. Repo staging: explicit paths only.

## 1. Step zero — adversarial spec review (before any code)

Hand `opensolar-requirements.md` + `opensolar-target-design.md` + this plan to the **Codex lane**
with the review checklist (§6). Disposition every finding (accept/fix/reject-with-reason) before
Lane 1 starts. Targeted external prior-art scan happens here if a finding needs it (durable-execution
ledgers, workflow-DAG schemas) — half a day, scoped to open questions only.

## 2. Lanes

### Lane 0 — Spine config *(amended per review 6.1/7.2)*
- **Files:** `harness/config/physical-operators.json` (shipped default), `harness/config/solar-user-config.json` aliases, remove `operator-model-selections.json` from shipped set, **all `solar-harness.sh` stub insertions** (product-mode pane gate + registry teardown hook + intake-router hook — thin calls into lane-owned modules, one PR).
- **Moved out:** the human-review dependency-policy change is NOT a Lane 0 one-liner — `DEPENDENCY_BLOCK_STATUSES` is a process-global (graph_scheduler.py:43); the fix is a per-node `on_human_review` policy consult in the skip-propagation loop, **owned by Lane 3**.
- **Tests:** preflight-style unit tests (disabled operators unselectable; bare-`sonnet` resolution; product-mode submit-failure ⇒ terminal blocked node, no pane fallback).
- **Gate (re-scoped per round-2 review F8):** P0 green + no diff in legacy-mode behavior **for
  flag-gated code paths**. Shipped-default **config** changes (registry allowlist, neutralized
  user-config) are deliberate product changes under R8/mandate — they are the spine, not a
  regression, and are exempt from the bit-preservation clause. Local re-enablement remains possible
  (gating, not deletion).
- **Owner decision embedded:** add the second OpenAI evaluator entry here (yes/no). *(Decided: yes, landed `048b4e56`.)*
- **PR-3 (due — F4):** wire the Lane 0.5 interfaces now that they exist: registry teardown hook in
  the wrapper/stop path, `preflight-run` stub at intake, watchdog `is-terminal` gate in
  `coordinator-watchdog.sh`; M1 rule = resolve active sid at the call site, fail-open to global
  watchdog behavior when none resolves.

### Lane 0.5 — Supervision + preflight *(renamed; absorbs the ownerless component from review 6.1)*
- **Files:** new `harness/lib/run_process_registry.py` + new `harness/lib/run_preflight.py` (+ CLI);
  call sites in `coordinator-watchdog.sh` (terminal-marker check) and wrapper cleanup in
  `live-codex-e2e-isolated.sh` (its `solar-harness.sh` hook lands via Lane 0's stub PR).
- **Tests:** preflight scenarios 20/27 (auth-absent, no-capacity fail-closed); registry survives
  crash; idempotent teardown. Real-daemon teardown proof (incl. watchdog-respawn) runs at the
  **non-hermetic P1.6 tier** (spawns real processes; still no models/network).
- **Gate:** P1.5 logic scenarios + P1.6 teardown green; every later rung's cleanup gate uses it.

### Lane 1 — Contract schema + compiler + plan validator *(amended per review 6.1/C1+C2)*
- **Files (all new):** `harness/lib/workflow_contract.py`, `harness/lib/workflow_router.py`,
  **`harness/lib/plan_validator.py`** (previously ownerless — same compile-check core),
  `harness/config/workflows/{research.deepdive.rsi_demo,code.cli_smoke,pm.generic.v1}.workflow.json`.
  The `solar-harness.sh` intake hook arrives via Lane 0's stub; the **`workflow_contract_id` guard**
  (net-new dispatcher code — `dag_variant` is NOT overloaded, it stays in its closed enum) is
  scheduled as a Lane 3 item per the serialized-files rule.
- **Tests (mandatory list):** the 11 deterministic tests from `rsi-demo-stage-contract.json`
  generalized (schema-valid; variant guard; no-impl-capsule/no-patch_diff on research stages;
  byte-identical twice; trigger matches RSI prompt / rejects generic words; every task_type
  capsule-admitted; obligations resolve by node_kind; roots contained; route resolvable) **plus the
  two rejection replays: preserved v7 graph → `OBLIGATION_UNSATISFIABLE_FOR_NODE_KIND`; preserved v9
  graph → `ARTIFACT_ROOT_UNRESOLVED`** (AC-R2.1/2.2), plus the four historical admission shapes (AC-R2.3).
- **Gate:** P0 + P1 (replays) green. No runtime wiring beyond the intake hook behind its flag.

### Lane 2 — Fake-operator scenario harness (the testing engine; highest leverage)
- **Files (all new):** `harness/tools/fake_operator.py`, `harness/tests/run_scenario.py`,
  `harness/tests/scenarios/F-CLASS-01…30.scenario.json`, CI job.
- **Scenario↔class mapping (the fault catalog — corrected per review 1.1/4.x/9.1):** 01
  shape-goldens · 02/03 router · 04 admission reject-no-fallback · 05/07 obligation legality ·
  06 manifest discovery · 08 busy-singleton bounded-wait+classification (AC-R7.5) + zero-evaluator
  (Run-D 246) · 09/10 v5 mechanical-FAIL replay · **11 parseable-but-stale closeout is FAILED by the
  content gate (true-positive preserved)** · 12 duplicate-repair/single-flight · 13
  late-eval-from-old-generation · 14/15 wrapper contract + producer-completion mechanism (the 18 ms
  race itself = preserved v8 replay at P1) · 16 workdir-vs-workspace (v9) · 17 kill-mid-run route
  records · 18 cross-provider record ⇒ fail-closed · 19 disabled-operator unselectable · 20
  auth-absent preflight · 21 installed-fallback + write-outside-root · 23 parent-status truth
  (`a8203924` shape) · 25/26 validator token/wording · 27 no-live-capacity preflight · 28 wedge
  timeout classification (S01, v10 shapes; timeouts injected via the `SOLAR_*_TIMEOUT_SEC*` env
  knobs so scenarios run in seconds) · 29 critic-block-vs-node-passed (LDES shape) · 30
  backfilled-eval non-consumable. **= 29 hermetic classes; F-CLASS-22 (real process death) runs at
  the non-hermetic P1.6 tier; F-CLASS-24 is delegated to Lane 6's install rung.**
- **Gate:** full hermetic catalog green in CI, no network/quota (P1.5 rung exists from here on);
  P1.6 = the real-daemon teardown tier (real processes, still no models/network).

### Lane 3 — Gate ledger + artifact manifest (contracted path)
- **Files:** new `harness/lib/gate_ledger.py`, `harness/lib/artifact_manifest.py`; integration
  touch-points in `graph_node_dispatcher.py` (`node_verdict`, `_reconcile_existing_dispatches`,
  `_start_node_repair_from_eval_fail`, `_proof_artifact_presence`) and `graph_scheduler.py`
  (`parent_ready_check`/`mark_node_result` verdict-content consult) — **behind `SOLAR_GATE_LEDGER`,
  additive, legacy shims preserved**.
- **Tests:** AC-R4.1–4.4 scenarios/replays (v5 sidecar, LDES shape, thin-eval, stale-generation,
  PM-task correlation); property suite (no transition without record; terminal absorbing); manifest
  cases AC-R6.1–6.3.
- **Gate:** P1 + P1.5 green; graph suite pre-existing reds identical stash-proven.

### Lane 4 — DeepDive router port + RSI contract + adapter *(amended per review 9.1a/C3)*
- **Step 1 (before any Lane-4 test exists): VENDOR the DeepDive source into the repo** — commit
  `deepdive_requirement_compiler.py` + `deepdive_brief_expander.py` + `research/profiles/` + its
  tests, ported from the mirror's `main` @ `e2480290` (primary; read
  `harness/docs/deepdive-requirement-compiler-isolation.md` there first) cross-checked against
  `upstream/codex/*`, with a parity report in docs. **No CI gate may depend on the external mirror.**
- **Files:** the vendored research router + new `harness/lib/research/demo_artifact_adapter.py`;
  contract file already in Lane 1.
- **Tests:** ported compiler tests; adapter produces 5 demo artifacts from native fixtures and
  `validate_rsi_demo_report.py` passes; `eval-artifacts` good/bad fixtures; D-graph golden.
- **Gate:** P1.5 research scenarios green → **P2 ×2 providers** (codex first; claude-only on the same
  commit — the missing rung) → **P3: ONE bounded RSI demo run, zero manual driving** → decision gate
  (record demo / Track A unblock).
- **Prereq flags:** synthesizer stage = builder-authored path (F-055); evaluator-count decision from Lane 0.

### Lane 5 — Wrapper + dashboard contract consumption *(amended per review 7.1)*
- **Files:** `scripts/live_codex_epic_status.py` (`--contract`), `status-server.py` (one GET route),
  plan-artifact `suggested_operator_id`/`host_type` relabel (R5) — **gated behind
  `SOLAR_PRODUCT_MODE`: flag-off emits the legacy field names bit-for-bit**.
- **Tests:** wrapper derives expectations from contract (v8/v9 replays still green); endpoint smoke.
- **Gate:** P1.5 + P4 (dashboard-initiated run) after Lane 4's P3.

### Lane 6 — Installer acid tests (fully independent, owns R10/F-CLASS-24)
- Per-OS clean-machine artifact tests per the gap register (G1/G2/G5/G15). Shares no files with
  Lanes 0–5; schedule whenever machines are available.

## 3. Join order and live-run budget

`Lane 0 + 0.5 + 1 + 2` in parallel (Lane 0's stub PR merges first; module lanes hang off it) → join
at P1.5 (hermetic catalog) + P1.6 (real-daemon teardown) → `Lane 3` → `Lane 4` P2 (two live smokes,
one per provider, auto-archived) → P3 (one live bounded demo) → `Lane 5` P4 (one dashboard-initiated
run). **Total planned live runs: 4** (plus 2-minute micro-probes ad lib). Any live failure → fixture
first, fix second, no re-run until its scenario passes.

**P3 validity precondition (added per review 10.1, verbatim from the reviewer):** *P3 counts as
evidence only if the Lane 2 catalog is green AND Lane 3's verdict-content + provenance rules are
active.* A green P3 without those is a hollow pass (F-CLASS-29/30 could be satisfying the gate) and
does not advance any claim.

## 4. Decision gates (owner attention points)

1. Second OpenAI evaluator entry (Lane 0) — recommended yes.
2. Spec-review findings disposition (§1).
3. After P3: record the demo (Track A) now, or proceed to Lane 5 first.
4. After P4: next contract = Resource Radar (P6 path) vs generic-path adoption (Phase 6) — data from
   the P2–P4 runs decides.

## 5. Definition of done (per lane and overall)

Lane-done = its tests green + its taxonomy scenarios green + pre-existing-red baseline unchanged
(stash-proven) + docs updated (`coverage-matrix` verdicts flipped with evidence links). Overall-done
for this phase = P4 pass + coverage matrix shows the 23 SOLVED classes verified at their named rungs
+ no new failure class discovered (if one is: targeted evidence gathering reopens for that class only).

## 6. Adversarial review checklist (for the Codex reviewer)

1. Find a failure class in `opensolar-failure-taxonomy.json` this design does NOT retire or track.
2. Find a compile check that can pass while the runtime still hangs (gap between R2 and dispatch).
3. Find a ledger write path that bypasses projection (grep for direct `node["status"]=`).
4. Find a scenario the fake-operator seam cannot express (TUI-only behavior? timing finer than file mtimes?).
5. Find a contract field the wrapper/dashboard needs but the schema lacks.
6. Find a lane file-collision (two lanes touching one file).
7. Find a place the design silently changes legacy (flag-off) behavior.
8. Find a Sihao-architecture concept this replaces rather than completes (mandate check).
9. Find a live-run dependency hidden in a P0–P1.5 gate.
10. Propose the smallest cut that would still pass P3 (scope discipline).
