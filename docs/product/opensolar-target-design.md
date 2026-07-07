# OpenSolar Target Design — the shape of the changed system

**Date:** 2026-07-06 · **Stage:** D of R→D→I→C · Satisfies `opensolar-requirements.md` (R1–R9).
Design principle (owner/Sihao mandate): *complete* the baseline architecture in its own vocabulary —
requirement compiler, contracts, capsules, evidence gates. All new components are **additive**; the
execution core (dispatcher/scheduler/pool/routing) is consumed, not rewritten.

## 0. Flow (target)

```
intake text
  └─ ROUTER ──(trigger match)──► CONTRACT COMPILER ──► task_graph (dag_variant=<workflow_id>)
      │                              ▲ compile checks (R2) — reject = build error
      ├─(no match)──► PM/planner ──► PLAN VALIDATOR ──(errors)──► bounce to planner (≤2) ─► PLAN_COMPILE_FAILED
      │                              └─(clean)──► task_graph (dag_variant=pm.generic.v1)
      └─(unroutable)──► rejection artifact
task_graph ──► PREFLIGHT (routes/health/capacity/auth/paths) ──► existing pool dispatch
  each stage execution ──► route record (R5) + artifact MANIFEST (R6)
  each gate decision  ──► GATE LEDGER record (R4) ──► node status = projection
terminal ──► parent status truth (R7) ──► wrapper/dashboard read contract + ledger + manifest
```

## 1. New components (file-level)

### 1.1 Workflow contracts + compiler — `harness/lib/workflow_contract.py`
- Contracts: `harness/config/workflows/*.workflow.json`, schema `solar.workflow_contract.v1`
  (fields per `workflow-contract-schema.example.json`; that file's three contracts are the seed set).
- API (pure, stdlib+yaml only, no runtime imports):
  - `load_contract(path) -> Contract` (schema-validate; raise `ContractSchemaError`)
  - `compile_checks(contract, capsule_registry, operator_registry, provider_policy) -> list[CompileError]`
    — implements R2(a–d). `CompileError = {code, stage_id, message, admitted|declared|resolved}` with codes
    `TASK_TYPE_NOT_ADMITTED`, `OBLIGATION_UNSATISFIABLE_FOR_NODE_KIND`, `ARTIFACT_ROOT_UNRESOLVED`,
    `ROUTE_UNRESOLVABLE`.
  - `instantiate(contract, inputs: dict) -> dict` — emits the **existing task_graph format**
    (nodes with id/depends_on/logical_operator/task_type/capability_capsule_id/write_scope/
    proof_obligations/acceptance/evaluator_gate/dashboard_label/timeouts) + top-level
    `dag_variant=<workflow_id>`. Byte-identical for identical inputs (no timestamps inside; run ids
    injected by caller).
  - `match_trigger(text, env, requirement_type) -> workflow_id | None` — explicit markers +
    env gates + requirement-compiler type; generic words insufficient (R1/AC-R1.3).
- Node-kind legality table (R2b): `artifact|analysis|publish|verify` ⇒ `output_present`/acceptance/
  gate kinds only; `code` ⇒ may add `patch_diff`/`patch_within_scope`. Single source, exported for
  the plan validator.

### 1.2 Router at intake — `harness/solar-harness.sh` (+ thin shim `harness/lib/workflow_router.py`)
*(amended per review C1+C2)*
- Insertion point: the intake path immediately **before** `should_epic_decompose_request` — the
  generalization of the `f7febf00` bounded-mode bypass. Resolution order: explicit `workflow_id` →
  `match_trigger` → generic path → rejection.
- **Contract identity key:** contracts stamp a NEW top-level `workflow_contract_id` on the graph.
  `dag_variant` is NOT overloaded — it stays within its existing closed enum
  (`short|standard|parallel_spec|parallel_delivery|research`, consumed by the gate-backfill switches
  at `graph_scheduler.py:1194-1216` and `codex_pm_router.py:1234-1270`); contract instantiation
  emits a legal enum value (`research` for the research contracts) so gate backfill keeps working.
- Dispatcher guard: on graph load, if `workflow_contract_id` names a registered contract, verify
  the graph matches `instantiate()` output for that contract version (hash check). This guard is
  **net-new** dispatcher code (small, flag-gated) — the original `invalid_deepdive_dag_variant`
  guard exists only in the lisihao mirror / `upstream/codex/*`, not on this branch.

### 1.3 Plan validator (generic path) — `harness/lib/plan_validator.py`
- `validate_plan(task_graph, capsule_registry, operator_registry, provider_policy) -> list[CompileError]`
  — same checks/codes as 1.1, applied to planner output. Root normalization per `pm.generic.v1`
  contract policy (normalize-then-check for write_scope prefixes; AC-R2.2).
- Call site: where planner output is consumed and `planning_complete` is set (coordinator/pm path).
  On errors: write `<sid>.plan-compile-errors.json`, re-dispatch planner with errors appended
  (bounded, default 2), then terminal `PLAN_COMPILE_FAILED`. Env gate `SOLAR_PLAN_VALIDATOR=1`
  (default on in product mode).

### 1.4 Gate ledger — `harness/lib/gate_ledger.py` *(amended per review finding 3.1/5.1)*
- Storage: `sprints/<sid>.gate-ledger.jsonl` (append-only, atomic appends; same durability pattern
  as `node_runstate.py`, which this extends rather than replaces).
- Record: `{record_id, sid, node_id, kind: eval_verdict|auto_resolution|repair_start|repair_exhausted|
  human_verdict|gate_check|status_transition|route_record, author: {type: evaluator|doctor|policy|
  human|scheduler, operator_id?}, verdict?, verdict_kind: content|mechanical|infrastructure,
  eval_generation, repair_attempt, pm_task_id, evidence_snapshot_at, created_at,
  route?: {provider, model, operator_id, backend, exit_code, started_at, finished_at}}`.
  `kind: route_record` is appended per stage execution and is the storage for R5/AC-R5.1.
- **TWO choke points (amended per round-2 review F7):** (1) status transitions intercept at the
  **primitive** — `graph_scheduler.set_node_status` (:2359) becomes the single status writer and,
  under `SOLAR_GATE_LEDGER`, appends a `status_transition` record for every write; (2) **route/stage
  evidence intercepts at the operatord seam** — `operator_runtime.write_result` (and envelope-write
  at stage start) emits the `kind: route_record` ledger entry, because route facts are produced in a
  separate process and never pass through the scheduler; a run killed before reconcile must already
  have its route records (AC-R5.1). The other writers are routed or audited into it: `_mark_graph_node` (dispatcher :3848)
  delegates to it; the inline `node["status"]=` sites (incl. `dispatch_node_evals` :7902 and
  `node_verdict` :8215) are converted to calls; **`doctor_graph` (:2871) is neutralized on the
  contracted path** — its would-be writes become `author.type=doctor, gate_consumable=false`
  records, never direct status. AC-R4.3's property/audit test enumerates this full writer surface
  (the reviewer's C4 list) and greps for any residual direct write.
- `project_node_status(sid, node_id) -> status` — the projection (R4). Rank rules ported from
  `graph_scheduler._status_rank` but transitions exist only via records.
- Gate consumption: `parent_ready_check`/`mark_node_result`/`node_verdict`/
  `_reconcile_existing_dispatches`/`_start_node_repair_from_eval_fail` consult the ledger —
  locking the `5fcff602` verdict-content semantics and the `4df6477d` provenance rule structurally.

### 1.5 Artifact manifest — `harness/lib/artifact_manifest.py`
- `write_manifest(sid, node, generation, contract_stage|write_scope, roots) -> path` — called by the
  dispatcher at build-complete and repair-complete. Row: `{path, resolved_root, size, sha256, mtime}`
  + sidecar map (handoff/patch/guard/resource/eval[]) + `operator_result_ids`.
- Consumers: `_proof_artifact_presence` (replaces filename-shape scans), evaluator support-artifact
  block, wrapper artifact resolution (extends `1240285a` multi-root logic), publish step (canonical
  copy per contract `publish_rule`), dashboard deliverables list.

### 1.6 Preflight — `harness/lib/run_preflight.py` (+ CLI `solar-harness preflight-run`)
- Checks (R5/R7/R8/R2d): per-role route resolution under provider policy; operator health
  (backend CLI present, not deprecated/disabled, lease state via `operator_runtime.
  get_operator_runtime_state` — the single classifier, closing the status-server split-brain);
  live capacity (pool up or auto-startable); auth present per provider (existence/validity signal
  only — never reads token contents); harness path self-consistency (resolved `solar-harness`,
  `HARNESS_DIR`, `PYTHONPATH` inside the active tree — the `cb2cc504` class); contract compile if
  contracted. Output `sprints/<sid>.preflight.json`; fail-closed with remediation strings.

### 1.7 Fake-operator harness — `harness/tools/fake_operator.py` + `harness/tests/scenarios/`
- A `command`-backend operator (same seam codex uses) reading a scenario file:
  `{operators:[{id, role, provider}], script:[{match:{node_id?, role?, seq?},
  action:{write_files:{rel_path: content|@fixture}, exit_code, delay_s, result_status,
  eval_verdict?, verdict_kind?}}], faults:[die_after_transcript_before_result | duplicate_dispatch |
  late_eval_from_generation:N | drop_heartbeat | respawn_watchdog | write_outside_root | …]}`.
- Runner `harness/tests/run_scenario.py`: sandbox HARNESS_DIR, registers fake operators, drives
  intake→…→teardown, asserts expected terminal states/ledger records/classifications.
- **Scenario catalog = the taxonomy**: `scenarios/F-CLASS-01.…json` … `F-CLASS-30.…json` (mapping
  table in the implementation plan). CI job runs the whole catalog (P1.5 rung).

### 1.8 DeepDive router restore — `harness/lib/research/deepdive_requirement_compiler.py`
- **Primary source (updated 2026-07-06): `~/opensolar-state/lisihao-Solar-mirror` `main` @
  `e2480290` (2026-06-15)** — Sihao's own main now carries the DeepDive files MERGED (11 files:
  compiler, `deepdive_brief_expander.py`, profiles, plus design docs
  `harness/docs/deepdive-requirement-compiler-isolation.md` and
  `deepdive-insight-runtime-v2-cais-agent-insight.md` — read the isolation doc before porting).
  Cross-check against the `upstream/codex/*` refs in this repo (earlier variants). Ships with its
  own `test_deepdive_requirement_compiler.py` plus `research/profiles/`.
- Wrapped as contract `research.deepdive.rsi_demo` (compressed D1–D6 for the demo; faithful D1–D9
  as `research.deepdive.v1`). Artifact adapter `harness/lib/research/demo_artifact_adapter.py`
  maps native jsonl exports → the five demo artifacts. Synthesizer stage uses the builder-authored
  path for the demo (F-055 boilerplate bypass), engine synthesis behind a later flag.

### 1.9 Run process registry — `harness/lib/run_process_registry.py` (Lane 0.5)
- `register(run_id, role, pid)` on every daemon spawn (status-server, coordinator, watchdog,
  operatord, drivers) → `run/process-registry/<run_id>.jsonl`; `teardown(run_id)` kills by registry,
  watchdog-first, verifies exit; `mark_terminal(run_id)` — watchdog checks it before any respawn.
  Wrapper cleanup and ladder cleanup-gates call `teardown`.

### 1.10 Wrapper/dashboard consumption
- `scripts/live_codex_epic_status.py --contract <path>`: expected artifacts/roots/terminal states/
  validator command derived from the contract (existing producer-completion + stability + multi-root
  logic retained as defense in depth).
- `status-server.py`: `GET /api/sprints/<sid>/contract` (read-only: contract + per-stage
  ledger-projected state + manifest links). No other dashboard change.

## 2. Changed behavior (small, enumerated)

1. Intake resolution order (1.2). 2. `needs_human_review` leaves the global
`DEPENDENCY_BLOCK_STATUSES` on the contracted path; blocking is per-stage `on_human_review`
(`block_dependents` default for code contracts, `warn_and_continue` for bounded research). 3. Product
mode (`SOLAR_PRODUCT_MODE=1`): pane dispatch disabled — pool-submit failure ⇒ terminal blocked node
with reason. 4. Status writes on the contracted path go through the ledger projection (legacy path
shimmed, unchanged behavior). 5. Plan artifacts rename `selected_operator_id` →
`suggested_operator_id` (reader tolerates both); `host_type` reflects actual backend.

## 3. Config changes (spine — Lane 0)

- `harness/config/physical-operators.json` (shipped default): enabled = `mini-claude-*` +
  `mini-codex-*` (verified healthy); `gemini/glm/antigravity/thunderomlx/browser/deepseek/local`
  entries `enabled:false`. Provider labels corrected (the codex-tagged-anthropic entries).
- `operator-model-selections.json` removed from shipped config (dead config, G8).
- `solar-user-config.json` model aliases: bare `sonnet` resolves Anthropic or preflight-fails (R8/AC-R8.3).
- Env gates introduced: `SOLAR_PRODUCT_MODE`, `SOLAR_PLAN_VALIDATOR`, `SOLAR_GATE_LEDGER`
  (all default on in product mode, off for legacy compatibility until P2 passes).

## 4. Explicitly unchanged *(re-scoped per review 3.1/C1)*

**No rewrite** of `graph_scheduler.py` / `graph_node_dispatcher.py` (all ~20 rc8 fixes retained) —
but "unchanged" does NOT mean untouchable: the design makes **narrow, flag-gated interceptions at
named primitives** (`set_node_status` choke point, `doctor_graph` neutralization, the
`workflow_contract_id` guard, the per-node human-review policy consult), each individually testable
and each off when its flag is off. Truly unchanged: `operator_runtime`/`operatord`/`pm_dispatch`
dispatch machinery; provider-routing selector logic; dashboard UI; installer/wizard (Lane 6 owns
artifact testing); the research engine internals (`state_machine.py`, `eval-artifacts`); capsule
YAML contracts (consumed as-is — capsules become the admission authority, unmodified).

## 5. Failure-class cross-reference

Compiler+router: 01–05, 07, 16(compile-half), 19(alias-half) · Ledger: 09, 10, 12, 13, 29, 30 ·
Manifest: 06, 16, 21(artifact-half) · Preflight: 18, 19, 20, 21, 27 · Route records: 17, 18 ·
Supervision+registry: 22, 28, truth items under R7 (incl. AC-R7.5 busy-singleton bound, the owning
AC for 08's misclassification) · Fake-operator harness: **29 scenario classes at P1.5 + F-CLASS-22
at the non-hermetic P1.6 tier + F-CLASS-24 delegated to Lane 6** (corrected per review 1.1) · Spine
config: 08(partly), 19, 27, pane classes. Full per-class verdicts:
`opensolar-plan-coverage-matrix.md`; review dispositions: `opensolar-spec-review-dispositions.md`.
