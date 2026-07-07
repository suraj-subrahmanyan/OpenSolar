# OpenSolar Requirements — the changed system SHALL…

**Date:** 2026-07-06 · **Stage:** R of R→D→I→C · **Companions:** `opensolar-target-design.md` (D),
`opensolar-implementation-plan.md` (I), `opensolar-plan-coverage-matrix.md` (traceability to all 30
failure classes), `opensolar-failure-corpus.md` (evidence).

Conventions: **SHALL** = hard requirement with acceptance criteria (AC). Every requirement cites the
failure classes it retires (F-CLASS-xx). Framing note per owner/Sihao mandate: these requirements
*complete* the baseline architecture (requirement compiler → contracts → evidence gates → capsules);
capsules become MORE authoritative, never less.

---

## R1 — Routing

The system SHALL resolve every intake to exactly one of: **(a)** a registered workflow contract
(trigger match), **(b)** the validated generic path (`pm.generic.v1`), or **(c)** an explicit
rejection with a machine-readable reason. Research-typed requests SHALL NOT enter software-lifecycle
epic decomposition. Epic decomposition SHALL be an explicit admission decision (size threshold or
explicit request), never the default.

- AC-R1.1: the RSI prompt ("deep research report … HTML") routes to `research.deepdive.rsi_demo`; `task_graph.json` carries `dag_variant=research.deepdive.rsi_demo`; a dispatcher guard rejects execution when the variant mismatches (port of the original `invalid_deepdive_dag_variant` guard).
- AC-R1.2: the 2026-06-30 web-research prompt (corpus F-037) no longer produces `S01_requirements…S05_verification_release` children.
- AC-R1.3: generic words ("research", "研究") alone do NOT trigger the research contract (original `is_explicit_deepdive_request` semantics preserved); explicit markers or `requirement_compiler=RESEARCH` do.
- AC-R1.4: an unroutable/oversized request yields a rejection artifact with reason, never a silent epic.
- Retires: F-CLASS-02, 03; bounds 01.

## R2 — Compile gate

No plan (contracted or planner-generated) SHALL execute unless it compiles. Compilation SHALL check:
**(a)** every node's `task_type` ∈ its resolved capsule's `task_type_in`; **(b)** every proof
obligation references an artifact in the node's declared outputs or a gate-produced input, and
obligation kinds are legal for the node's `node_kind` (`patch_diff` ⇒ `code` only); **(c)** every
output path resolves inside declared `artifact_roots`; **(d)** every role resolves to ≥1 enabled,
healthy, non-deprecated operator under the run's provider policy. Compile failure on the generic path
SHALL bounce the plan to the planner with the errors (bounded retries, default 2), then fail closed
as `PLAN_COMPILE_FAILED` — never a silent pane fallback, never a runtime **admission-mismatch** hang.
*(Scoped per review 2.1: compile checks registry resolvability, not live capacity — the capacity
hang is owned by R7/AC-R7.5, whose bounded-wait guarantee is the anti-hang mechanism for F-CLASS-08.)*

- AC-R2.1: the preserved v7 graph (S1 artifact node bound to `cap.requirement-compiler-implementation` with `patch_diff` obligations) is **rejected** at compile with `OBLIGATION_UNSATISFIABLE_FOR_NODE_KIND`.
- AC-R2.2: the preserved v9 graph (write_scope without the `workspace/` prefix) is **rejected** (or normalized per contract policy) with `ARTIFACT_ROOT_UNRESOLVED`.
- AC-R2.3: each of the four historical admission shapes (`analysis`, `tests`, `implementationworker`, logical-op-map-vs-audit-capsule) is a compile error with the offending node id and admitted set in the message.
- AC-R2.4: a node whose role resolves only to disabled/deprecated/unhealthy operators fails compile with remediation text.
- Retires: F-CLASS-04, 05, 07; the compile-time half of 16 and 19.

## R3 — Determinism (contracted workflows)

Instantiating the same contract version with the same inputs SHALL produce a byte-identical task
graph. Node ids, stage order, capsule bindings, task_types, output paths, and gate configs come from
the contract, not from sampling.

- AC-R3.1: golden-file test — two instantiations byte-equal; CI-diffed.
- AC-R3.2: contract files are schema-validated in CI (`solar.workflow_contract.v1`).
- Retires: F-CLASS-01 for contracted workflows (dashboard naming drift S1/R1 included).

## R4 — Gate ledger (evidence is append-only; status is a projection)

All gate-relevant decisions (eval verdicts, auto-resolutions, repair start/exhaust, human verdicts,
gate checks) SHALL be append-only ledger records carrying: `author` (operator id | doctor | policy |
human), `verdict`, `verdict_kind` (`content|mechanical|infrastructure`), `eval_generation`,
`repair_attempt`, `pm_task_id`, `evidence_snapshot_at`. Node status on the contracted path SHALL be a
pure projection of the ledger; no subsystem writes status directly. Gates SHALL consume verdict
**content** (fail-closed when an expected verdict record is missing), never node completion alone.
Records not authored by the assigned evaluator for the current generation SHALL NOT be
gate-consumable (doctor backfill is flagged, never consumed).

- AC-R4.1: v5 replay — a mechanical FAIL (`research_eval_json_missing`) cannot flip a policy-passed node; `verdict_kind=mechanical` is set by the gate runner, not inferred from strings.
- AC-R4.2: LDES-shaped scenario — a critic record `verdict=block` blocks the gate even when the critic *node* status is `passed` (locks `5fcff602`/`983ce35a`).
- AC-R4.3: thin/backfilled eval.json (`generation_mode=repair_backfill` or self-graded) is never consumed (locks `4df6477d`); property test: no status transition without a corresponding ledger record; terminal statuses absorbing. *(Per review 3.1: the audited writer surface is the full C4 list — `set_node_status`, `_mark_graph_node`, `doctor_graph`, and every inline `node["status"]=` site — with `set_node_status` as the single choke point and `doctor_graph` neutralized on the contracted path.)*
- AC-R4.4: stale-generation records are archived, never applied (locks `714eb781`); PM-task correlation preserved (locks `2a8ab9db`).
- Retires: F-CLASS-09, 10, 12, 13, 29, 30.

## R5 — Route truth

Every stage execution SHALL emit an append-only route record (provider, model, operator id, backend,
exit) at execution time; a run killed at any point has complete route evidence for every stage that
ran. Provider policy SHALL be fail-closed per role at preflight. Plan artifacts SHALL label operator
suggestions as suggestions (`suggested_operator_id`), never as the active route; `host_type` labels
SHALL reflect the actual backend.

- AC-R5.1: kill-mid-run scenario yields route records for all executed stages; no terminal node needed for route proof. Storage is the ledger's `kind: route_record` with payload `{provider, model, operator_id, backend, exit_code, started_at, finished_at}` *(added per review 5.1 — previously unstorable)*.
- AC-R5.2: P2 rung passes per shipped provider with zero cross-provider records.
- AC-R5.3: no artifact records `selected_operator_id` naming a provider the policy excludes (the `mini-claude-sonnet-builder`-in-a-codex-run lie, F-031, is impossible or relabeled).
- Retires: F-CLASS-17, 18; the alias half of 19 via allowlist+preflight.

## R6 — Artifacts

Every declared output SHALL land inside the contract's `artifact_roots` (canonical + declared
aliases, with a publish/export rule). After build/repair the dispatcher SHALL write a per-node
artifact manifest (paths, resolved roots, sizes, hashes, generation, sidecars); proof evaluation,
evaluators, the wrapper, and the dashboard SHALL discover artifacts via the manifest, never by
filename guessing. Artifacts SHALL never land in the repository checkout root.

- AC-R6.1: v9 replay — workdir-written artifacts resolve via manifest and validate; canonical copies produced by the publish rule.
- AC-R6.2: patch-proof discovery cases (`ff35c302` filename shapes, `a8203924` synthesis, `92c5615d` obligation shapes) pass via manifest without per-filename special cases.
- AC-R6.3: contamination scenario — a node attempting to write outside declared roots is blocked and reported (`ARTIFACT_ROOT_VIOLATION`), covering the repo-root stray-file class.
- Retires: F-CLASS-06, 16; the artifact half of 21.

## R7 — Termination and supervision

Every wait SHALL be bounded and every in-flight marker SHALL carry a heartbeat: eval dispatch,
role-pool inflight suppression, leases, repair windows, coordinator ticks. Expiry SHALL produce a
classified diagnostic (`ORCHESTRATION_WEDGE_NOT_PRODUCT_PROOF` family), never a silent spin. Terminal
truth SHALL propagate: all-nodes-terminal ⇒ parent status terminal ⇒ projection terminal; finalized
is frozen. Every daemon started for a run SHALL register (pid, role, run_id) in a run-scoped process
registry; teardown kills by registry (watchdog first) and the watchdog SHALL NOT respawn past a
run-terminal marker. Supervision failures SHALL snapshot state (leases, status, inbox, process tree).

- AC-R7.1: S01-wedge scenario — hung operator with inflight suppression expires within its budget with the wedge classification (generalizes `8341fc5a`).
- AC-R7.2: v10-shaped scenario terminates with a classified terminal state well before any external timeout; no 90-minute ceilings.
- AC-R7.3: `a8203924`-shaped scenario — graph terminal ⇒ parent `status.json` terminal (fixes F-032); finalized sprints cannot reopen (locks `13a43861`); mid-run acceptance verdict is `IN_PROGRESS` (locks `7aa029fe`).
- AC-R7.4: teardown scenario — zero surviving run-scoped processes after wrapper exit, including watchdog-respawn attempts (fixes F-043; proven at the non-hermetic P1.6 real-daemon tier; every ladder rung's cleanup gate enforces it).
- AC-R7.5 *(added per review 2.1; the owning AC for F-CLASS-08's busy/absent misclassification)*: a stage whose `evaluator_gate.on_capacity_unavailable=wait` SHALL wait **at most** its `result_timeout_sec`; expiry produces the wedge classification, never an unbounded wait. Scenario: busy-singleton evaluator → bounded wait → classified expiry (with timeouts injected via the existing `SOLAR_*_TIMEOUT_SEC*` env knobs so the scenario runs in seconds).
- Retires: F-CLASS-22, 28; the truth half of 23; F-067 family; the hang mode of F-CLASS-08.

## R8 — Shipped surface (the spine)

The shipped configuration SHALL enable only: the operator-pool execution path, Claude-CLI and Codex
physical operators, the contracted workflows + validated generic path, and the dashboard. The legacy
cockpit-pane *dispatch* path SHALL be disabled in product mode (panes may remain as a viewer);
operators/capsules for gemini/glm/antigravity/thunderomlx/browser-agents/notebooklm/flashmlx and
personal ingest adapters SHALL ship disabled; dead config (`operator-model-selections.json`) SHALL
not ship as apparently-live. Nothing is deleted from the repository — gating only. A disabled
component is re-enabled only after passing the ladder under its own contract.

- AC-R8.1: in product mode, an operator-pool submit failure produces a terminal blocked node with reason — never a pane fallback (`pane_not_idle` is unreachable on the product path).
- AC-R8.2: the selector cannot pick a disabled operator; preflight lists only enabled+healthy ones.
- AC-R8.3: bare `sonnet` either resolves to Anthropic or fails preflight — it never silently reaches GLM (F-068).
- Retires: F-CLASS-19 (v1 scope), 27 reachability half; the hazard half of 21.

## R9 — Testability without live models

The full pipeline SHALL run under a deterministic fake-operator backend driven by scenario files
(scripted artifacts, exit codes, delays, verdicts, faults). Every taxonomy class (30) SHALL have ≥1
scenario reproducing it; a class is not closed without its scenario, and a fix is not done until its
class's scenario passes. Every live run at any ladder rung SHALL auto-archive a replayable bundle
under `~/opensolar-state/run-archive/` at teardown. Recorded-LLM replay SHALL be available where
realistic model text matters. Tests SHALL pin `HARNESS_DIR`/`SPRINTS_DIR`/`PYTHONPATH` (no
installed-harness imports).

*Amendments per review 1.1/9.1/4.x:* scenario coverage is **29 classes hermetic at P1.5** + F-CLASS-22
at the **non-hermetic P1.6 real-daemon tier** + F-CLASS-24 delegated to Lane 6's install rung.
Scenario 11 asserts the true-positive gate behavior (parseable-but-stale closeout SHALL be failed by
the content gate) — builder quality itself remains the quality track. F-CLASS-15's scenario covers
the producer-completion mechanism; the historical 18 ms race is covered by the preserved v8 replay
at P1. All CI inputs SHALL be in-repo (the DeepDive source is vendored before Lane 4 tests exist —
no external-mirror dependency in any CI gate).

- AC-R9.1: full scenario suite (≥30 scenarios) green in CI: no network, no quota, wall-clock minutes.
- AC-R9.2: the P1.5 rung gates every lane join in the implementation plan.
- AC-R9.3: a live failure is converted to a fixture before its fix is merged (bisection happens offline).
- Retires: the discovery-by-live-run method itself (the weeks-lost meta-failure).

## R10 — Installability (parallel track)

A new user on a clean machine SHALL get a working install per OS, proven by artifact acid tests
(install → first-run bootstrap → bundled-harness sync → dashboard loads → intake works), not by CI
build success. This track owns F-CLASS-24 and runs independently (Lane 6); its requirements are the
gap-register G1/G2/G5/G15 items and are not re-specified here.

---

## Non-requirements (explicit, to prevent scope creep)

1. NO dispatcher/scheduler rewrite — the compiler emits the existing task-graph format; ledger/manifest are additive with legacy shims.
2. NO provider-routing logic changes beyond consuming `provider_policy` and the relabeling in R5.
3. NO dashboard redesign — one additive read-only contract endpoint + existing projection consuming ledger truth.
4. NO new providers; hybrid mode is deferred until both strict modes pass P2.
5. NO live web until the Resource Radar contract's P6 rung; NO epics before a bounded contract holds P3/P4.
6. NO new `SOLAR_DEMO_REPORT_MODE`-style engine conditionals — behavior differences come from contract fields.
7. Usage accounting, full registry hygiene, synthesizer content quality, wizard integration: separate tracks (coverage matrix marks them PARTIAL-BY-DESIGN with owners).
