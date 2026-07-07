# Baseline Capability Inventory — lisihao/Solar (`main` @ `a3a0ecaa`)

**Date:** 2026-07-06. Read-only inventory of Sihao's baseline snapshot in this repo, his
`upstream/codex/*` capability branches, and what the packaging line (`upstream/openJiuwen-Solar`)
already kept/dropped. Companion to the failure corpus. **Nothing in this document deletes anything —
"disable" means off in the shipped configuration; all code stays in the repo.**

## 0. The rule that decides every row

A dormant component is **harmless** only if the runtime cannot reach it without explicit opt-in.
It is a **live hazard** if it sits inside a reachable selection/fallback/classification path. The
corpus has three proofs: the selector picked the dead gemini operator (Run F, exit 1); a mislabeled
codex operator tagged `provider=anthropic` served builds (Run G); the idle pane path swallowed a
capsule admission failure into a permanent silent hang (RSI v1). Dormant + reachable ≠ free.

## 1. What the baseline says it is (its own README)

"An AI-native execution fabric for long-running, evidence-driven software work … natural language
as the control surface, requirements as compilable artifacts, AI products as schedulable physical
operators, and software delivery as evidence-gated DAG execution." Three layers: **Solar Core**
(CLAUDE.md/agents/skills/rules/hooks/core — the Claude/Codex-native kernel), **Solar Harness**
(requirement compiler, sprint control plane, TaskGraph runtime, operator fleet, evaluator,
benchmarks, experience memory), **Solar Knowledge** (docs/research/indices). Pipeline:
`intent → contract → PRD/plan → TaskGraph IR → operator binding → lease → dispatch → handoff →
eval → gate → memory → optimization`.

## 2. Scale and shape

- `harness/lib/` = **253 entries**; `harness/tools/` = **271 entries**, largely a *duplicated copy*
  of lib (F-059 at full scale — the dual-lineage drift risk is baseline-native, not something we introduced).
- 278 of his own sprint/epic dirs committed; `SPRINTS-HIGHLIGHTS.md` curates **46 passed sprints** —
  dominated by Solar-fixing-Solar (pane resilience, coordinator chains, pidfile, doctor, SIGHUP),
  plus May-2026 product epics (tech-hotspot radar, HF-paper insight flow, GitHub intelligence),
  one spot-checked `passed/completed`.
- ~100+ persona agents (`agents/`), ~40 skills (`skills/`), a TypeScript `core/` (agent-daemon,
  engine, evolver, hive, nerve/TVS, ontology, dashboards), `codex-bridge/`, `mempalace/` (memory MCP),
  `secretary/openclaw`, personal `web/` artifacts, `demos/`.

## 3. Capability map with disposition

Legend: **KEEP-ON** = enabled in shipped product (the spine) · **KEEP-DORMANT** = stays in repo,
unreachable without opt-in, no action needed · **DISABLE** = reachable hazard, off in shipped
config (code kept) · **DROPPED** = already absent from the packaged line (done by earlier packaging).

### 3a. Harness execution fabric (the product)

| Capability | Evidence of state | Disposition |
|---|---|---|
| Requirement compiler → PM → planner → TaskGraph (apo_plan_compiler, epic_decomposer, capability_capsules, graph_scheduler, graph_node_dispatcher) | Working; carried every green run; hardened by our ~20 fixes | **KEEP-ON** (spine) |
| Operator pool runtime (operator_runtime, operatord, pm_dispatch, multi_task_runner, codex_operator) | Working; the only path with clean green proofs | **KEEP-ON** (spine) |
| Legacy cockpit-pane dispatch/fallback path | Worked only with Sihao watching; product-mode failure amplifier (silent-hang class) | **DISABLE** in product mode (dev flag) |
| Claude CLI operators + sonnet evaluator | Green (Run H; June-28 lane); stale for rc8 runtime — needs the P2 Claude rung | **KEEP-ON** |
| Codex/OpenAI operators + evaluator | Green (`ab795810`, smoke `c42d1e2f`) | **KEEP-ON** |
| Evaluator/eval_runner + deterministic gates, evidence/event ledgers, node_runstate | Working; core of our fixes | **KEEP-ON** |
| Gemini adapters (gemini_adapter, gemini_enhanced_search, gemini deep-research integration, gemini operators) | Dead on this machine (exit 1, Run F); reachable via selector | **DISABLE** |
| Antigravity/thunderomlx local backends + operators | Endpoint unreachable off Sihao's Macs; reachable via multi-task command backend | **DISABLE** |
| Browser-agent fleet (chatgpt_browser_agent_task_operator, browser_job_runtime, browser_profile_control, chatgpt_report_operator, webwright bridge branches) | Sihao-machine browser profiles; never exercised here; reachable as operators | **DISABLE** (revisit for Resource Radar P6) |
| flashmlx perf-debugger + notebooklm capsules | flashmlx caused the s2a research misbind (F-056); notebooklm personal | **DISABLE** |
| understand-anything-* capsules (indexer/tour/chat/kg) | Reachable via goal classifier; unvalidated on product path | **DISABLE** for v1 (candidate contract later) |
| Personal ingests (apple_notes_ingest, chatgpt-conversation-ingest, cocoindex, agent_rules_books adapter) | Personal data paths | **DISABLE** |
| Evolution/self-optimization (evolution_engine, experience_runner, failure_miner, backlog_autoscaler, autoresearch_pane_optimizer) | Meta-optimization; unvalidated; some reachable from coordinator ticks | **DISABLE** for v1 (own track later) |
| ai_influence / tech-hotspot pipelines (ai_influence_status_page, youtube report, github_intelligence) | His May epics passed with him driving; product-unvalidated; `github_intelligence.evidence` import already broken in our tree | **DISABLE** (future Resource-Radar-style contracts) |
| `harness/tools/` duplicate copies of lib | Drift hazard (had to double-patch twice) | **KEEP** but dedupe spine modules (route tools→lib) |

### 3b. Research lane

| Capability | Evidence | Disposition |
|---|---|---|
| Research engine (`lib/research/`: state_machine FSM, cli, claim_compiler, evaluator, survey gates, eval-artifacts) | Survived packaging intact; deterministic gate is real; **synthesizer body is hardcoded boilerplate (F-055)** | **KEEP-ON** behind the DeepDive contract; fix or bypass synthesizer before demo |
| DeepDive router (deepdive_requirement_compiler, brief_expander, profiles) | **Never on main**; lives on `upstream/codex/*` branches with tests (`96b9e140`) | **RESTORE** as the research contract front door |
| Insight overlay D10–D18 (insight_gates, prediction_packet_builder, conference_signal_extractor, CAIS profile) | Side-branch capability, demo-scale unnecessary | **KEEP-DORMANT** (port later if insight products wanted) |

### 3c. Solar Core / kernel layer (Claude-Code overlay)

| Capability | Evidence | Disposition |
|---|---|---|
| Kernel + rules + hooks + core agents/skills used by the overlay | Productized separately via `kernel/`, `components.d/` in the packaged line | **KEEP-ON** (already component-gated) |
| ~100 persona agents, ~40 skills (a2a-hub, clawdwork, apple-calendar, email-to-calendar, banner…) | Personal breadth; unreachable unless invoked | **KEEP-DORMANT**; ship a curated subset list |
| TypeScript `core/` (agent-daemon, engine, evolver, hive, nerve/TVS, ontology, demo UIs) | Harness already runs without TVS ("no TVS dependency" per packaging note); evolver = self-modification | **KEEP-DORMANT**; evolver **DISABLE** if reachable |
| mempalace (memory MCP server) | Opt-in MCP; harmless dormant | **KEEP-DORMANT** |
| codex-bridge (CODEX-PROTOCOL, to/from-codex) | Superseded by codex operator path for runtime; may still serve the overlay | **KEEP-DORMANT** |

### 3d. Already dropped by earlier packaging (precedent: faithfulness was always partial)

`data/`, `insight-reports/`, `secretary/` (openclaw), `.solar/` state, `.clawhub`,
`install-core.sh`, `Macmini-2-Macbook.sh`, `CLAUDE.md.backup.*`, `package-lock.json`. The packaged
line **added**: `desktop/`, `components.d/`, `kernel/`, `bin/`, `distribution/`, `get-solar.sh`,
`install.ps1`, `requirements/`, `release-exclude.txt`, VERSION/INSTALL docs.

### 3e. Privacy flags for any public cut (not runtime issues)

Personal artifacts still tracked on baseline: `web/spring-travel-2026.html`, `web/huawei-*.html`,
`library/Article`, `demos/moltbook-digest.html`, his committed sprint history (Chinese personal
project names), persona files. Keep in private repo; scrub list for the public orphan cut.

## 3f. Deep capability map (added after full-lib sweep)

**Cockpit architecture (verified from `main:harness/solar-harness.sh`):**
- **"Product Delivery" session** — 2×2 grid: pane 0.0 `PM 产品经理`, 0.1 `Planner 规划者`, 0.2 `Builder 主建设者`, 0.3 `Evaluator 审判官`; persona-injected via `pane-launcher.sh`.
- **"Builder Lab" session — 4 parallel builder panes** (`Builder 1–4` / `lab-builder-1..4`), each with a `SOLAR_BUILDER_SLOT` and a **model matrix** (`SOLAR_LAB_BUILDER_MODEL_MATRIX`); matrix change triggers respawn of all four. This is the multi-builder parallel capability (the "4 builder panes").
- Background-window session for daemons; pane leases/doctor/hygiene/role-pools; `cmux-workspace-sample.yaml`.

**Deep-research stack (verified from `main:harness/lib/research/cli.py` — ~45 subcommands):**
- Core FSM run: `init → add-source → extract → ledger → mine → outline → write → check → compile → synthesize → export → eval-artifacts`.
- Search: `search` (Serper API + `serper-usage` meter), `handoff-search` (human-in-the-loop search Markdown), `import-search` (import human/Gemini/GPT results) — the human search gate is **by design**.
- Source governance: `policy-doctor`, `policy-explain` (source-authority scoring), `source-audit`.
- **Survey pipeline (professor-grade, the deepest research capability):** `survey-plan/pack/write-section/run-sections` (revision loops), `survey-watch-responses/-register/-tick` (periodic watcher), `survey-rewrite-queue/-run` (scorecard-driven rewrites), `survey-auto-repair` (strict-eval→rewrite→re-eval), `survey-finalize-run` (one-shot pipeline), `survey-enrich-papers` (recursive enrichment + trend clusters), `survey-continue/status-next-action`, `survey-chief-editor`. Deterministic gates: `argument_density`, `controversy_matrix`, `global_consistency_pass`, `source_quality_distribution`, `source_gap`, `golden_style_gate`, `style_contract`, `report_ast`.
- Plus the DeepDive router (side branches) and the D10–D18 insight overlay.

**Capability families across the 253 lib modules:**
- **Actor/operator plane (~25 modules):** actor lease/mailbox/profiles/registry/runtime; operator flow-control, model-selection, persona, router, runtime, schedule-binder, score, state-machine; logical-operator registry/router; unified selector; provider adapters; model registry + scenario routing.
- **Autopilot/intake:** autopilot + operator dispatcher, intent gateway/consumer/engine-adapter, task queue, dispatch scheduler, backlog autoscaler, concurrency policy.
- **Evidence/quality (~20):** eval_runner, evidence/event ledgers, verification_gate, verifier/, activation proofs, data-plane + write-path audits, architecture/workflow guards, failure fingerprint/handler/miner, **runtime_chaos_suite**, benchmarks (agent-arena, capability-fusion, heavy-proof, platform-workflow, certification suite).
- **Knowledge plane (~25):** knowledge ingest dispatcher/registry/health, semantic extract, qmd indexer/embed/proxy, spans, grounding hook, dashboard; 10 `wiki-*` modules (upload/extract/quality-gate/backlink-index/quarantine); obsidian indexer; **mineru** PDF extraction; cocoindex/ragflow/ruflo adapters; mirage internal search.
- **Skills-as-operators:** `skill_to_capsule_compiler`, skill-capsule bridge, skill operator registry, skill metrics/healthcheck/evolution — Claude-Code skills compiled into dispatchable capsules.
- **Meta/self-improvement:** evolution_engine, experience_runner, meta_harness_adapter, operator_score, skill_evolution_runner (the "AI optimizes AI" layer).
- **Product pipelines:** tech_hotspot_radar, ai_influence (status page/daily digest/github-trends/youtube report), hf_paper_insight (with S01–S05 closeout modules), github_intelligence, social_browser_backend_x, youtube modules.
- **Remote fleet:** remote_dispatch, remote_multi_task_monitor, `Macmini-2-Macbook.sh` — multi-Mac operation.
- **Oddities (product nonsense, fine for a personal repo):** ~15 one-off `*_closeout.py` sprint artifacts committed INTO lib/; `tools/` as a 271-entry near-duplicate of lib; committed personal sprint history and web artifacts; `operator-model-selections.json` self-described as not read at runtime.

## 4. Net effect on the shipped surface

The spine that stays ON is exactly the pipeline the README calls the product: intake → compile →
plan → dispatch → build → eval → gate → evidence, on Claude-CLI + Codex operators, plus the
dashboard and the (restored) research contract. Everything DISABLED is either provably dead off
Sihao's machines, personal-data-bound, self-modifying, or unvalidated-but-reachable. Nothing is
deleted; re-enabling any row later = flipping its component/registry gate **after** it passes the
validation ladder for its own contract.
