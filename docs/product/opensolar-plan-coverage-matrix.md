# Plan Coverage Matrix — every failure class vs the plan that must solve it

**Date:** 2026-07-06. Purpose: verify, class by class, that the current plan (requirements R1–R10,
design components, lanes, validation ladder) solves each failure class in
`opensolar-failure-taxonomy.json` (30 classes) — and to separate **proper systemic failures** from
**environmental/process noise**. Verdicts: **SOLVED** (plan mechanism + verification rung named),
**SOLVED-PENDING-DECISION** (mechanism exists, one owner call), **PARTIAL-BY-DESIGN** (plan reduces,
separate track owns the rest), **PROCESS** (discipline, not code).

## A. The matrix

| # | Class | Proper failure? | Plan mechanism | Verified by | Verdict |
|---|---|---|---|---|---|
| 01 | Planner DAG nondeterminism | Proper (systemic) | R3 byte-identical contracts for known families; plan-validator bounds the generic path | P1.5 golden-file + v7/v9 rejection replays | **SOLVED** (contracted) / bounded (generic) |
| 02 | Generic PM for research | Proper | R1 router; DeepDive contract restore | P1 trigger tests; P3 demo run | **SOLVED** |
| 03 | Epic over-decomposition | Proper | R1 + epic admission rule (size/explicit) | P1 compile tests | **SOLVED** |
| 04 | task_type admission (fixed 4×) | Proper | R2 compile check; non-admitted type = build error | P1.5 admission scenarios | **SOLVED** |
| 05 | Artifact node × patch-diff proof | Proper | R2 obligation-satisfiability + node_kind legality | v7 replay must be rejected | **SOLVED** |
| 06 | Missing/undiscoverable patch proof | Proper | R6 per-node artifact manifest (fixes `ff35c302`/`a8203924`/`92c5615d` locked in) | P1.5 manifest scenarios | **SOLVED** |
| 07 | Obligation mismatch by artifact type | Proper | R2 (obligations must reference declared outputs/gate inputs) | compile tests | **SOLVED** |
| 08 | Evaluator capacity / human-review cascade | Proper | Capacity model (busy≠absent, done `5ba3bdee`); per-stage `evaluator_gate` policy; deterministic gates replace LLM eval where contract allows; 2nd evaluator | contention scenario in P1.5; live at P3 | **SOLVED-PENDING-DECISION** (2nd evaluator = owner call) |
| 09 | Sticky auto-resolution clobbered | Proper | R4 ledger: decisions append-only; status = projection | v5 replay scenario | **SOLVED** (structural, replaces marker hack) |
| 10 | Mechanical vs content eval FAIL | Proper | R4 `verdict_kind: content\|mechanical\|infrastructure` set by gate runner | v5 sidecar replay | **SOLVED** |
| 11 | Closeout builder quality (true-positive FAILs) | Proper but **content**, not orchestration | Deterministic validator commands per stage (structured-output rule `9f2d7f35` generalized); builder briefs carry validator token lists | Run-G→Run-H pattern as regression | **PARTIAL-BY-DESIGN** (prompt/model quality is its own track) |
| 12 | Repair lifecycle races | Proper | R4 generations + single-flight (`714eb781`, `cd528d0a`) + property tests (terminal absorbing) | P1.5 race scenarios; live repair at P3 | **SOLVED** (live-repair exercise still owed) |
| 13 | Stale eval generation / doctor backfill | Proper | Done (`70a7b914`/`714eb781`); R4 schema-locks `eval_generation` as required field | v7 mismatch-archive replay | **SOLVED** |
| 14 | Wrapper epic observation | Proper | Wrapper reads the contract (stages/terminal states), not heuristics | wrapper contract tests | **SOLVED** |
| 15 | Wrapper timing race | Proper | Done (`fd83ee51`); contract terminal states as primary signal | v8 replay | **SOLVED** |
| 16 | Artifact-root divergence | Proper | R6 `artifact_roots` contract field + publish rule; runtime-writer normalization in Lane 3 (wrapper multi-root `1240285a` stays as defense) | v9 replay | **SOLVED** (runtime-side lands with Lane 3) |
| 17 | Route proof missing on dead runs | Proper | R5 per-stage-execution append-only route records | kill-mid-run scenario | **SOLVED** |
| 18 | Route violations / route-truth lies | Proper | R5 fail-closed preflight (done) + plan artifacts labeled as suggestions; `host_type` relabel | route scenarios; P2 per provider | **SOLVED** (label cleanup = small Lane 5 item) |
| 19 | Alias/registry data quality | Proper | Spine allowlist (Lane 0) + health-in-preflight; `sonnet`→GLM trap dies with allowlist | preflight tests | **SOLVED for v1** (full registry hygiene = later track) |
| 20 | Auth preservation/validity | Proper (operational) | Preflight per-provider auth check (fail-closed, actionable) — covers the revoked-cached-token case via cockpit-restart guidance | P2 micro-probe | **SOLVED** |
| 21 | Installed-harness contamination | Proper | Preflight path self-consistency (no `~/.solar` fallback), roots containment (no repo-root artifacts) | contamination scenario | **SOLVED** |
| 22 | Orphan coordinator/watchdog/process residue | Proper — **and the one gap this audit found** | Run-scoped process registry + teardown-by-registry + watchdog respects run-terminal marker. **Not yet assigned to a lane — must be added to the implementation plan (Lane 0.5) when R/D/I docs are written** | teardown scenario in P1.5; every rung's cleanup gate | **SOLVED-ON-PAPER → needs its lane** |
| 23 | Dashboard/projection untruth | Proper | Ledger projection + contract endpoint (Lane 5) fixes parent-status truth; **usage=0 explicitly deferred** (own track) | P4 rung | **PARTIAL-BY-DESIGN** |
| 24 | Installer/wizard gaps | Proper (separate surface) | Lane 6 per-OS artifact acid tests; wizard rebased separately | P-install gates | **PARTIAL-BY-DESIGN** (parallel track, not refactor scope) |
| 25 | Report quality / synthesizer boilerplate | Proper (content) | DeepDive lock prerequisite: fix or bypass `lib/research/cli.py` synthesizer (builder-authored path chosen for demo); deterministic research gates carry quality | P3 artifact validation | **PARTIAL-BY-DESIGN** (flagged demo blocker) |
| 26 | Self-incriminating wording | Proper-minor | Validator token list in contract + builder brief; export wording lint | v4 replay | **SOLVED-LITE** |
| 27 | No live workers | Proper (operational) | Preflight live-capacity per role; auto-start or fail-closed | preflight tests | **SOLVED** |
| 28 | Supervision faults (latches, cooldowns, dead PIDs, rc=139, CLI-drift regex) | Proper | R7 heartbeat+timeout on every wait (generalizes `8341fc5a`, Fix 0/1/4, 900→90s); structured failure snapshots; CLI-drift caught at P2 micro-probes | wedge scenarios; micro-probes | **SOLVED** (drift class needs the probe tier, by design) |
| 29 | Gates consume status, not verdict content | Proper | R4: gates read ledger verdict records, fail-closed on missing verdict (locks `5fcff602`/`983ce35a`/`949d3e3c`) | LDES-shaped scenario | **SOLVED** |
| 30 | Verdict provenance (self-graded/backfilled) | Proper | R4: records carry author+generation; evaluator writes own record; backfill non-consumable (locks `d61d92a2`/`4df6477d`) | thin-eval.json scenario | **SOLVED** |

**Tally: 23 SOLVED / 1 SOLVED-PENDING-DECISION (2nd evaluator) / 5 PARTIAL-BY-DESIGN with named owner
tracks / 1 gap found by this audit (process-registry lane — now recorded).** No class is unaddressed.

## B. Noise vs proper — the failures that were NOT systemic

These appeared in the record but are process/environment, answered by discipline rather than plan code:

| Incident | Nature | Answer |
|---|---|---|
| Assistant ran the codex eval tick inside a read-only managed sandbox → poisoned result + evaluator cooldown | verification-environment error (self-inflicted, documented) | ladder rule: live ticks run unsandboxed/escalated; the `2a8ab9db` correlation fix also removed its sting |
| "Blocked" that was slow opus (~8 min) | impatience misread | bounded waits with budgets + classification markers (ladder discipline #4) |
| Laptop sleep killing a live run | environment | ladder: live runs are rare, monitored, auto-archived |
| `/tmp` evidence loss (all v1–v9 bundles, demo kits, readiness reports) | process | durable-evidence rule: `~/opensolar-state/` only; auto-archival at teardown |
| Over-optimistic status notes later overturned ("substantially YES", "pools stopped") | reporting discipline | claims cite ladder rungs; DEFINITION-OF-DONE wording rules |

## C. Self-introduced issues — the owner's question answered directly

Yes, some failures were introduced by the fix process itself, and the corpus records them as chains:
`a3d39ca2`'s logical-op map **created** v3's failure shape; `62e0c9ac`'s escalation target
(`needs_human_review`) combined with `DEPENDENCY_BLOCK_STATUSES` **created** the v2/v5/v10 cascade;
`1f99dd25`'s evaluator bypass **created** v5's missing-gate-input FAIL; `9dd2d5ff` was disproven by
its own evidence. Every one of these is the same root pattern — a local fix encoding an assumption no
contract checked — and every one lands in classes 04/08/09/10, all SOLVED above. Also verified: the
packaging itself did **not** break the engine (engine byte-identical original→rc.3;
"no code regression" audit of 2026-06-25), so self-introduced issues were confined to the fix layer,
not the migration.

**Deleted-files concern:** already systematically handled once — the 2026-06-23 recovery built
`codex-fileops-catalog.tsv` (973 file ops from Codex transcripts), recovered **all 26 lost `/tmp`
roots → 160 files** into `~/opensolar-state/recovered-work/`, and rescue-tagged 17 orphaned commits.
The catalog's Delete entries are routine sprint-artifact cleanups (June 8–9 era), not lost product
code. The transcripts remain the ultimate recovery source and are now inventoried (corpus appendix).

## D. Timeline correction (from the recovery index)

Project prehistory goes back further than June 11: the 440-session index starts **2026-05-22**
(AI4Research research-paper→PPTX skill era), packaging migration began **2026-06-10**
(`3291998b WS0: purge runtime and personal artifacts`), first runtime self-commits June 19, KB
discipline June 23 — which is why failure records are dense from June 23 (that's when *verification*
started; June 10–18 was construction: WS0 purge → installers → GUI → CLI honesty).
