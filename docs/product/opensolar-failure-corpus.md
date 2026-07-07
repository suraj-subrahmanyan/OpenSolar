# OpenSolar / AI4Research Failure Corpus

**Date compiled:** 2026-07-06
**Compiled by:** Failure-Corpus Architect session (read-only archaeology; no runtime code touched)
**Status:** evidence-backed reconstruction. Facts vs inference are marked. Unknowns are explicit.

## 0. Method, sources, and lost evidence

Evidence actually read for this corpus:

- `~/opensolar-state/knowledgebase/verified-runs/` — ~50 reports incl. `00-ROOT-CAUSE.md`, `01-FIX-STATUS.md`, `04-EVAL-REPAIR-ATTRIBUTION-FIX.md`, `05-HANDOFF-2026-06-28.md`, `run-E/F/G/H-*.md`, `RC3-TO-RC8-PROGRESS-BROKEN-FIXED-OPEN-20260629.md`, `RC8-GAP-REGISTER-AND-FIX-PLAN-20260629.md`, `RC8-RUNTIME-ARCHITECTURE-GAP-AUDIT-20260629.md`, `RC8-CODEX-ONLY-E2E-FAILURE-AUDIT-PLAN-20260629.md`, `RC8-RUNTIME-AUDIT-HANDOFF-20260630.md`, `RC8-CODEX-LIVE-WEB-RESEARCH-DEMO-20260630.md`, per-commit `RC8-CODEX-ONLY-LIVE-E2E-*.md`.
- `docs/product/` on branch `feat/rc8-demo-golden-path` — the five RSI-demo diagnoses, `rc8-codex-runtime-smoke-review.md`, `branch-regression-matrix.md`, `rsi-deepdive-vs-original-solar.md`, `rsi-demo-stage-contract.json`.
- Session memory files (`rc8-demo-golden-path`, `rc8-s01-prd-gate-wedge`, `rsi-deepdive-workflow-lock`, `runtime-build-wall-is-no-live-workers`, etc.) — these are the only surviving record of RSI demo runs v1–v9 details.
- Git history: `main`, `pkg/migration` (339 commits ahead of main), `upstream/openJiuwen-Solar` (62 ahead of pkg/migration), `integration/rc8-runtime-mode-contract` (23 ahead of upstream), `rc8-runtime-mode-contract` (original-hash lineage), `feat/rc8-demo-golden-path` (14), `fix/rc8-s01-prd-gate-wedge`, `validation/rc8-paperfilter`, `validation/rc8-local-research-report`, `feature/setup-wizard`, `feat/runtime-fixes`.

**Lost evidence (explicit):** all `/tmp` bundles named in the task brief are gone — `/tmp/solar-rc8-*`, `/tmp/RC8-*`, `/tmp/solar-rsi-demo-run-*`, `preserved-evidence-rsi-demo-v2..v9`, `/tmp/solar-dashboard-demo-readiness`, `/tmp/solar-demo-video-kit`, `/tmp/rsi-demo-recording-ready`. `git worktree list` shows `/tmp/solar-rc8-s01-prd-gate-fix` and `/tmp/solar-rc8-validation-local-report` as *prunable* (directories deleted). Where a failure record below cites a `preserved-evidence-rsi-demo-v*` path, that path is the historical location recorded in the memory/diagnosis docs, and the surviving primary evidence is the committed diagnosis doc plus the memory record — not the raw bundle.

**Dual hash lineages (important for the commit map):** the runtime-contract fixes exist twice: original hashes on local branch `rc8-runtime-mode-contract` (e.g. `ff35c302`, `714eb781`, `a8203924`, `cb2cc504` — these match the KB report filenames) and rebased hashes on `integration/rc8-runtime-mode-contract` (e.g. `c7783029`, `d00903ab`, `d2339f21`, `63769097`). Similarly `feat/runtime-fixes` commits (`62e0c9ac`, `703e6c27`, `d3e9b690`, …) were re-landed on `upstream/openJiuwen-Solar` as (`0344d159`, `ec8caff1`, `0e4842b3`, …). Both hashes are given as `original / integrated`.

**Redaction:** no tokens, keys, or auth payloads appear in this corpus. Where auth is relevant (Codex auth preservation), only the *existence* of auth files is noted.

---

## Phase A — rc3-era installed runtime and the "build wall" (≤ 2026-06-27)

Baseline: `main` = `a3a0ecaa`, the Sihao developer harness. `pkg/migration` added the product shell (desktop, installer, dashboard, service templates — 339 commits). The installed `~/.solar/harness` was rc3/rc4-era while newer code existed in the tree.

### F-001 — Build dispatch wall: `worker_capacity_exhausted` with idle operators
- **date:** diagnosed 2026-06-27 · **source:** `verified-runs/00-ROOT-CAUSE.md` · **branch:** installed `~/.solar/harness` (rc4-era)
- **run id:** 50 historical sprints surveyed; outcome distribution `interrupted 19 · superseded 16 · passed 11 · active 3 · completed 1 · blocked 1`
- **failed node:** build dispatch (all fresh runs) · **node status:** nodes queue forever with `worker_capacity_exhausted`
- **primary class:** operations/no-live-workers · **secondary:** operator-registry semantics (config "available" ≠ live)
- **root cause (proven):** "there are NO LIVE WORKERS" — cockpit tmux panes sat at bash, builder pane `needs_respawn`; the multi-task pool session was `missing` (0 live workers). The ~30 `mini-*` entries in `physical-operators.json` are a configured pool, not running workers.
- **wrong hypotheses first (recorded):** capability-vocabulary mismatch (27 required caps vs 12 advertised) — disproven by reading `graph_scheduler.py:1909-1972`.
- **what worked:** PM + Planner stages; 12/50 sprints had previously completed.
- **fixed by:** operational (`multi-task start`), plus config commits `0e0429ef`/`2729e974` (codex profiles in pool) and `a846252b`/`c62ad1da` (per-sprint work_dir). · **tests:** none for the operational part · **live revalidated:** yes (Runs B–H) · **still open:** the *architecture* question (why "select runtime" doesn't guarantee live workers) persisted into rc8 route-preflight work. · **dashboard-visible:** yes (runs looked stuck).
- **evidence quote:** "Real cause: there are NO LIVE WORKERS. … every build node queues `worker_capacity_exhausted` — there is literally no builder running to take it." (`00-ROOT-CAUSE.md`)

### F-002 — Run A: provider routing violated the user's selection
- **date:** 2026-06-27 · **source:** `05-HANDOFF-2026-06-28.md` §4 · **class:** route-proof provider violation (#18)
- **record:** "Run A (TLS explainer): labeled Claude but routed to OpenAI/Codex → NOT a clean Claude proof."
- **fixed by:** default provider policy `2155c1be` (memory) / `cb18f8b0` (integrated), later hard route selectors (Phase C). · **still open:** no (superseded by route-proof artifact) · **dashboard-visible:** no (that was the problem).

### F-003 — Run C: dashboard intake 30s shell-out timeout
- **date:** 2026-06-27 · **source:** `05-HANDOFF-2026-06-28.md`, memory `runtime-build-wall-is-no-live-workers`
- **class:** dashboard · **root cause:** `api.ts` 30s timeout aborted `/intake` although the intake CLI takes ~90s.
- **fixed by:** `d2edac3d` (210s timeout for intake/verdicts/handoff) · **live revalidated:** yes (Run D intake 00:52:14→00:53:47Z) · **still open:** no.

### F-004 — Run D: eval dispatch spun 246× with no terminal state; deliverable came from outside the pipeline
- **date:** 2026-06-28 · **source:** `04-EVAL-REPAIR-ATTRIBUTION-FIX.md` §1, `run-E-*.md` · **branch:** `feat/runtime-fixes` (installed copy)
- **run id:** `sprint-20260628-005214-…-083ff55f` · **user prompt:** monolith-vs-microservices briefing (pinned Claude)
- **graph shape:** N1..N5, gates G_RESEARCH/G_DRAFT/G_VERIFY/G_REVIEW · **failed nodes:** N1, N2 stuck `reviewing`; N3 (deliverable node) never ran
- **node status history:** N1 `reviewing` @00:58:11Z, N2 `reviewing` @00:58:19Z, **no repair_attempts, no eval_dispatched_at**
- **artifact state:** deliverable produced by a **direct `claude` CLI call**, not the pipeline ("NOT a full end-to-end Claude pipeline success")
- **provider table:** N1/N2 `backend=claude-cli, model=sonnet, provider=anthropic` (from RUN_DIR status.json, pre-fix not durable)
- **primary class:** evaluator capacity (#8) · **secondary:** attribution gap (provider proof reaped after 120min), silent non-terminal retry
- **root cause (proven):** `dispatch_node_evals` found **zero evaluator panes**, "skipped with `no_available_evaluator` and returned — over and over, **246 times**, with no per-node failure counter and no terminal escalation."
- **fixed by:** `62e0c9ac` / `0344d159` (durable node_runstate + bounded escalation to `needs_human_review`, env `SOLAR_GRAPH_NODE_EVAL_MAX_DISPATCH_FAILURES` default 8) and `703e6c27` / `ec8caff1` (`SOLAR_GRAPH_EVAL_OPERATOR_POOL` — the evaluator pool existed but was gated behind the *builder* pool flag).
- **tests added:** 8/8 unit (sandbox), replay of the real Run D graph (Run E: both nodes escalated after 3 failures) · **live revalidated:** yes — Run F ran 3 real opus evals through the pool · **still open:** no for the hang; **yes** for the deeper design issue (a singleton evaluator serializes every DAG — recurs as F-022/F-045) · **dashboard-visible:** partially (`needs_human` phase mapped after fix).
- **evidence quote:** "`events.jsonl` (506 events) → 246 × `graph_eval_dispatch_failed` … `{"reason":"no_available_evaluator","capacity":{"available_evaluators":0…}}`"

### F-005 — Operator selection picks broken/mislabeled operators
- **date:** 2026-06-28 · **source:** `run-F` ("selector first picked a gemini operator that fails here, exit 1"), `run-G` caveats · **class:** operator registry / selection (#19 adjacent)
- **root cause:** config marks operators enabled/available with no backend health; `physical-operators.json` data-quality errors — "`mini-codex-gpt55-medium-planner-2` (a physical-operators entry mislabeled `provider=anthropic`; a *planner* operator used for builder nodes)".
- **fixed by (chain):** failure cooldown in `d3e9b690`/`0e4842b3`; default Claude/Codex provider policy `2155c1be`/`cb18f8b0`; role-compatible selection `cfbe0e26`/`ce046b31`; backend health `09d47d0e`/`23b9039f`; deprecated-skip `c6ef0190`/`8e7f1dcf`; dead-lease recovery `73387de9`/`0b715b52`.
- **tests:** unit/replay per commit (memory records "replay-verified, no live run" for the selection commits) · **live revalidated:** partially (Run H used pinning; rc8 runs used named codex operators) · **still open:** registry hygiene (mislabeled entries) was flagged in run-G "Remaining" and again in G7/G8 of the gap register — **open**.

### F-006 — Closeout/evidence nodes fail eval (malformed YAML, stale handoff)
- **date:** 2026-06-28 · **source:** `run-F` (N3 FAIL: "the N3 builder never rewrote handoff.md — still the stale planner handoff"), `run-G` (S3 malformed `review_decision.yaml` FAILED), `run-H` (fix verified)
- **class:** content evaluator FAIL (#11) — a *true positive*; builder-quality on closeout nodes · **secondary:** structured-output contract absent
- **fixed by:** `56079fd6` (memory) / `9f2d7f35` (integrated) — "require structured-output validation in build dispatch (closeout nodes)": .yaml/.json write-scope nodes must `yaml.safe_load`/`json.load` before closeout.
- **live revalidated:** **yes** — Run H: "S3's dispatch.md INCLUDED the 'Structured Output Validation (REQUIRED)' block. The deliverable `<sid>.review_decision.yaml` PARSES cleanly … (Run G: same node, malformed YAML, FAILED. Fix works.)"
- **still open:** the general "review/evidence builder underperforms" pattern was still listed in the gap register (G14) — partially open.

### F-007 — DAGs require manual driving; coordinator does not self-advance
- **date:** 2026-06-28 · **source:** `run-F` ("the cockpit coordinator daemon is idle bash, so it does not auto-advance sprints"), `run-G` (fix) · **class:** wrapper/coordination
- **fixed by:** `d3e9b690`/`0e4842b3` (multi-task auto-advance + deadlock exit), `a1105f82`/`c710b732` (coordinator self-completes approved sprints; "INERT until cockpit restart") · **live revalidated:** Run G (self-advanced, exited cleanly), Run H (fully green) · **still open:** coordinator self-complete later segfaulted under Codex (F-025).

### F-008 — Deliverables land in harness root; codex not reachable from the pool
- **date:** 2026-06-27 · **source:** `01-FIX-STATUS.md` · **class:** artifact-root (#16 precursor) + provider plumbing
- **fixed by:** `a846252b`/`c62ad1da` (default work_dir `SPRINTS_DIR/<sid>/workdir`), `0e0429ef`/`2729e974` (codex profiles) · **still open:** the workspace-vs-workdir divergence recurred at the wrapper layer in v9 (F-051) — the root convention was never contractual.

### F-009 — Process finding: slow opus evals misread as "blocked"
- **date:** 2026-06-28 · **source:** `run-H` ("that was IMPATIENCE: … opus eval was just slow, ~8 min") · **class:** report-quality/verification discipline. Fix: `f550b7d4`/`7f33eb67` sonnet evaluator (speed), and the lesson feeds the validation ladder (bounded, evidence-based waits).

---

## Phase B — rc5→rc7 packaging / installer / dashboard (2026-06-24 → 2026-06-29)

These are product-shell failures. They are included because they consumed large amounts of time and because two of them (F-014, F-018) directly interact with the runtime contract story.

### F-010 — Desktop artifact serves a stale installed harness
- **source:** `RC3-TO-RC8-PROGRESS…` ("a new `.exe`/`.dmg` could still serve an old `~/.solar/harness`") · **class:** installer (#24)
- **fixed by:** `a10dfcfe` (sync bundled harness when stale; bump rc.8) · **live revalidated:** artifact-level test still gated at time of the reports · **still open:** artifact install acid tests (macOS/Windows) were still the release gate.

### F-011 — Tracked persona symlink to a private absolute path broke packaging
- **source:** `RC8-GAP-REGISTER…` §3: symlink target `/Users/lisihao/.solar/harness/personas` · **class:** installer/packaging
- **fixed by:** `446a1c5b` · **still open:** no (but raw `../harness` bundling flagged fragile — G9).

### F-012 — Prepackage check false-failed on frontend `node_modules` symlinks
- **fixed by:** `c48507fb`; Desktop Build reported green after · **class:** installer/CI false-red.

### F-013 — Fresh Ubuntu 24.04 PEP-668 pip install hard-fail → fixed `1d9fddf0` (rc.7).

### F-014 — macOS session click white-screen / stale published artifact
- **source:** WEBAPP-AUDIT memory ("macOS white-screen = stale published artifact (BrowserRouter); rc6 source = HashRouter+app://+open-SSE (unproven on real .dmg)"), friend's macOS report in `RC8-RUNTIME-AUDIT-HANDOFF` ("session click white-screen/freeze likely React/SSE route issue", "symlinked `~/.solar/harness` dangerous", "get-solar.sh default pointed to unpublished rc.8 tag") · **class:** installer + dashboard · **fixed by:** rc6 router change; `e2749449` (bundled runtime first on macOS); macOS bootstrap fix noted at `97f13dcc` (worktree `/tmp/solar-rc8-macos-bootstrap-fix` — bundle lost, branch `fix/rc8-macos-bootstrap-fix` exists) · **still open:** clean-Mac artifact acid test.

### F-015 — WSL2 install path failures (CI green ≠ user path)
- **source:** cross-os memory (4 CI gotchas), gap register P0-6 ("User now reports WSL2 install is not working properly"), `714eb781` note ("WSL distro is missing and port stays null") · **class:** installer · **still open:** yes (fresh Windows first-run bootstrap).

### F-016 — Usage reports 0 while real model calls happen
- **source:** gap register G6 · **class:** dashboard/accounting · **still open:** yes (P0/P1 in register; no fix commit found).

### F-017 — Dashboard illegibility ("Log Message" wall, raw state blobs, giant plan cards)
- **fixed by:** dashboard overhaul chain on `feat/dashboard-overhaul` (`94aa4f9d`, `826a3c9b`, `9c3e3c8e`, `0ea0b822`, `ffe9806b`, `d2edac3d`) — gates green, merged into release content per `RC3-TO-RC8` ledger · **class:** dashboard.

### F-018 — Research nodes bound code-capability capsules (earliest capsule-misbind on record)
- **date:** rc5 era (pkg/migration) · **commit:** `ba1dd657 fix(capsules): research nodes must not bind code-capability capsules`
- **significance (inference, marked):** this is the same failure family as v7's artifact/proof-contract mismatch (F-049), appearing **weeks earlier** on a different layer. The class was patched per-site, not contractually, and recurred.

---

## Phase C — rc8 Codex-only runtime-mode contract (2026-06-29 → 2026-07-01)

Goal: "select Codex and nothing silently routes to Claude." Method: repeated live E2E of a small `uniqwords.py`/`countchars.py` prompt, one fix per exposed seam. Branch `rc8-runtime-mode-contract` (original hashes), later rebased to `integration/rc8-runtime-mode-contract`.

### F-019 — Audit node dispatched `task_type=analysis`; audit capsule admits only canonical types
- **date:** 2026-06-29 · **source:** `RC3-TO-RC8` ledger ("a live Codex-only run failed before model execution because an audit/scope node persisted `dispatch_task_type=analysis`, while the audit capsule only admitted … `audit_inventory`")
- **class:** operator/capsule/task_type mismatch (#4) — **first of four instances of this class**
- **fixed by:** `5f994ae7` / `fbb5ab6e` (canonicalize read-only audit labels → `audit_inventory`) · **tests:** capability+PM 18/18, subset 68/68 · **live revalidated:** partial (S1 dispatched to codex builder with provider openai).

### F-020 — Live E2E `48d4a770`: planner gate never advanced; orphan codex processes after cleanup
- **date:** 2026-06-29T16:27Z · **source:** `RC8-CODEX-ONLY-LIVE-E2E-20260629T162741Z.md` (HEAD `c6ef0190`) · **run:** `sprint-20260629-162742-…-48d4a770`
- **observed:** poll loop stuck `status=drafting phase=prd_ready`; cleanup section lists surviving `status-server.py`, `coordinator.sh`, and 3 × `codex_operator.py` processes.
- **classes:** wrapper/PM-gate stall + process cleanup (#22) · **fixed by:** subsequent chain (F-021…F-030); cleanup class never got a dedicated fix — **open** (recurs in F-043).

### F-021 — Stale pre-repair eval output decides a repaired node (repair lifecycle race / stale generation)
- **date:** 2026-06-29 (`ce61db90` run) and again 2026-06-30 (`75c79ef1` clean run) · **source:** `RC8-CODEX-ONLY-E2E-FAILURE-AUDIT-PLAN` P0-1; `RC8-RUNTIME-AUDIT-HANDOFF` ("Final eval JSON says `generated_by=graph_scheduler.doctor`, `generation_mode=repair_backfill` … a pre-repair eval path repopulated canonical sidecars after repair")
- **classes:** stale eval generation / stale sidecar race (#13) + repair lifecycle race (#12)
- **root cause (proven):** canonical `<node>-eval.md/json` files are not tied to a dispatch generation/repair attempt; a late pre-repair evaluator (or the scheduler *doctor backfill*) overwrites them after repair, and reconcile treats stale evidence as current.
- **fixed by (three passes):** `70a7b914`/`d09e1ed0` (fence repair eval generations + close blocked DAGs) → `714eb781`/`d00903ab` (eval_generation/repair_attempt/eval_dispatch_id stamped on dispatch and assignments; stale/doctor sidecars archived; duplicate node dispatch guard) → `cd528d0a` on integration (keep graph open during active repair — the *parent terminalization* race the earlier fixes exposed).
- **tests:** graph suite 37, pinned subset 102 (714eb781); repair-lifecycle deterministic tests listed in `rc8-codex-runtime-smoke-review.md` §2 · **live revalidated:** the passing smoke at `cd528d0a` did **not** trigger repair — repair path is deterministic-test proven only (explicit in the smoke review) · **still open:** live repair exercise.

### F-022 — Busy singleton evaluator classified as "no evaluator" → burns escalation budget → terminal `needs_human_review`
- **date:** 2026-06-29 · **source:** failure-audit plan P0-2: "`_operator_pool_role_available('evaluator')` returns false when the only evaluator is busy … conflates 'no evaluator exists' with 'a valid evaluator exists but is temporarily busy.'"
- **class:** evaluator capacity (#8) · **fixed by:** `5ba3bdee` (bound evaluator capacity stalls and archive attempts; busy → `evaluator_temporarily_busy`, removed from `_EVAL_STUCK_REASONS`)
- **still open as design:** the singleton-evaluator contention itself remained and resurfaced as the RSI v2/v5/v10 `needs_human_review` cascade (F-045, F-048, F-052).

### F-023 — Failed dependency leaves downstream `pending` and parent `active` forever
- **source:** failure-audit plan P0-3: final graph "`S1`: failed; S2/S3 unset/pending; parent still `active/planning_complete`; `failed_nodes`: empty" → loop spins to external timeout
- **class:** graph closure / terminalization · **fixed by:** `70a7b914`/`d09e1ed0` (dependency-block terminalization; explainable terminal parent) · **live revalidated:** later runs show `graph_node_dependency_blocked_terminalized` firing correctly (RSI v2) — the *mechanism* works; whether a blocking status **should** cascade is a separate design question (F-045).

### F-024 — Missing/undiscoverable patch proof for code nodes (three distinct sub-bugs)
- **class:** missing patch proof sidecar (#6) + proof-artifact discovery
- **(a) discovery:** repair created `<sid>.S1-patch.diff` but "Evaluator/sidecar evidence still reported missing patch diff" → `ff35c302`/`c7783029` (node-scoped patch filename discovery; removed the false-positive fallback "handoff + write_scope ⇒ patch present").
- **(b) synthesis:** live run exposed missing `S1-patch.diff` when the worker produced none → `a8203924`/`d2339f21` (synthesize deterministic patch sidecars from write-scope files when obligations require patch_diff).
- **(c) obligation shape:** on the integration branch, live smoke at `154a1d48` failed on missing `S1-patch.diff`; `92c5615d` made proof emission honor *sidecar obligations* (`patch_diff exists` without a `field`), which then exposed the repair race fixed by `cd528d0a`.
- **live revalidated:** yes — `a8203924` clean run green (below); integration smoke at `cd528d0a` green with 7,023-byte `S1…-patch.diff`.

### F-025 — Coordinator self-complete tick segfaults (`rc=139`)
- **date:** 2026-06-29→30 · **source:** `RC8-RUNTIME-AUDIT-HANDOFF` ("repeated `rc=139` … The crash is in Python import while invoking `multi_task_runner.py`")
- **class:** runtime supervision / environment · **root cause (proven):** Python 3.13 readline segfault under missing `en_US.UTF-8` locale, triggered only via coordinator invocation.
- **fixed by:** `83575bab`/`8ad0da81` (output-file capture + `PYTHONFAULTHANDLER=1` — observability only) then `792f6a2b`/`fcee2d97` (lazy readline import + locale selection — the real fix) · **tests:** `test_multi_task_runner_readline_locale.py` · **live revalidated:** yes (subsequent green runs use self-complete ticks).

### F-026 — Stale operator lease/status with dead PIDs blocks selection
- **source:** handoff item 2 ("`operator-status/…evaluator-1.json` still says `runtime_state=running` … No live processes for those PIDs")
- **class:** operator runtime state · **fixed by:** `73387de9`/`0b715b52` (dead-PID lease recovery) + `2db50662` (route proof + stale status recovery, integration) · **residual (open):** status-server recomputes operator state independently — "dispatcher/selector and dashboard can disagree" (arch audit P0-4, split-brain).

### F-027 — Fresh eval assignment closed out by an older failed result
- **source:** handoff: "`_latest_operator_result_for(sid,node,operator)` filtered only by sprint/node/operator, not by the active eval assignment's PM task ID" — a fresh retry was killed by the previous (sandbox-poisoned) result and re-cooled the evaluator.
- **class:** eval closeout correlation · **fixed by:** `2a8ab9db` / `0c66ae6a` (correlate eval closeout to active PM task) · **tests:** 29 in `test_graph_dispatch_submit.py`.

### F-028 — Legacy Claude planner pane races the Codex role-pool planner → `a85adc43`/`6578bb9d`. Class: dual-path orchestration.

### F-029 — Clean-harness contamination: operator shell falls back to installed `~/.solar`
- **source:** handoff: "planner shell failed `solar-harness context inject` with command-not-found, then fell back to global `~/.solar/bin/solar-harness`, invalidating clean proof"
- **class:** installed harness contamination (#21) · **fixed by:** `cb2cc504`/`63769097` (task-local cmd-shims, HARNESS_DIR/PYTHONPATH pinning) + `b20e44d3` (test-level contamination guard). Also process discipline: pytest importing installed lib produced 6 false failures until env was pinned (recorded twice).
- **still open:** the *installed copy* drifting from any branch remains a standing hazard (also memory `sonnet-e2e-proven-and-runtime-walls`: "sync-harness-runtime.sh clobbers model config").

### F-030 — `task_type=tests` rejected by implementation capsule → `713201b0`/`d9dc0ab4` (canonicalize test-authoring aliases). **Second instance of class #4.**

### F-031 — Route-truth artifacts lie even when routing is correct
- **source:** clean-run findings: "`S1_IMPLEMENT_CLI-physical-plan.json` still records `selected_operator_id=mini-claude-sonnet-builder` … Execution did not spend Claude, but the artifact lies"; also "`host_type=claude_code_session`" for codex operators.
- **class:** route-proof/observability (#17/#18-adjacent) · **fixed by:** partially `30169c80` (sync closeout and command attribution) · **still open:** yes — flagged again in the `a8203924` green-run gaps.

### F-032 — Parent `status.json` stays `active` after all graph nodes passed
- **source:** `a8203924` green run: "parent `status.json` still says `status=active` … even though `task_graph.json` and `task_dag.state.json` are terminal passed. This is a dashboard/product closeout projection bug."
- **class:** status projection / dashboard truth · **still open:** yes (recommended fix #1 after that run; no commit found).

### F-033 — Multi-task-launched node attribution incomplete (`operator_id=N/A`, `dispatch_mode=None`) — **open** (recommended fix #2 after `a8203924`).

### F-034 — Codex model aliases missing from model-registry → `154a1d48`/`2523d7b6`. Class: model alias/registry (#19). Deterministic CLI checks in smoke review §2.

### F-035 — Codex auth lost in isolated sandbox E2E → `f26ce84b`/`8310a149` ("preserve Codex auth in isolated live E2E"). Auth files exist and are copied; contents not inspected here. Class: auth preservation (#20).

### F-036 — Evaluator/PM contract overreach: acceptance stricter than the user prompt
- **source:** clean-run finding 2: "Eval failed A4 partly because literal invalid UTF-8 *path bytes* exited 0. That is a Linux surrogateescape edge case the prompt did not clearly require. This is a PM contract/evaluator quality problem."
- **class:** quality/contract authoring · **still open:** yes — no commit addresses PM acceptance-criteria calibration.

### Phase C outcome (proven)
- 2026-06-30: first **clean** Codex-only green DAG at `a8203924` (`sprint-20260630-181209-…-ab795810`, S1/S2/S3 passed, 15 route records all `openai`, 0 violations) — `RC8-CODEX-ONLY-LIVE-E2E-A8203924-20260630.md`.
- 2026-07-01: isolated smoke at `cd528d0a` **passed** (`sprint-20260701-202854-…-c42d1e2f`): OpenAI-only route proof `{"ok": true, "stage_count": 5, "providers": ["openai"]}`, patch proof 7,023 B, clean teardown — `rc8-codex-runtime-smoke-review.md`.
- Explicit scope statement in the smoke review: does **not** prove Claude-only, wizard/installer, deep research, live repair, long reports.

---

## Phase D — Epic decomposition and validation wedges (2026-06-30 → 2026-07-02)

### F-037 — Deep-research prompt decomposed into a 5-child *software-lifecycle* epic; wedged at S01 for the whole run
- **date:** 2026-06-30T14:05Z · **source:** `RC8-CODEX-LIVE-WEB-RESEARCH-DEMO-20260630.md` · **branch/HEAD:** `714eb781` · **run id:** `epic-20260630-create-a-deep-research-report-for-an-early-stage-startup-cto`
- **user prompt:** 2026 AI coding assistant landscape deep-research report, ≥8 cited URLs, accessed_at timestamps, "Do not fabricate sources."
- **graph shape:** children `S01_requirements → S02_architecture → S03_core_runtime → S04_orchestration_ui → S05_verification_release` — a software-engineering lifecycle imposed on a research task
- **failed node:** S01 `active`, `operator: None` for ~37 minutes of polls (14:05→14:42); S02–S05 `pending` throughout · **artifact state:** epic/task_graph/traceability JSON only; zero research artifacts · **route-proof:** none
- **operator table:** leases repeatedly released `{"released": true, "release_reason": "dispatch_window_unavailable"}` (dozens of identical lines)
- **primary class:** generic PM decomposition used for deep research (#2) · **secondary:** epic over-decomposition (#3), wrapper epic observation (#14 — this run motivated `c8bda26e`), S01 wedge (F-039)
- **still open:** **yes at architecture level** — this exact decomposition is what the DeepDive lock removes.

### F-038 — Paperfilter validation: wrapper watched only parent epic; oversize epic
- **date:** ~2026-07-01/02 · **source:** commits `c8bda26e` ("test(e2e): observe epic child status in live Codex wrapper", +852 lines incl. `scripts/live_codex_epic_status.py`) and `86643597` ("test(e2e): add artifact validation mode"); branch `validation/rc8-paperfilter` = `86643597`; task brief confirms "Paperfilter validation exposed epic observation and oversize epic issues."
- **classes:** wrapper epic observation bug (#14); epic over-decomposition (#3)
- **raw run bundle:** lost with /tmp; the wrapper code + tests (231→546 test lines) survive as the fix record. · **live revalidated:** the wrapper was used by every later validation run.

### F-039 — Local-research-report validation wedges at S01: unbounded role-pool inflight suppression + hung codex operator
- **date:** confirmed 2026-07-02 · **source:** memory `rc8-s01-prd-gate-wedge`; branch `fix/rc8-s01-prd-gate-wedge` @ `8341fc5a` · **baseline:** `86643597` on `validation/rc8-local-research-report`
- **observed:** the bounded report task decomposed into "the SAME 5-child software-lifecycle epic as paperfilter … and wedged at S01 for the full 30-min timeout, zero artifacts, zero route-proofs."
- **root cause (proven):** "`coordinator.sh` `handle_drafting` role-pool suppression (~line 3151) trusts `pm_operator_role_pool_task_seen` indefinitely — … NO staleness/heartbeat/timeout. A pooled codex operator that … hangs (`codex exec` never returns; observed 3 operators alive ~17 min) keeps `current_task_id` set forever."
- **also (true negative):** "The PRD block (`active_blocked_invalid_prd`) is a TRUE negative — the autopilot scaffold prd.md genuinely lacks 7 of 11 schema sections" (F-040).
- **fixed by:** `8341fc5a` (bounded `SOLAR_ROLE_POOL_INFLIGHT_TIMEOUT_SECONDS` default 900 + `ORCHESTRATION_WEDGE_NOT_PRODUCT_PROOF` classification + wrapper wedge detection) · **tests:** 3 new deterministic (2 bash + 1 pytest), regression suites green · **live revalidated:** **no** ("deterministic-only … a fresh live run could still end INCOMPLETE, just now with a terminal diagnostic") · **still open:** the underlying codex-operator hang and PM PRD quality.
- **classes:** #1/#3 (epic shape), #22 (secondary finding: "wrapper cleanup … coordinator/watchdog daemons SURVIVE and the watchdog RESPAWNS the coordinator → orphaned quota burn" — F-043).

### F-040 — PM PRD scaffold genuinely incomplete (7 of 11 schema sections missing) — PM/report quality, **open**.

### F-043 — Wrapper cleanup does not kill coordinator/watchdog; watchdog respawns coordinator
- **sources:** F-039 secondary finding; RSI memory repeats it at v7 ("wrapper cleanup AGAIN left them"), v8 ("coordinator RESPAWNED, survived first kill"), v9 · **class:** process cleanup (#22) · **still open:** **yes** — killed by exact PID manually every run; no committed fix found.

---

## Phase E — Bounded RSI demo, runs v1–v10 (2026-07-02 → 2026-07-03)

Prompt: "Give me a deep research report on Recursive Self-Improving Models in HTML format", bounded single sprint (`SOLAR_DEMO_REPORT_MODE=1` bypasses epic decomposition — built in `f7febf00`), Codex-only, offline 9-source seed pack. Branch `feat/rc8-demo-golden-path` (11 code commits + 3 docs commits, NOT pushed). Primary surviving evidence: the five committed diagnosis docs + memory `rc8-demo-golden-path` (bundles lost).

Each run below exposed **exactly one new blocker**; content, when produced, was consistently valid.

### F-044 — v1: builder node stalls at capsule admission (`task_type=implementationworker`)
- **run:** `sprint-20260703-033355-…-81b566e9` @ `f7febf00` · **diagnosis:** `docs/product/rsi-demo-builder-stall-diagnosis.md`
- **graph:** PM ✅ Planner ✅ (PRD 2055B, 52KB task_graph, B1..B5+V1); **B1 `assigned`, never executed**; 0/5 artifacts; no route-proof
- **root cause (proven, file:line):** `_graph_node_task_type` (graph_node_dispatcher.py:6613) returns the **logical-operator NAME** (`ImplementationWorker` → lowercased `implementationworker`) as `--task-type`; capsule `cap.requirement-compiler-implementation` admits `{implementation, debugging, refactor}` → `admission_failed` → pane fallback `pane_not_idle` → node stuck `assigned` with no escalation. "This is a semantic mismatch: the envelope carried a role/operator identity where the capsule expects a task classification."
- **class:** #4 (operator/capsule/task_type mismatch — **third instance**) · **fixed by:** `a3d39ca2` (+`builder_node_liveness.py`, stall marker, role-compat invariant) · **tests:** +23 new · **live revalidated:** v2 ("S1 envelope task_type=implementation … NO stall marker").

### F-045 — v2: evaluator contention escalates S2 to `needs_human_review`, which dependency-blocks the whole report
- **run:** `sprint-20260703-044556-…-247c1aea` @ `a3d39ca2` · **diagnosis:** `rsi-demo-s2-human-review-diagnosis.md`
- **node history:** S1 passed (real eval); S2 `eval_dispatch_failures: 8/8, last_eval_result: DISPATCH_FAILED, last_eval_reason: evaluator_temporarily_busy` → `needs_human_review`; S3/S4/S5 `graph_node_dependency_blocked_terminalized` (graph_node_dispatcher.py:2883); `needs_human_review ∈ DEPENDENCY_BLOCK_STATUSES` (graph_scheduler.py:43)
- **artifact state:** S2 output deterministically VALID (9 sources, 18 claims, 0 dangling links, no placeholders) — the gate blocked *valid* work because the **single OpenAI evaluator** was busy on S1
- **classes:** #8 (evaluator capacity) + #9 precursor · **fixed by:** `1f99dd25` (12-condition bounded-mode auto-resolution → `passed_with_review_warning`) · **tests:** +14 · **live revalidated:** v5 (fired live 3×) — and immediately exposed F-048.

### F-046 — v3: planner nondeterminism defeats the v1 fix — task_type authority belongs to the *resolved capsule*
- **run:** `sprint-20260703-055227-…-7b880653` @ `1f99dd25` · **diagnosis:** `rsi-demo-dispatch-task-type-authority-diagnosis.md`
- **root cause (proven):** this run's planner resolved S1 to `cap.requirement-compiler-audit` (admits `{audit_inventory, documentation, reporting, evidence}`); the v1 fix's `logical_operator→implementation` map produced a non-admitted type. The correct value `audit_inventory` **was already resolved and present** in `S1-physical-plan.json` — "the task-type resolver just didn't read it." Mechanism: `_ensure_execution_plan_payload` writes the resolved plan into `text_payload`, not `node`; the resolver read `node`. "**Why v2 passed and v3 failed: planner non-determinism** … v2 succeeded by luck."
- **classes:** #1 (planner DAG nondeterminism) + #4 (**fourth instance**) · **fixed by:** `34d5c921` (capsule-admission-aware priority chain; never submit a non-admitted type; unresolvable → deterministic `DISPATCH_TASK_TYPE_NOT_ADMITTED_BY_RESOLVED_CAPSULE`, no silent pane fallback) · **tests:** +10 · **live revalidated:** v4 ("submit_error NONE … R1 capsule=implementation, task_type=implementation, admitted").

### F-047 — v4: full pipeline green; run failed only on the demo validator's own regex
- **run:** `sprint-20260703-…-012e6eb0` @ `34d5c921` — ALL 5 artifacts produced (report.html 14KB, 9 sources, 27 claims, 0 dangling links); all stages OpenAI
- **failure:** `validate_rsi_demo_report.py` `\bplaceholder\b` matched the report's own sentence "No placeholder text remains" → `PLACEHOLDER_CONTENT`
- **class:** #25/#26 (validator/report-wording interaction — the report *describing* its own cleanliness self-incriminated against a naive validator) · **fixed by:** `9510c88e` (stub-token detection only) · **tests:** +14; fixed validator passes on preserved v4 report.

### F-048 — v5/v6: auto-resolution not sticky; *mechanical* evaluator FAIL (missing `research_eval_json`) flips a pass-equivalent node back to `failed_review`
- **runs:** v5 `…-4c468ea2` @ `9510c88e`; v6 `…-489d9efa` @ `9dd2d5ff` (owner-paused after review found the first patch insufficient) · **diagnosis:** `rsi-demo-sticky-auto-resolution-diagnosis.md` incl. the CORRECTION section
- **root cause (proven):** the deep-research quality gate (graph_node_dispatcher.py:8427) requires `research_eval_json`; auto-resolution had *intentionally bypassed* the evaluator, so the input was missing → synthetic FAIL → `_start_node_repair_from_eval_fail` **direct-writes** `failed_review` (:2027) bypassing the `set_node_status` rank guard → R5 never ready. The archived sidecar `…R2-eval.repair1…json` proves the FAIL was **mechanical**: `failed_conditions=["research_quality_gate"]` only; acceptance D1/D2/D3 all PASS; `errors=["research_eval_json_missing:…"]`.
- **classes:** #9 (sticky auto-resolution) + #10 (mechanical evaluator FAIL) + #12 (direct-write bypasses the status state machine) · **fixed by:** `9dd2d5ff` (insufficient — treated any `verdict=FAIL` as genuine) then `8f05dfb7` (marker-is-authority; `_is_genuine_content_eval_fail` predicate; guard at the repair choke point covering both flip routes; quality-gate obligation dropped for marker nodes; idempotent re-resolution) · **tests:** `test_sticky_auto_resolution.py` rewritten to 18 incl. v5 replay · **live revalidated:** **no** — "full R1→R5 self-completion still unproven live"; v7–v9 never re-reached the sticky path (0 auto-resolution events each).

### F-049 — v7: artifact-authoring node bound to the implementation capsule; `patch_diff` proof obligations are unsatisfiable for no-code nodes
- **run:** `sprint-20260703-155749-…-bf66d46b` @ `8f05dfb7` · **diagnosis:** `rsi-demo-artifact-node-proof-contract-diagnosis.md`
- **node:** S1 goal "transform the local source-pack metadata into … sources.json", `write_scope` = data/markdown files **only**, yet capsule `cap.requirement-compiler-implementation`, `proof_obligations` incl. `output_present patch_diff`, `check.patch_within_scope`
- **status history:** builder RAN fine (sources.json + checklist produced, functional acceptance PASS) → `S1-patch_diff_not_emitted.json (patch_diff_not_emitted_no_write_scope_targets)` → 3 genuine proof-gate FAILs → repair budget (1) exhausted → last eval `STALE_ARCHIVED (eval_generation_mismatch 0!=1)` → S1 terminal `failed` → S2/S3/S4 skipped
- **classes:** #5 (artifact node bound to patch-diff proof) + #7 (proof obligation mismatch by artifact type) · **root chooser:** static default `DEFAULT_CAPSULE_BY_LOGICAL_OPERATOR["ImplementationWorker"]` because no branch existed for workspace-artifact-writing nodes
- **fixed by:** `fe2a7d69` (bounded-mode routing branch → `cap.requirement-compiler-audit` with role-mapped admitted task_type; `ARTIFACT_NODE_PROOF_CONTRACT_MISMATCH` classifier; safety net dropping patch obligations for mis-bound artifact nodes while real code nodes keep them) · **tests:** 10/10 new + regression · **live revalidated:** **yes, twice** (v8, v9: "S1 AND S2 both resolved to cap.requirement-compiler-audit … NO patch_diff anywhere … S1 PASSED").

### F-050 — v8: wrapper validated a mid-draft report (18 ms race) → false `VALIDATOR_FAILED`
- **run:** `…-c2ec65ca` @ `fe2a7d69` — all 5 artifacts produced; final report clean; wrapper's test_command fired on file **presence** while S2 was still `reviewing`, caught a transient `TODO` (result written 13:01:23.929 vs final report 13:01:23.911)
- **class:** #15 (wrapper validation timing race) · **fixed by:** `fd83ee51` (producer-node completion gate + (size,mtime) stability + `ARTIFACT_VALIDATION_INCOMPLETE` state; helper-only) · **tests:** 13 new incl. v8-evidence replay · **live revalidated:** **yes** (v9: "47 polls all `pending` — validator NEVER fired prematurely").

### F-051 — v9: artifacts valid but in the sprint workdir, not the wrapper's workspace (write_scope path-prefix nondeterminism)
- **run:** `…-fbce668c` @ `fd83ee51` — ALL 4 nodes passed, route-proof `ok=True providers=[openai]`, all 5 artifacts VALID in `sprints/<SID>/workdir/rsi-deep-research-report/`; wrapper expected `$SB/workspace/rsi-deep-research-report/` → `expected_artifacts_missing`
- **root cause (proven):** "PLANNER NONDETERMINISM in write_scope path convention: v9 emitted `rsi-deep-research-report/report.md` (RELATIVE, no `workspace/` prefix); builder cwd=workdir … v8 emitted `workspace/…`. No workdir→workspace sync for the relative-path case."
- **classes:** #16 (workspace/workdir artifact-root mismatch) + #1 · **fixed by:** `1240285a` (wrapper-side multi-root resolution, workdir-wins conflict rule, canonical `evidence/report/` copy) — **the runtime writer was intentionally left unchanged** (owner-gated) · **tests:** 12 new incl. v9 replay · **live revalidated:** no live run after `1240285a` recorded.

### F-052 — v10: claims node `needs_human_review` again; the 12-condition auto-resolution didn't fire; ran to the 90-min ceiling
- **source:** `rsi-deepdive-vs-original-solar.md` §2 table (v10 row) + **transcript-recovered detail** (session `a1946976…jsonl`, 2026-07-03T19:19–20:51Z — recovered 2026-07-06 from `~/.claude/projects/-home-ssubr-opensolar-jiuwen-installer/`)
- **run:** launched 19:19Z from HEAD `1240285a` in fresh sandbox `rsi-demo-v10-sandbox`, "stacks all four live-informed fixes together for the first time"; env `SOLAR_DEMO_REPORT_MODE=1`, `SOLAR_FORCE_SINGLE_SPRINT=1`, `SOLAR_ALLOW_EPIC_DECOMPOSITION=0`, `SOLAR_BUILDER_NODE_RESULT_TIMEOUT_SEC=300`; `--timeout-seconds 5400`
- **outcome (verbatim from closeout):** "ran to the **full 90-min timeout** (poll 171), `status=active` / `artifact_state=pending` the entire time … S2 (claims) escalated to `needs_human_review` from evaluator contention (`evaluator_temporarily_busy`, 8 dispatch failures), the bounded-demo auto-resolution didn't fire, so S3–S5 were dependency-skipped. No report artifacts were ever produced."
- **what worked:** "the wrapper stayed `pending` throughout and never emitted a false `VALIDATOR_FAILED` — the timing (`fd83ee51`) and root-resolution (`1240285a`) fixes behaved correctly." Cleanup again required manual daemon kills (watchdog first) — F-043 recurring.
- **classes:** #8 + #9 + #1 — the auto-resolution's 12 conditions were shape-matched to earlier runs' nodes and did not match v10's S2; per-shape conditional patches cannot keep up with nondeterministic graphs.
- **still open:** yes — this is the terminal data point of the generic-path chain and the direct motivation for the workflow lock (designed the same day, `568fbb81`/`328f0c0b`, committed while v10 was still running).

### F-053 — Meta-failure: planner DAG nondeterminism (class #1, the umbrella)
- **evidence across runs:** v4=R1–R5, v7=S1–S4, v2=S1–S5, v9 write_scope prefix flip, v3 capsule flip. "Same input → different run every time" (`rsi-deepdive-vs-original-solar.md` §1 table).
- **consequence (proven pattern):** every reshuffle exposed a different capsule/proof/artifact-root bug; **content was fine** ("v8/v9 produced valid 5/5 artifacts; the validator passed on the finalized files. The failures were all orchestration-substrate failures").
- **still open:** yes — by design of the generic path; addressed only by the workflow lock.

### F-054 — The DeepDive front door was dropped during OpenSolar packaging (root architectural finding)
- **evidence (proven by cloning lisihao/Solar):** original ships `harness/lib/research/deepdive_requirement_compiler.py` (`is_explicit_deepdive_request()`, `build_deepdive_evidence_dag()` fixed D1–D9, `dag_variant=deepdive_research` guard, `OPERATOR_MAPPING` stating "never returns standard/research PM DAG"), plus `deepdive_brief_expander.py` and `research/profiles/` — **all MISSING from OpenSolar**, while the downstream engine (`cli.py`, `state_machine.py`, `evaluator.py`, `survey/*`, `research eval-artifacts`) survived in-repo.
- **consequence:** research requests fall through `should_epic_decompose_request` → PM epic → LLM planner. "OpenSolar kept the DeepDive **engine** but lost the **router**."
- **classes:** #2 (root of), #1, #3 · **fix state:** design committed (`568fbb81` + `328f0c0b`), **not built**.
- **REFINEMENT (2026-07-06, verified in-repo):** the compiler was never on `main` at all (`git ls-tree -r main | grep -c deepdive` = 0) — the baseline snapshot the productization forked from **predates/excludes the DeepDive merge**. The file lives on Sihao's side branches **inside this repository**: `upstream/codex/evaluator-control-plane`, `upstream/codex/evaluator-sidecar-closeout`, `upstream/codex/graph-eval-drain-routing`, `upstream/codex/pr13-main-conflict-resolution`, `upstream/codex/eval-quota-requeue` (commits `96b9e140`/`9de0586f` "Complete DeepDive insight runtime core" touch `deepdive_requirement_compiler.py` ±355 lines, `research/profiles/`, `insight_gates.py`, and ship `test_deepdive_requirement_compiler.py`). So the restore is `git show <upstream/codex ref>:harness/lib/research/deepdive_requirement_compiler.py` — no external clone required. This also reframes the drop: it wasn't a packaging deletion; **the fork point was a main lineage that never carried the research router**, and nobody inventoried the side branches before productizing.

### F-055 — Deep-research synthesizer emits hardcoded boilerplate as report body — memory `deepresearch-synth-hardcoded-content` (`lib/research/cli.py`). Class #25 (report quality). **Open**; must be fixed before the DeepDive engine is put on the demo path.

### F-056 — `classify_task_goal` misbinds "benchmark" research to a perf-debug capsule → unsatisfiable proof obligation — memory `s2a-capability-misbinding`. Same family as F-049 at the classifier layer. **Open.**

---

## Phase F — Dashboard/demo readiness and hygiene (2026-07-03 →)

### F-057 — Demo readiness: Track B recordable, Track A runtime-gated (recovered from transcripts 2026-07-06)
- **source:** session `a8f9afa9…jsonl` (2026-07-03T16:09–16:16Z) + `a1946976…jsonl` (Demo Recording Package Agent, 20:35Z). The `/tmp` files are lost but the full assessment survives in-transcript.
- **Track A (strict dashboard-initiated live run) — blocked, two reasons, both outside the dashboard:** (1) "The four demo env vars are inert on the installed runtime. I grepped `~/.solar/harness` and this repo branch: zero hits for `SOLAR_DEMO_REPORT_MODE` … They exist only on the rc8 demo branch"; (2) "Completion needs live workers. `/intake` only creates the sprint." Plus the then-open R2 `failed_review` fix. Also recorded: Electron not required (record in a browser); `/app` is a 404, root URL only.
- **Track B (real-artifact presentation) — "fully rehearsable today and is the safety net":** dashboard B-roll + real completed report output + caption "long-running execution compressed"; 11-shot list (`dashboard-recording-shotlist.md`): shots 1–4 must be genuine dashboard captures, 6–11 may come from Track B real artifacts, "never a fabricated completion."
- **artifact survival:** the v4 run's complete 5/5 artifact set was copied to **`C:\Users\ssubr\Downloads\rsi-demo-v4-report\`** (opened in the Windows browser 2026-07-03T17:03Z) and the recording package was also copied to C: — so real demo artifacts survive on the Windows side even though every `/tmp` copy is gone. v4 vs v5 comparison recorded: v4 = complete 5/5 incl. evaluation-checklist; v5 report is longer/stronger (~21KB vs ~10KB text) but its set is incomplete (R2→R5 bug).
- **class:** dashboard readiness (#23) · **still open:** Track A remains gated on the workflow lock reaching ladder P3.

### F-058 — Runtime artifacts leak into the repo working tree
- **evidence (live, right now):** untracked `countletters.py` (a Phase-C-style CLI deliverable), `utils.py`/`test_utils.py` (palindrome helper — a builder artifact), `special_breakdown_document.md` in the repo checkout root; the RC8 handoff repeatedly warns not to stage `harness/.pm/*`, `physical-operators.json`, `uniqwords.py`, `striptrail.py`, `trimblank2.py`.
- **classes:** #21 (contamination) + #22 (cleanup) · **interaction hazard:** repo SessionEnd hook auto-commits `git add -A` (memory `session-end-autocommit-hazard`) — runtime dirt can be committed silently. **Open.**

### F-059 — Two divergent copies of core runtime modules (`lib/` vs `tools/`)
- **evidence:** arch audit P1-3; `7f9718b5` routed the tools entrypoint to lib for the dispatcher; `ff35c302`/`714eb781` had to patch **both** copies. RUNTIME-VERIFICATION-AUDIT (06-26) lists "B2 divergent tools/ vs lib/ dup modules". **Partially fixed** (dispatcher); other modules open.

---

## Phase A′ — The pre-KB era, 2026-06-19 → 06-26 (added 2026-07-06 from session memories; raw transcripts in `-tmp-solar-codex-runtime-validation-*` dirs remain unmined)

The owner correctly challenged that the corpus was a subset. This pass mined the June-era memory
distillations and found ~10 additional instances and **two new classes** (F-CLASS-29/30 in the taxonomy).

### F-060 — Verifier mis-routed to a builder; orphaned PASS eval with no consume path; scanner dormancy
- **runs:** `8ecfa91b` (2026-06-21), `c63ba5bd` (burned test vehicle) · **source:** memory `runtime-pipeline-walls`
- S1/S2 passed genuinely, S3 (Verifier) **reviewed PASS on disk but the parent never closed**: (i) `_role_penalty` let an evaluator-role node fall back to a builder pane; (ii) a handoff-less Verifier had **no code path that consumes its eval** (reconcile requires a handoff; `_node_eval_needed`=False once eval.json exists); (iii) the edge-triggered scanner never re-woke (eval artifacts are unwatched files). Also established the rule: hand-run node-verdicts pollute the sprint (stale dispatch_id → `no_pane`) — burned two test vehicles.
- **classes:** role selection + supervision + termination · later properly fixed at operator level by role-compatible selection (`cfbe0e26`/`ce046b31`).

### F-061 — G_REVIEW certified on node *completion*, not verdict *content* (NEW CLASS 29)
- **run:** LDES deep-research `de49b5a4` (2026-06-23) · **source:** memory `n7-final-accept-fail-greview-bug` + patch file `~/opensolar-state/0001-runtime-G_REVIEW-gate-*.patch`
- N3 critic node `passed` while its verdict said **block**; N5 verifier node `passed` while `verifier_decision.json` said **FAIL**; G_REVIEW read only node STATUS, so a transient pass **auto-closed the sprint and exported to the knowledge vault with coverage=0** before the evaluator reverted it.
- **fixed by:** `5fcff602` (feat/p0-gui-react) — and **independently** by `983ce35a` on the codex branch, then re-landed as `949d3e3c` on the backbone. Memory `greview-fix-not-active-in-runtime` records the drift hazard: the fix existed on one branch while the installed runtime lacked it.
- **plan:** gates read ledger verdict records, fail-closed when a verdict artifact is missing (R4).

### F-062 — Verdict provenance not structural: doctor-backfilled / self-graded eval JSON (NEW CLASS 30)
- **sources:** memories `eval-json-backfill-vector`, `live-intake-codex-findings`, `claude-e2e-not-proven` (thin eval.json: `reasons:null, has_evidence:false` while the real reasoning sat in eval.md)
- eval.json could be written by the scheduler doctor (`generation_mode=repair_backfill`) or reflect a self-graded builder verdict with no independent eval report — a latent hollow-pass vector, safe only because a human checked the .md each time.
- **fixed by:** `d61d92a2` (narrow) → `4df6477d` (broad: an executor node with a verdict but no independent eval report never passes; two entry points closed) · **plan:** ledger records carry author + generation; the evaluator writes its own verdict record (R4).

### F-063 — Proof-gate fake attestation: guard/resource sidecars demanded but never emitted; the "check" was narrative
- **date:** 2026-06-21 · **source:** `runtime-pipeline-walls` · the LLM's `check.guard_decision_written` flag was prose — no real secret scan existed. **Fixed `99b9a9fe`:** deterministic sidecar emission with a real pattern scan (verified with a planted secret → `block`). Ancestor of the patch-proof family (F-024) and the deterministic-gates principle.

### F-064 — Front-half fire-once dispatch latch with no liveness; 15-minute cooldown pairs; pane-hygiene state persisting across restarts
- **sources:** memories `runtime-completion-fixes-proven`, `runtime-completion-cooldown-hardens`, `codex-pane-dispatch-blockers` · any post-send failure stalled a run forever (`.drafting-flow-dispatched` never cleared); two 900s cooldowns stacked; `needs_respawn` from 06-23 still blocking dispatch on 06-25.
- **fixed by:** Fix 0/1/4 (drafting liveness reconcile, artifact backfill, clean-start reset — `566d0aa4`), cooldowns 900→90 · **class:** supervision (F-CLASS-28), earliest era.

### F-065 — Over-broad "usage limit" regex false-matched a benign codex banner → `pane_not_idle` forever (CLI drift; runtime-only regex fix, 2026-06-25).
### F-066 — Revoked Codex auth cached in long-lived panes; `codex login status` false-positive (auth files exist ≠ token valid). Class 20.
### F-067 — Termination-truth trio on the codex e2e bring-up (2026-06-24): mid-run `acceptance_verdict=FAIL` poisoned every node (`7aa029fe` → IN_PROGRESS); post-close scan **reopened finalized sprints** (`13a43861` → finalized-is-frozen); coverage stuck IN_PROGRESS (`65d835ec`).
### F-068 — Model alias trap: bare `sonnet` mapped to `zhipu-glm-4.7`; only `anthropic-sonnet` reached Claude (memory `sonnet-e2e-proven-and-runtime-walls`). Class 19.
### F-069 — Cross-era recurrence proof: stale repair-eval sidecars were fixed on 2026-06-23 (`108c245b` "ignore stale repair eval sidecars") and the same class was fixed AGAIN in rc8 (`70a7b914`, `714eb781`) on a different lineage six days later — the strongest single datum that fixes without a contract layer don't stay fixed across branches.

**Positive-evidence notes from the same era:** Claude-Sonnet full e2e proven 2026-06-24 (`9dfb3dae`, S1–S5 passed, independently verified); Codex e2e proven across three task classes the same day; native `codex --search` made the scraper pipeline unnecessary. The audit capsule itself (`c2203137`) was *added during productization* on 06-23 — it is not baseline.

---

## Chronological fix-chain summary (one line per live run that drove a fix)

| # | Date | Run | HEAD | Exposed | Fix |
|---|------|-----|------|---------|-----|
| 1 | 06-27 | 50-sprint survey | installed rc4 | no live workers | operational + `0e0429ef`/`a846252b` |
| 2 | 06-28 | Run D `083ff55f` | installed | 246× eval dispatch, no terminal | `62e0c9ac`, `703e6c27` |
| 3 | 06-28 | Run F `214d41bf` | +703e6c27 | gemini op selection; manual driving | pinning → `d3e9b690` |
| 4 | 06-28 | Run G `0f845c74` | d3e9b690 | malformed YAML closeout; mislabeled op | `56079fd6`/`9f2d7f35` |
| 5 | 06-28 | Run H `d08c0658` | f550b7d4 | — first fully-green Claude DAG | (verification) |
| 6 | 06-29 | `48d4a770` | c6ef0190 | planner gate stall; orphan procs | chain below |
| 7 | 06-29 | `ce61db90` | 8ad8cfb2 | stale eval gen; busy-vs-absent evaluator; no closure | `70a7b914`, `5ba3bdee` |
| 8 | 06-29→30 | `204f7cfd` (dirty) | 73387de9→2a8ab9db | rc=139; stale lease; stale-result correlation | `83575bab`, `73387de9`, `2a8ab9db` |
| 9 | 06-30 | clean `countchars` | 2a8ab9db | patch-proof discovery | `ff35c302` |
| 10 | 06-30 | clean `75c79ef1` | ff35c302 | doctor backfill stale eval; dup repair dispatch | `714eb781`, `792f6a2b` |
| 11 | 06-30 | clean (planner) | a85adc43 | installed-harness fallback | `cb2cc504`, `713201b0`, `a8203924` |
| 12 | 06-30 | clean `ab795810` | a8203924 | — **first clean Codex-only green DAG** | (stale parent status, N/A attribution remain) |
| 13 | 06-30 | web-research epic | 714eb781 | research → software epic, S01 wedge | design issue — no patch |
| 14 | 07-01 | integration smoke | 154a1d48 | missing S1-patch.diff | `92c5615d` |
| 15 | 07-01 | integration smoke | 92c5615d | repair terminalization race | `cd528d0a` → **smoke PASS** `c42d1e2f` |
| 16 | 07-02 | local-research-report | 86643597 | S01 wedge (inflight no-timeout) | `8341fc5a` (det-only) |
| 17–25 | 07-03 | RSI v1–v9 | f7febf00→fd83ee51 | one new blocker per run (F-044…F-051) | `a3d39ca2`…`1240285a` |
| 26 | 07-03 | v10 (summary) | — | needs_human_review again, shape-mismatch | **workflow-lock design** `568fbb81`/`328f0c0b` |

## What this corpus proves vs what it infers

**Proven:** every file:line root cause in the five RSI diagnoses; the run E/F/G/H mechanics; the Phase C fix chain and green runs; the DeepDive compiler absence (clone comparison); the epic decomposition of research prompts (live report); the fact that the *content* engine repeatedly produced valid artifacts while the orchestration substrate failed.

**Inferred (marked):** Track A/B readiness detail (evidence lost); the continuity between `ba1dd657` (rc5) and the v7 proof-contract failure (same class, different layer — strong but circumstantial); exact dates for a few undated commits.

**Unknown → resolved 2026-07-06 via transcript archaeology:** a run after `1240285a` DID happen (v10, see F-052) and deadlocked at S2 `needs_human_review` — the bounded demo has still never completed 5/5 + route-proof end-to-end. **Still unknown:** current state of the installed `~/.solar/harness` relative to any branch; contents of the lost paperfilter run bundle.

---

## Appendix — Branch / worktree / transcript inventory (added 2026-07-06)

### Local branches and lanes (beyond the runtime lineage covered above)
- **GUI lane:** `feat/p0-gui` (06-16) → `feat/p0-gui-backend-integration` (06-23; includes `949d3e3c` "G_REVIEW gate consumes verifier/critic verdicts — port 5fcff602 to engine lane") → `feat/p0-gui-react` (06-26, current checkout).
- **CLI honesty lane:** `cli/batch1-honesty` @ `a0e4501a` (06-14; worktree `~/opensolar-batch1`, clean except node_modules) — front-door footgun removal, dead-config honesty, personal-text scrub, hooks DB-path fix.
- **CI lane:** `ci/cross-os-smoke` @ `0d031ce8` (06-28) — WSL bind-host/false-green fixes.
- **Packaging lanes:** `fix/rc8-packaging-install-hardening` (= pushed rc8 desktop fixes), `fix/rc8-macos-bootstrap-fix` @ `97f13dcc`, `feat/macos-launcher` (06-16), `feature/setup-wizard` (= `c48507fb`, 0 ahead of upstream).
- **Baseline snapshots:** `main` = `archive/personal-history` = `a3a0ecaa` (contains 278 committed sprint/epic dirs, `SPRINTS-HIGHLIGHTS.md` with 46 passed sprints — mostly Solar-fixing-Solar — and Sihao's May-2026 radar/insight epics, one spot-checked `passed/completed`).
- **43 `harness-builder-*` branches** (06-19 → 06-24): auto-created by the runtime's own builder commits — the harness committing to its own repo; untriaged.
- **26 `upstream/codex/*` branches:** Sihao's Codex PR branches carrying capabilities never merged to main — DeepDive compiler (5 branches, F-054 refinement), browser-webwright bridge, chatgpt-report-operator, gpt-requirement-writer, evaluator-control-plane, capsule-proof-adapter-runtime, etc. **These were never inventoried before productization** — the corpus's fork-point finding.

### Transcript archive (authorized by owner, surveyed 2026-07-06)
- **Claude:** 44 project dirs under `~/.claude/projects/` relate to Solar — main dir 242MB; plus per-worktree dirs for the wiped `/tmp` sandboxes (`-tmp-solar-codex-runtime-validation-*` ×~20 from the 06-23/24 era, `-tmp-solar-rc8-runtime-mode-contract-harness`, `-tmp-opensolar-demo-workspace`, …) and `-home-ssubr--solar-harness` (97 sessions — Claude running *inside the installed harness*, i.e. runtime pane transcripts). Key recoveries already folded in: v10 outcome (F-052), Track A/B (F-057).
- **Recoverable lost documents (not yet re-extracted):** `/tmp/solar-research-epic-design/` — a research-native epic template (`S01 scope-contract → S02 source-inventory → S03 claim-extraction → S04 synthesis-report → S05 verification-release`, replacing `epic_decomposer.py`'s software slices; the epic-level counterpart of the workflow-contract plan) in session `d1a4ad60…jsonl`; `/tmp/solar-claude-readiness/claude-demo-readiness.md` (Claude-only backup Go/No-Go, 9 hard gates) in session `463cc399…jsonl`.
- **Codex:** `~/.codex/sessions` = 738 files / 704MB, but these are the owner's own codex-lane sessions; the RSI-demo builder runs left **no transcripts** (`codex exec --ephemeral` with harness-owned state home per `b8a527ce`) — by design, at the cost of losing builder-side evidence.
- **Windows-side survivors:** `C:\Users\ssubr\Downloads\rsi-demo-v4-report\` (complete v4 5/5 artifact set) + a C: copy of the recording package.
