# Workflow Contract Unification Plan

**Date:** 2026-07-06. Design document — no runtime code is changed by this plan.

> **Mandate update (2026-07-06, owner + Sihao):** "making it work" explicitly outranks staying
> faithful to the original baseline. This authorizes the surface cuts in §8 (added below) that
> earlier drafts kept conservative: single execution path, allowlisted shipped registry,
> gate-policy change for human-review blocking, epic-off-by-default for small tasks. The product
> promise is restated as: **every prompt gets a correct route — locked workflow, validated generic
> DAG, or honest rejection — on a spine of components proven to work on a stranger's machine.**
> "All components work for any prompt" is explicitly NOT the promise.
Companion schema with three worked contracts: `workflow-contract-schema.example.json`.
Precedent inside the codebase: `docs/product/rsi-demo-stage-contract.json` on
`feat/rc8-demo-golden-path` (the RSI lock), and the original `deepdive_requirement_compiler.py`
in lisihao/Solar (the dropped router). This plan generalizes those two into one layer.

## 1. What the contract layer is

A **workflow contract** is a versioned, machine-readable document that fully determines a run
*before any LLM is invoked as planner*. A small **contract compiler** turns it into the existing
task-graph format; the existing dispatcher/scheduler/evaluator execute it. The compiler is new code;
the executors are not rewritten (see `no-touch-list.md`).

Three invariants define the layer:

1. **One authority.** Every fact the five current authorities negotiate at runtime (stage list,
   capsule, task_type, outputs, proof obligations, gates, artifact roots, providers, labels) is
   written once in the contract and consumed read-only by everyone else — planner, dispatcher,
   capsule admission, evaluator, wrapper, dashboard.
2. **Compile-time satisfiability.** The compiler rejects a contract (never emits a graph) if any
   stage's `task_type` is not admitted by its capsule, any proof obligation references an artifact
   not in the stage's declared outputs or gate inputs, any artifact path escapes the declared roots,
   or any stage's role cannot resolve to a healthy operator under the provider policy. This turns the
   four F-CLASS-04 runtime hangs, the v7 unsatisfiable patch obligation, and the v9 root divergence
   into build failures.
3. **Byte-identical instantiation.** Same contract + same inputs → same task graph, every run.
   Planner nondeterminism (F-CLASS-01) is removed for contracted workflows, not mitigated.

The LLM planner is not deleted: it remains the path for genuinely novel tasks (an explicit
`workflow_id: pm.generic.v1` contract that declares "planner-generated stages"), and it can be used
*inside* a stage (e.g., chapter planning) where its output is content, not orchestration.

## 2. Contract fields (the unified vocabulary)

Per workflow:

| Field | Meaning | Failure class it retires |
|---|---|---|
| `workflow_id`, `version` | stable identity; dashboards and KB key on it | run-to-run incomparability |
| `trigger` | explicit markers + env gates + requirement-compiler type that route intake here; modeled on `is_explicit_deepdive_request` (generic words deliberately insufficient) | F-CLASS-02/03 |
| `provider_policy` | runtime, `allowed_providers`, route-proof requirement, per-stage overrides | F-CLASS-18 |
| `artifact_roots` | canonical root, allowed aliases, export/publish rule (workdir → canonical) | F-CLASS-16 |
| `stages[]` | the fixed DAG (below) | F-CLASS-01 |
| `validator_command` | the deterministic end-to-end validator the wrapper runs | F-CLASS-14/15 half |
| `release_proof_level` | which rung of the validation ladder this workflow must pass to be claimable (see `runtime-validation-ladder.md`) | over-claiming |

Per stage:

| Field | Meaning | Failure class it retires |
|---|---|---|
| `id`, `depends_on`, `gate_family` | fixed topology | F-CLASS-01 |
| `node_kind` | `artifact` \| `code` \| `analysis` \| `verify` \| `publish` — drives which proof template is legal | F-CLASS-05/07 |
| `logical_operator` | the named worker concept (e.g. `DeepDiveSourceCollector`) | role/type conflation (F-044) |
| `task_type` | THE dispatch task_type, written once, compile-checked against the capsule | F-CLASS-04 |
| `allowed_capsules` | explicit; `forbidden_capsules` optional (RSI lock forbids `cap.requirement-compiler-implementation` on report stages) | F-CLASS-05 |
| `allowed_operators` / role | physical resolution constraint, checked against health at preflight | F-CLASS-19/27 |
| `outputs[]` | declared artifacts with types; the per-node artifact manifest is generated from this | F-CLASS-06 discovery half |
| `proof_obligations[]` | only `output_present`/acceptance/gate kinds legal for the stage's `node_kind`; `patch_diff` legal only on `code` stages | F-CLASS-05/06/07 |
| `evaluator_gate` | kind (`deterministic_command` \| `llm_eval` \| `none`), capacity requirement, wait-vs-escalate policy, and `on_human_review: block_dependents | warn_and_continue` | F-CLASS-08/09/10 |
| `route_proof` | emit-per-execution record (provider/model/operator/exit), not assembled by a terminal node | F-CLASS-17 |
| `dashboard_label` | what the UI shows; the UI renders the contract, not heuristics | F-CLASS-23 projection half |
| `timeouts` | stage liveness budget + escalation classification (`ORCHESTRATION_WEDGE_NOT_PRODUCT_PROOF`) | F-CLASS-28 wedges |

## 3. Runtime semantics the contract requires (small, targeted changes)

These are the only executor-side changes the plan needs, each already prototyped somewhere in the
fix history:

1. **Router at intake.** Before `should_epic_decompose_request`, match triggers against registered
   contracts; on match, instantiate the contract's graph (`dag_variant=<workflow_id>` guard, exactly
   like `deepdive_research`). Prototype: `f7febf00`'s bounded-mode bypass + the original compiler.
2. **Gate ledger, not status writes.** Gate outcomes (eval verdicts, auto-resolutions, repairs) are
   append-only records carrying `eval_generation`, `pm_task_id`, `verdict_kind`
   (`content|mechanical|infrastructure`), and `evidence_snapshot_at`; node status becomes a
   projection. Prototypes: `714eb781` generation stamps, `8f05dfb7` marker-authority,
   `62e0c9ac` runstate ledger. This retires the direct-write clobber class permanently.
3. **Per-node artifact manifest.** Dispatcher writes the manifest after build/repair from the
   contract's `outputs[]`; proof/eval/wrapper read the manifest. Prototype: the "no-more-random-runs
   plan" item 1 in `RC8-RUNTIME-AUDIT-HANDOFF-20260630.md`.
4. **Preflight = contract check.** The existing route preflight extends to: providers resolve,
   operators healthy, capacity live for every declared role, auth present, harness paths
   self-consistent (no installed-copy fallback). Fail-closed with remediation text. Prototypes:
   route preflight + `cb2cc504` shims + `b20e44d3` guard.

## 4. Contract registry and precedence

- Contracts live in `harness/config/workflows/*.workflow.json` (schema-validated in CI).
- Intake resolution order: explicit `workflow_id` in the request → trigger match (most specific
  marker wins) → `pm.generic.v1` fallback (today's behavior, unchanged).
- `pm.generic.v1` is itself a contract: it declares "stages: planner-generated", generic proof
  templates by `node_kind`, and the same route/artifact/ledger semantics — so even the generic path
  gains the compile-time checks (a planner-emitted node whose task_type isn't admitted by its capsule
  is rejected *at plan-compile*, with a repair prompt to the planner, instead of hanging at dispatch).

## 5. What this deliberately does NOT do

- No dispatcher/scheduler rewrite — the compiler emits the graph format they already execute.
- No provider-routing changes beyond consuming the contract's `provider_policy` (routing logic was
  just hardened; don't churn it).
- No dashboard redesign — one additive endpoint (`GET /api/workflows/<run>/contract`) so the existing
  UI can render labels/gates when it's ready.
- No new evaluator models, no "stronger model" dependency: the deterministic gates
  (`research eval-artifacts`, YAML/JSON parse, validator commands) carry the weight.

## 6. Phased refactor roadmap

Ordering rule: each phase is deterministically testable before the next, and the first live run
happens only at P3 of the validation ladder.

**Phase 0 — Freeze and baseline (no code).**
Land this corpus + taxonomy + this plan; agree the no-touch list; register the pre-existing red tests
(from RUNTIME-VERIFICATION-AUDIT: `test_multi_task_runner_status_surface`, `lib.compile_eval` import,
tmux-reuse reds) so future diffs are judged against a known baseline.

**Phase 1 — Contract schema + compiler (new code only).**
`workflow_contract.py`: load, schema-validate, compile to task_graph, and the four compile-time
checks (task_type admission, obligation satisfiability, root containment, route resolvability).
Ship with the three example contracts. Tests: the 11 deterministic tests already listed in
`rsi-demo-stage-contract.json` (`deterministic_tests_required_before_live`), generalized. No runtime
wiring yet — the compiler can be run standalone against fixtures and against preserved v7/v9 graphs
(replay: the compiler must *reject* v7's S1 and v9's write_scope).

**Phase 2 — RSI DeepDive lock wired behind its trigger.**
Restore/port the DeepDive router (D1–D9 or the compressed D1–D6 variant per
`rsi-deepdive-workflow-lock.md`), gated on `SOLAR_DEMO_REPORT_MODE=1` OR explicit DeepDive markers.
Artifact adapter maps native research jsonl → the five demo artifacts. Validation ladder P0→P2.
This is the first safe implementation phase with user-visible value (the demo).

**Phase 3 — Gate ledger + manifest under the contracted path only.**
Introduce the append-only gate ledger and artifact manifest for contract-run graphs; generic path
untouched. Replay v5 (mechanical FAIL) and v8 (timing) evidence as fixtures.

**Phase 4 — Wrapper/dashboard read the contract.**
`live_codex_epic_status.py` takes `--contract` and derives expected artifacts/roots/terminal states
from it (its multi-root and producer-completion logic remains as defense in depth). Dashboard gets the
read-only contract endpoint + stage strip.

**Phase 5 — Resource Radar as the second contract** (`resource-radar-workflow-lock.md`), proving the
layer generalizes; first workflow allowed to reach P6 (live web) *after* its offline rungs are green.

**Phase 6 — Generic path adoption.** `pm.generic.v1` contract wraps the LLM planner with
plan-compile validation; the four F-CLASS-04 sites collapse into one compiler check. Only after the
two locked workflows have been stable across the ladder.

**Explicitly deferred:** registry hygiene (G7/G8), usage accounting (G6), process-registry cleanup
(F-CLASS-22), installer/wizard, synthesizer content quality (F-055) — separate tracks; see
`no-touch-list.md` for why each must not ride along.

## 7. Consolidation answer (what moves into the contract compiler)

From the corpus, the compiler absorbs, as *data + compile checks*, logic that today lives as
scattered runtime patches:

- the four task_type canonicalization sites (`5f994ae7`, `713201b0`, `a3d39ca2`, `34d5c921`)
- the artifact-vs-implementation capsule routing branch (`fe2a7d69`) and its `ba1dd657` ancestor
- the patch-proof obligation shape rules (`92c5615d` + the `node_kind` legality table)
- the bounded-demo trigger/bypass (`f7febf00`) generalized into `trigger`
- wrapper expectations (`86643597`, `fd83ee51`, `1240285a` root lists) sourced from `outputs[]`/`artifact_roots`
- route policy env-var bundles (`solar-harness.sh` codex/claude mode blocks) as `provider_policy`

None of those commits get reverted; the contract makes their generalized form the default and their
per-site forms redundant over time.

## 8. The product spine (mandate-unlocked cuts — working > faithful)

Productionization target restated: (a) installer/packaging works for any new user on any new
machine; (b) every prompt gets a correct route. To get there, the shipped product runs on a
**spine**, and everything off the spine is gated off (not deleted from the repo — disabled in the
shipped configuration). Each cut names the failure classes it retires outright:

1. **One execution path: the operator pool.** The legacy cockpit-pane dispatch path is
   hard-disabled in product mode (dev flag only). Retires: silent pane fallback after admission
   failure (F-044's hang mode), `pane_not_idle`, legacy-planner-pane races (F-028), pane
   exhaustion/`needs_respawn` (F-001's cockpit half), and the S01 pane-suppression wedge surface.
2. **Two providers, allowlisted registry.** Shipped `physical-operators.json` contains only
   claude-cli and codex operators verified healthy on a clean machine; gemini/glm/thunder/flashmlx/
   browser/notebooklm entries ship disabled. Retires: broken-operator selection (F-005),
   mislabeled-provider surprises, most of G7/G8 for v1.
3. **One router.** Contracted workflows (research, code smoke) + `pm.generic.v1` validated fallback
   + honest rejection. Epic decomposition off by default below an explicit size threshold; when an
   epic does run, research-native slices for research prompts (the recovered
   `/tmp/solar-research-epic-design` template) replace the software-lifecycle slices.
4. **Gate policy change:** `needs_human_review` is no longer dependency-blocking by default — it
   becomes a per-stage contract policy (`block_dependents` only where the contract says so).
   Retires the v2/v10 cascade class as a *default* behavior instead of patching its instances.
5. **One evidence model:** preflight, per-stage route records, gate ledger, artifact manifest,
   truthful terminal status. 
6. **Dedupe `lib/` vs `tools/`** for the modules on the spine (previously deferred; now in scope
   because shipped-surface reduction shrinks the blast radius).
7. **Installer track unchanged in scope but explicit in its gate:** per-OS artifact acid tests on
   clean machines are the only accepted proof of (a); CI green is necessary, never sufficient.

What the mandate does NOT unlock: a dispatcher/scheduler rewrite. That caution was never about
faithfulness to Sihao — it protects ~20 of OUR OWN tested fixes.
