# RSI DeepDive Workflow Lock

**Date:** 2026-07-06. Design (not built). This document consolidates and supersedes-in-place the two
design docs already committed on `feat/rc8-demo-golden-path`
(`rsi-deepdive-workflow-lock-design.md` @ `568fbb81`, corrected/grounded @ `328f0c0b`, plus
`rsi-demo-stage-contract.json` and `rsi-deepdive-vs-original-solar.md`). It restates the lock in the
unified workflow-contract vocabulary and records exactly why it defeats the v1–v10 failure chain.

## 1. What is being locked, and why

The demo prompt — "Give me a deep research report on Recursive Self-Improving Models in HTML format" —
is a textbook DeepResearch request currently pointed at the wrong door. Under
`SOLAR_DEMO_REPORT_MODE=1` it bypasses epic decomposition (`f7febf00`) but still enters the **generic
PM/LLM-planner**, which invents a fresh graph per run (R1–R5 / S1–S4 / S1–S5), fresh capsule bindings,
and fresh write_scope conventions. Every v1–v10 live failure was a consequence of that nondeterminism
meeting an uncontracted substrate (corpus F-044…F-053); the *content* was consistently fine (v8/v9:
valid 5/5 artifacts, validator PASS on final files).

**Decisive grounding (proven by cloning `lisihao/Solar`):** the original Solar ships the lock already —
`harness/lib/research/deepdive_requirement_compiler.py` with:

- `is_explicit_deepdive_request(text)` — explicit markers only (`deepdive`, `deep dive`,
  `deepresearch`, `deep research`, `深度研究`, `深研`, `深度调研报告`); generic "research/研究/调研"
  deliberately insufficient;
- `build_deepdive_evidence_dag(questions, insight_mode)` — a **fixed D1–D9 DAG**,
  `dag_variant=deepdive_research`, with a guard (`!= deepdive_research → invalid_deepdive_dag_variant`);
- `OPERATOR_MAPPING` stating "never returns standard/research PM DAG";
- optional D10–D18 insight overlay (not needed for the 5-artifact demo).

OpenSolar packaging **dropped** this file (plus `deepdive_brief_expander.py` and `research/profiles/`)
while keeping the downstream engine (`cli.py` with 14+ subcommands, `state_machine.py` FSM
INIT→SEARCHING→DRAFTING→METERING→RENDERING→FINALIZED, `evaluator.py`, `survey/*` gates, and the
deterministic `research eval-artifacts` quality gate). **The lock is therefore a routing decision plus
a file restore/port — not new capability.**

**Restore source (verified 2026-07-06, in-repo):** the compiler + `research/profiles/` +
`test_deepdive_requirement_compiler.py` exist on this repository's `upstream/codex/*` branches
(e.g. `upstream/codex/evaluator-control-plane`; commits `96b9e140`/`9de0586f`,
`6dca0331`/`74b74778` "Route DeepDive planning through generic insight mode", `3d14bc4d`).
`main` itself never carried them — the productization fork point predates the DeepDive merge.
Port from those refs (`git show <ref>:harness/lib/research/deepdive_requirement_compiler.py`)
rather than the external lisihao/Solar clone; diff against the clone only to confirm parity.

## 2. The two stage shapes (choose one, both are valid ports)

### 2a. Faithful port — original D1–D9

| Stage | Logical operator | Gate family | Output (demo artifact in bold) |
|---|---|---|---|
| D1 | DeepDiveBriefCapture | DD_SCOPE | scope-contract.json |
| D2 | DeepDiveSourcePlanner | DD_SOURCE | source-plan.json |
| D3 | DeepDiveSourceCollector | DD_SOURCE | **sources.json** |
| D4 | DeepDiveClaimCompiler | DD_EVIDENCE | **claims.json** |
| D5 | DeepDiveContradictionScanner | DD_EVIDENCE | contradiction-matrix.json |
| D6 | DeepDiveChapterPlanner | DD_SYNTHESIS | section-render-cards/ |
| D7 | DeepDiveChiefEditor | DD_SYNTHESIS | **report.md + report.html** |
| D8 | DeepDiveClaimVerifier | DD_REVIEW | verifier-decision.json |
| D9 | DeepDiveArtifactPublisher | DD_PUBLISH | **evaluation-checklist.md** + route-proof gate |

### 2b. Compressed demo variant — D1–D6 (as in `workflow-contract-schema.example.json`)

Scope(D1) → Sources(D2=orig D2+D3) → Claims(D3=orig D4) → Contradictions(D4=orig D5) →
Report(D5=orig D6+D7) → Verify/Publish(D6=orig D8+D9). Fewer stages ⇒ fewer evaluator-gate passes
through the singleton OpenAI evaluator ⇒ lower contention risk (the v2/v5/v10 killer) and fits the
~25-minute wrapper budget. Recommendation: **ship 2b for the bounded demo**, keep 2a as the general
`research.deepdive.v1` contract; the demo contract notes the mapping so nothing is lost.

Alternative naming, if preferred for the demo UI: D1 Scope · D2 Sources · D3 Claims · D4 Tensions ·
D5 Synthesis · D6 HTML · D7 Verification · D8 Export — a 1:1 relabel of 2a with D6+D7 split; either is
fine as long as the shape is byte-identical run to run.

## 3. Contract essentials (what makes it a lock)

- **Trigger:** `SOLAR_DEMO_REPORT_MODE=1` OR explicit DeepDive markers OR
  `requirement_compiler = RESEARCH` → **bypass** `should_epic_decompose_request` and PM epic
  decomposition entirely; instantiate the contract graph with a `dag_variant` guard.
- **Capsules:** research/audit capsules only. `cap.requirement-research-scout`
  (`output_present source_manifest`), `cap.requirement-research-synthesizer`
  (`output_present synthesis_md`), `cap.requirement-compiler-audit` (handoff-only proof). The
  implementation capsule and `patch_diff`/`patch_within_scope`/`resource_binding.workspace_root`
  obligations are **forbidden by contract** on every stage.
- **Quality gates:** claims and verification stages use the native deterministic
  `research eval-artifacts` gate (citation grounding, unsupported-claim rate) — **the gate produces
  its own `research_eval_json` input by construction**, eliminating the v5 mechanical-FAIL class.
  LLM eval remains only on the report stage, with `on_capacity_unavailable: wait` and
  `on_human_review: warn_and_continue` (bounded mode), so a busy singleton evaluator can never
  dependency-kill the report chain again.
- **Artifact roots:** canonical `workspace/rsi-deep-research-report/`, sprint-workdir alias, publish
  step copies to `evidence/report/…` — the v9 divergence becomes a normalization step instead of a
  failure.
- **Provider policy:** codex-only / OpenAI-only with per-stage-execution route records; capsule
  choice governs the proof contract, the physical operator pin governs the provider (the synthesizer
  capsule's Claude `preferred` list is irrelevant under the pin).
- **Source mode:** offline seed pack `demo-rsi/source-pack/` (9 real sources), FSM `SEARCH_SKIP` path —
  deterministic and network-free for the demo.
- **Artifact adapter:** maps native engine jsonl (`sources/evidence/claims/sections/final.md`) → the
  five demo artifacts, so `validate_rsi_demo_report.py` and the wrapper stay unchanged.

## 4. Why this avoids generic PM/software-epic decomposition (point by point)

| v-run failure | Generic-path cause | Under the lock |
|---|---|---|
| v1 builder stall | logical-op NAME sent as task_type | task_type is a contract literal, compile-checked against the capsule |
| v2/v10 needs_human_review cascade | single evaluator contention escalates to a dependency-blocking status | claims gate is deterministic (`eval-artifacts`); report gate waits on busy capacity; human-review is warn-and-continue in bounded mode |
| v3 admission flip | planner re-picked the capsule per run | capsules fixed per stage in the contract |
| v5/v6 sticky flip | quality gate demanded an input the bypassed evaluator never made | gate produces its own input; gate decisions are ledger records, not clobberable statuses |
| v7 patch_diff on a report node | static capsule default for ImplementationWorker | implementation capsule forbidden; artifact stages carry output_present proofs only |
| v8 mid-draft validation race | wrapper guessed "file present = file done" | wrapper reads per-stage terminal states from the contract (fd83ee51 stays as defense in depth) |
| v9 workspace/workdir divergence | planner-invented write_scope prefix | artifact_roots contractual + publish step (1240285a stays as defense in depth) |
| S01 epic wedge | research prompt → 5-child software epic | trigger bypasses epic decomposition entirely |

## 5. Implementation order (owner-gated, from the committed design)

(i) trigger/short-circuit in intake → (ii) contract→task-graph instantiator (port
`build_deepdive_evidence_dag` or compile from the contract JSON) → (iii) artifact adapter →
(iv) dashboard fixed-pipeline strip. Each behind `SOLAR_DEMO_REPORT_MODE`, with the 11 deterministic
tests from `rsi-demo-stage-contract.json` green **before** any live run
(schema-valid; dag_variant guard; no implementation capsule / no patch_diff; byte-identical DAG twice;
trigger matches RSI prompt and rejects generic words; every task_type capsule-admitted; adapter
produces 5 artifacts and validator passes; eval-artifacts good/bad fixtures; obligations resolve to
output_present; artifact-root/timing/proof regression suites; route-proof OpenAI-only unchanged).

**Known blockers to clear before the engine fronts a real demo (from the corpus, do not skip):**
- F-055: `lib/research/cli.py` synthesizer emits hardcoded boilerplate as the report body — must be
  fixed or the D5/D7 stage must use the builder-authored path with the eval-artifacts gate.
- Evaluator capacity: one OpenAI evaluator serializes gates; the compressed shape reduces passes, and
  a second OpenAI evaluator (registry change, owner-gated) removes the class.
- Full R1→R5-equivalent self-completion has never been proven live (v5 died before R5; sticky fix
  `8f05dfb7` is deterministic-verified only). The lock's first live run is that proof, at ladder P3.
