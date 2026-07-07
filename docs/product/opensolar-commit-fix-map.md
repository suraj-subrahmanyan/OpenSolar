# OpenSolar Commit-to-Fix Map

**Date:** 2026-07-06. Companion to `opensolar-failure-corpus.md` (F-xxx) and `opensolar-failure-taxonomy.json` (F-CLASS-xx).

Hash convention: `original / integrated` where the same change exists on two lineages
(`feat/runtime-fixes` → `upstream/openJiuwen-Solar`; `rc8-runtime-mode-contract` → `integration/rc8-runtime-mode-contract`).
"Live revalidated?" means a later live run exercised the fixed path and it behaved (not merely "a later run happened").
"Still risky?" = residual risk noted in evidence, not a new judgment.

## Phase A/rc6 — runtime lane (feat/runtime-fixes → upstream)

| commit | branch | problem fixed | failure class | tests added | live revalidated? | still risky? |
|---|---|---|---|---|---|---|
| `0e0429ef` / `2729e974` | feat/runtime-fixes | codex not reachable via multi-task pool (profiles) | F-CLASS-27 | config-only | yes (codex Runs B/C) | no |
| `a846252b` / `c62ad1da` | feat/runtime-fixes | deliverables landed in harness root; per-sprint work_dir | F-CLASS-16 | — | yes (Run D onward) | root convention still non-contractual (v9) |
| `62e0c9ac` / `0344d159` | feat/runtime-fixes | 246× silent eval-dispatch retry; no durable attribution | F-CLASS-08, attribution | 8 unit + Run-D replay | yes (Run F; RSI v2 escalation fired as designed) | escalation lands on dependency-blocking `needs_human_review` (F-045) |
| `703e6c27` / `ec8caff1` | feat/runtime-fixes | evaluator pool gated behind builder-pool flag | F-CLASS-08 | — | yes (Run F: 3 real pool evals) | singleton evaluator contention remains |
| `d3e9b690` / `0e4842b3` | feat/runtime-fixes | manual DAG driving; broken-operator re-selection | F-CLASS-27, F-CLASS-19 | unit (cooldown) | yes (Run G self-advanced + clean exit) | — |
| `2155c1be` / `cb18f8b0` | feat/runtime-fixes | default providers included unusable gemini/glm/local | F-CLASS-18/19 | replay-verified | no live at commit time | registry hygiene open (G7/G8) |
| `cfbe0e26` / `ce046b31` | feat/runtime-fixes | builder nodes picking planner/evaluator operators | F-CLASS-19 | replay-verified | indirectly (later runs) | — |
| `56079fd6` / `9f2d7f35` | feat/runtime-fixes | malformed YAML/JSON closeout artifacts | F-CLASS-11 | — | **yes (Run H: review_decision.yaml parses, S3 PASS)** | builder quality on closeout still weak (G14) |
| `09d47d0e` / `23b9039f` | feat/runtime-fixes | operators with missing CLI selected | F-CLASS-19 | unit | indirectly | health not yet a hard preflight |
| `a1105f82` / `c710b732` | feat/runtime-fixes | cockpit sprints don't self-complete | F-CLASS-27 | gated flag | **inert until cockpit restart** — later segfaulted (F-025) | yes at the time |
| `f550b7d4` / `7f33eb67` | feat/runtime-fixes | slow/deprecated opus evaluators | F-CLASS-19 | — | yes (Run H sonnet evals) | — |
| `d2edac3d` | feat/dashboard-overhaul | 30s intake shell-out timeout | dashboard | — | yes (Run D intake) | — |

## rc7/rc8 packaging (pkg/migration, pushed)

| commit | branch | problem fixed | failure class | tests added | live revalidated? | still risky? |
|---|---|---|---|---|---|---|
| `1d9fddf0` | pkg/migration | Ubuntu 24.04 PEP-668 pip bootstrap | F-CLASS-24 | CI smoke | CI yes; user-path partial | — |
| `a10dfcfe` | pkg/migration | artifact serves stale installed harness | F-CLASS-24 | local checks | **artifact acid test still gated** | yes |
| `446a1c5b` | pkg/migration | tracked persona symlink to private path | F-CLASS-24 | prepackage check | local yes | raw ../harness bundling fragile (G9) |
| `c48507fb` | pkg/migration | prepackage false-fail on frontend node_modules | F-CLASS-24 | negative symlink test | Desktop Build green (user-reported) | — |
| `e2749449` | upstream | macOS must install bundled runtime first | F-CLASS-24 | — | no clean-Mac proof | yes |
| `ba1dd657` | pkg/migration (rc5) | research nodes bound code-capability capsules | F-CLASS-05 (earliest) | — | unknown | class recurred at proof layer (v7) |

## rc8 runtime-mode contract (rc8-runtime-mode-contract / integration/rc8-runtime-mode-contract)

Ordered as committed (original lineage). All were local-only until the upstream push recorded in the KB.

| commit | problem fixed | failure class | tests added | live revalidated? | still risky? |
|---|---|---|---|---|---|
| `94922d9a` / `27fdcfc4`, `b787e9be` | route selectors resolve roles to selected provider family | F-CLASS-18 | selector subset 68/68 | partial (static route proof) | route truth in artifacts still lied later |
| `c6ef0190` / `8e7f1dcf` | Codex route observable + non-deprecated; node-keyed pool attribution | F-CLASS-18/19 | 18/18 capability+PM | partial | — |
| `5f994ae7` / `fbb5ab6e` | `analysis` label not admitted by audit capsule | **F-CLASS-04 (1st)** | tests+replay | partial (S1 dispatched openai) | class recurred 3 more times |
| `8ad8cfb2` / `562b652d` | provider routes fail closed; codex DAG unblock | F-CLASS-18 | subset green | yes (`ce61db90` route held) | exposed F-021/22/23 |
| `70a7b914` / `d09e1ed0` | stale pre-repair eval accepted; failed deps never terminalize | F-CLASS-13, F-CLASS-12 | replay tests | partially (later runs archive stale evals) | doctor-backfill variant survived until `714eb781` |
| `5ba3bdee` | busy singleton evaluator ≠ absent evaluator | F-CLASS-08 | deterministic | yes (v2 shows `evaluator_temporarily_busy` classification) | contention itself unsolved |
| `b8a527ce` / `e48a0612` | codex exec context (work_dir/CODEX_SQLITE_HOME/--ephemeral) | F-CLASS-28 | contract tests | yes | PM-path envelope lagged (arch audit P0-3) |
| `73387de9` / `0b715b52` | dead-PID stale lease blocks selection | F-CLASS-28 | unit | yes (S3 eval recovered live) | status-server split-brain open (P0-4) |
| `83575bab` / `8ad0da81` | rc=139 evidence capture (observability only) | F-CLASS-28 | bash -n | n/a | root cause was elsewhere |
| `2a8ab9db` / `0c66ae6a` | fresh eval closed by stale result (PM-task correlation) | F-CLASS-28 | 29 pytest | yes (diagnostic run reached terminal) | — |
| `ff35c302` / `c7783029` | node patch artifacts undiscoverable; false-positive presence fallback removed | F-CLASS-06 | graph 32 | yes (later green runs) | — |
| `714eb781` / `d00903ab` | eval generation contract + duplicate node dispatch guard | F-CLASS-13, F-CLASS-12 | 37 + 102 subset | yes (v7 shows mismatch archiving) | live repair loop still never green |
| `792f6a2b` / `fcee2d97` | Python 3.13 readline/locale segfault (the real rc=139) | F-CLASS-28 | locale test | yes (self-complete ticks work after) | — |
| `a85adc43` / `6578bb9d` | legacy Claude planner pane races codex role pool | F-CLASS-18 | control-plane bash | yes | — |
| `cb2cc504` / `63769097` | operator shell falls back to installed ~/.solar | **F-CLASS-21** | 9 pytest | yes (a8203924 clean run) | installed-copy drift remains a standing hazard |
| `713201b0` / `d9dc0ab4` | `tests` task_type rejected by implementation capsule | **F-CLASS-04 (2nd)** | 21 subset | yes | — |
| `a8203924` / `d2339f21` | synthesize node patch sidecars from write-scope | F-CLASS-06 | patch-proof tests | **yes — first clean Codex-only green DAG (`ab795810`)** | synthesized patch is weaker proof than a worker diff |
| `b20e44d3` | tests guarded against installed-harness contamination | F-CLASS-21 | itself | n/a | — |
| `7f9718b5` | tools/ dispatcher entrypoint routed to lib (drift) | F-CLASS-59/dup-modules | — | n/a | other dup modules remain |
| `f01e81e2` | isolated live E2E harness | (enabler) | 231-line test file | — | — |
| `f26ce84b` / `8310a149` | Codex auth lost in sandbox | F-CLASS-20 | — | yes | — |
| `154a1d48` / `2523d7b6` | gpt-5.5 / codex-spark missing from model registry | F-CLASS-19 | registry CLI checks | yes (smoke used aliases) | — |
| `2db50662` / `bc48eb82` | route proof artifact + stale operator status recovery | F-CLASS-17 | route-proof tests | yes (smoke route-proof ok) | per-stage route records still terminal-node-dependent |
| `7bd02a10` / `3099bd95` | repo workspace treated as dispatch-provisioned | F-CLASS-16 | — | yes | — |
| `30169c80` / `5b9b1e88` | closeout/command attribution sync | F-CLASS-18 (truth) | — | partial | plan-artifact lying + N/A attribution still open |
| `92c5615d` | patch proof emitted from sidecar-shaped obligations | F-CLASS-06 | exact failed-shape tests | yes → exposed repair race | — |
| `cd528d0a` | parent graph terminalized during active repair | F-CLASS-12 | repair lifecycle tests | **smoke PASS `c42d1e2f` (repair not triggered live)** | live repair unproven |
| `ad4f2551`, `dc0e015a` | docs: smoke review + regression matrix | — | — | — | — |

## Validation + wedge fixes (wrapper lane)

| commit | branch | problem fixed | failure class | tests added | live revalidated? | still risky? |
|---|---|---|---|---|---|---|
| `c8bda26e` | validation/* | wrapper blind to epic children | F-CLASS-14 | 231 test lines | yes (all later validations) | — |
| `86643597` | validation/* | no artifact validation mode | F-CLASS-17 | +315 test lines | yes | presence-triggered validation later raced (v8) |
| `8341fc5a` | fix/rc8-s01-prd-gate-wedge | role-pool inflight suppression unbounded; wedge unclassified | F-CLASS-28, F-CLASS-02 symptom | 3 deterministic | **no (deterministic-only)** | underlying codex hang + PRD quality untouched |

## RSI demo golden path (feat/rc8-demo-golden-path, NOT pushed)

| commit | problem fixed | failure class | tests added | live revalidated? | still risky? |
|---|---|---|---|---|---|
| `f7febf00` | epic decomposition bypass for bounded demo; seed pack; validators | F-CLASS-03 (scoped) | 40 bash+pytest | yes (v1 produced single sprint) | demo-mode-gated only |
| `a3d39ca2` | builder admission got logical-op NAME as task_type | **F-CLASS-04 (3rd)** | +23 | **yes (v2)** | superseded edge → v3 |
| `1f99dd25` | evaluator-unavailability escalation blocks report DAG | F-CLASS-08 | +14 | fired live in v5 (then F-048) | policy-as-status design flaw |
| `34d5c921` | task_type authority = resolved capsule, not logical-op map | **F-CLASS-04 (4th)** | +10 | **yes (v4: submit_error NONE)** | — |
| `9510c88e` | validator `\bplaceholder\b` false positive | F-CLASS-26 | +14 | fixed validator passes v4 report | — |
| `9dd2d5ff` | sticky auto-resolution v1 (insufficient) | F-CLASS-09 | 8 | **no — disproven by v5 evidence review** | superseded |
| `8f05dfb7` | mechanical-vs-content FAIL predicate; marker authority | F-CLASS-09/10 | 18 (rewrite incl. v5 replay) | **no (v7–v9 never re-reached the path)** | yes — unverified live |
| `fe2a7d69` | artifact nodes bound to patch-diff proof contract | **F-CLASS-05** | 10 | **yes twice (v8, v9)** | bounded-mode-gated; global class open |
| `fd83ee51` | wrapper validated mid-draft artifacts | F-CLASS-15 | 13 (v8 replay) | **yes (v9: 47 polls pending)** | — |
| `1240285a` | workspace/workdir artifact-root divergence (wrapper-side) | F-CLASS-16 | 12 (v9 replay) | **no live run after it recorded** | runtime writer still nondeterministic |
| `568fbb81`, `328f0c0b` | docs: DeepDive workflow lock design (grounded in lisihao/Solar) | F-CLASS-01/02 design | — | design only | — |

## Reading the map

- **Real architecture improvements** (changed a contract, not a symptom): `62e0c9ac`, `703e6c27`, `d3e9b690`, `9f2d7f35`, `714eb781`+`70a7b914`, `cd528d0a`, `34d5c921`, `fe2a7d69`, `2a8ab9db`, `cb2cc504`, `154a1d48`, `2db50662`.
- **Wrapper/test-harness patches** (correct, but they harden the observer, not the product): `c8bda26e`, `86643597`, `fd83ee51`, `1240285a`, `8341fc5a` (classification half), `83575bab`, `b20e44d3`, `f01e81e2`.
- **Demo-specific / mode-gated** (behind `SOLAR_DEMO_REPORT_MODE`; do not generalize as fixed): `f7febf00`, `1f99dd25`, `9dd2d5ff`, `8f05dfb7`, `fe2a7d69` (routing branch half), `9510c88e`.
- **Four commits fixed the same class (F-CLASS-04)** at four different sites: `5f994ae7`, `713201b0`, `a3d39ca2`, `34d5c921` — the clearest single signal that task_type/capsule admission needs one contractual owner.
