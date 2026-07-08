# OpenSolar (OpenJiuwen Solar) — System Test Plan & Report

> **How to use this document:** everything is pre-filled **except the Status / Found Defects columns in §5**, which are left blank for the test executor to fill in after running each bench. The exact command (or manual procedure) for every test is given inline. The deterministic CI-grade gates that already ran during plan preparation are recorded separately in §5.0 and do not need re-running unless the tree changes.

- **Target build:** `suraj-subrahmanyan/OpenSolar`, branch `pkg/migration` @ `cdc7e90`, `VERSION 1.0.0-rc.8`
- **Baseline:** Solar-Harness runtime and research product line — authored by Sihao (`lisihao`, upstream `lisihao/Solar`, mirrored in this repo's `main`)
- **Additions under test:** packaging, installer, distribution, desktop app, dashboard overhaul, runtime hardening — authored by Suraj (62 commits on `pkg/migration`)
- **Plan date:** 2026-07-08
- **Test environment (to be filled by executor):** ________________ (developer local machine; note OS, Python, presence of `sqlite3`/`tmux`/`bun`, Claude/Codex auth state, browser profiles)

---

## 1. System Feature List (L1 & L2 Hierarchy)

Spreadsheet-importable. `Source Status`: **Baseline (Sihao)** = shipped in upstream Solar · **Added by Suraj** = new in the packaging/migration line · combined tags where both apply.

| Level 1 Feature | Level 2 Feature | Specific Inputs / Formats Supported | Description | Source Status |
|---|---|---|---|---|
| Ingestion | Social Media — X/Twitter (feed path) | ~200-account allowlist (TSV: tier/category/handle); DuckDuckGo search → profile scrape → RSS fallback chain (no official X API) | AI Influence Daily digest, scheduled 3×/day; SQLite dedup/seen-state; raw Markdown into `~/Knowledge/_raw/` | Baseline (Sihao) |
| Ingestion | Social Media — X/Twitter (real-browser path) | X account pages via leased Playwright browser; DOM extraction → `PostRecord` | Social Browser Backend X: 10-step pipeline → SQLite `social_posts`, engagement metrics, 24h dedup window, hard-blocker gate before real browser leases | Baseline (Sihao) |
| Ingestion | Videos — YouTube | ~50-channel allowlist (YAML); channel RSS (no OAuth) + public `captionTracks`; browser-agent transcript fallback; local ASR (whisper) shipped but disabled by default | YouTube Influence Digest: transcripts → Markdown + SQLite; caps 30 videos/run, 3/channel, 72h lookback, 60k-char transcript | Baseline (Sihao) |
| Ingestion | Research Papers | HuggingFace Papers API (JSON) + arXiv API (Atom XML); arXiv IDs via regex; `arxiv.org/pdf/{id}` links | HF Paper Insight: paper snapshots, enrichment, taxonomy, R0–R5 resonance scoring, 7-day-TTL evidence packets, watch triggers | Baseline (Sihao) |
| Ingestion | Documents — PDF | PDF files (incl. arXiv PDFs from `source-manifest.jsonl`) | MinerU PDF→Markdown into an Obsidian vault with provenance frontmatter + audit JSON; idle-only worker, 2 GB cap, 3 rpm | Baseline (Sihao) |
| Ingestion | OSS / Code Trends | `github.com/trending`, `trendshift.io`, `star-history.com` HTML; optional GitHub API (`GITHUB_TOKEN`) | GitHub Trends digest → SQLite + digests. **Runner marked retired**, superseded by Tech Hotspot Radar | Baseline (Sihao) |
| Ingestion | Unified Radar | YouTube + X + GitHub combined (reuses legacy raw dirs) | Tech Hotspot Radar: unified scanner → SQLite + report IR → chapter jobs → synthesized report with evidence packs | Baseline (Sihao) |
| Research & Synthesis | DeepResearch evidence pipeline | Markdown via internal Mirage VFS connector (only shipped connector); SHA-256 content hashing | SQLite evidence graph (SourceDocument/EvidenceItem/Claim/CitationSpan/ReportAST), 20 CLI subcommands, 7-metric factuality gate, cited report compilation | Baseline (Sihao) |
| Research & Synthesis | YouTube deep-dive reports | Collected transcripts graded T0–T3 | State-machine run lifecycle (graded→grouped→planned→chaptered→synthesized→validated); rejects T3-only runs; e.g. `wwdc-2026-deep-dive.html` | Baseline (Sihao) |
| Research & Synthesis | Gemini Deep Research | Natural-language research request; Gemini web UI driven via Playwright | O1–O6 state-machine controller, machine-checkable completion evidence, success = done + report + ≥3 references; **real calls off by default** (`GEMINI_DR_REAL_CALLS=1`) | Baseline (Sihao) |
| Research & Synthesis | Browser agents | ChatGPT web, NotebookLM, technology-diagram painter, YouTube transcript UI | browser-use/Playwright wrappers over persisted logged-in Chrome profiles; ChatGPT used as "high model" reasoner for reports | Baseline (Sihao) |
| Research & Synthesis | Webwright browser operator | Task envelope JSON (`SOLAR_OPERATOR_ENVELOPE_JSON`) | Shared Playwright operator backbone: login recovery, profile leasing, DOM extraction; underpins all browser-agent ingestors | Baseline (Sihao) |
| Model Providers | Claude (Opus 4.8 / Sonnet) | Local Claude CLI subscription (`--model claude-opus-4-8` / `sonnet`); no API key on this path | Main-pane + lab models; Sonnet evaluator (Opus evaluators retired); `main_allowed=true` for both | Baseline (Sihao) — evaluator update by Suraj |
| Model Providers | Codex CLI (gpt-5.5-codex) | Local `codex` CLI session; read-only sandbox execs | Premium coding/architecture reasoner via chain-watcher bridge; tiered token budgets (S=4000/A=2000/B=none); fail-closed route selectors | Baseline (Sihao) — hardened by Suraj |
| Model Providers | Zhipu GLM (GLM-5.1, GLM-4.7) | Anthropic-compatible endpoint swap (`ZHIPU_MODEL`, env-based base-URL switch in `model-config.sh`); opt-out flag `~/.solar/secrets/no-zhipu.flag` | Lab-builder workhorse; default lab matrix `glm,glm,glm,deepseek` (3× GLM-5.1 + DeepSeek); `main_allowed=false` | Baseline (Sihao) |
| Model Providers | DeepSeek (V4 Pro) | `DEEPSEEK_API_KEY` or `~/.config/llm-keys/deepseek`; balance probe `api.deepseek.com/user/balance` | Low-cost cloud reasoner/fallback; lab-only; disabled by default in scenario routing | Baseline (Sihao) |
| Model Providers | Gemini (2.5 Pro / 2.5 Flash CLI; Antigravity 3.1-pro; Google API) | Gemini CLI (`--model gemini-2.5-pro/flash`); `gemini_antigravity` enabled; `GOOGLE_AI_API_KEY` path disabled by default | Lab-only alternates + the browser-driven Deep Research path | Baseline (Sihao) |
| Model Providers | ThunderOMLX local LLM (Qwen3.6-35b-a3b) | OpenAI-compatible local server `127.0.0.1:8002` (`LOCAL_LLM_*` env, `THUNDEROMLX_AUTH_TOKEN`); Mac-mini-hosted | Local knowledge/builder operators (`mini-thunderomlx-qwen36-*`), semantic extraction, cache prewarm/bench scripts | Baseline (Sihao) |
| Model Providers | Quota / balance probes | `quota-providers.sh` (DeepSeek balance, Zhipu, etc.), 300s TTL cache; `codex-budget.sh` circuit breaker | Real provider quota probes feeding operator admission (deprioritize missing-CLI/quota-exhausted operators) | Baseline (Sihao) — operator backend-health by Suraj |
| Model Providers | ⚠ Not present | — | **Kimi/Moonshot, MiniMax, Qwen-cloud (DashScope), OpenRouter are NOT in the model registry** — only via ThunderOMLX local Qwen. If promised, they are TBD/unsupported | — |
| Core Engine (Solar-Harness) | Coordinator / sprint state machine | Sprint `status.json`, `plan.md`, `handoff.md`, `eval.md`; pidfile; tmux panes | Poll-loop dispatcher: `drafting→active→planning→approved→reviewing→passed/failed`; pane routing PM/Planner/Monitor/Evaluator/Builder; stale-pidfile self-heal; watchdog with circuit breaker | Baseline (Sihao) — hardened by Suraj |
| Core Engine (Solar-Harness) | Gates & atomic verdict commands | `plan-verdict`, `handoff-submit`, `eval-verdict`, `verify-events` CLI | Atomic (tempfile+rename) status+history+event updates; 7-phase lifecycle with entry gates (plan needs Contract Done; ship needs eval PASS) | Baseline (Sihao) |
| Core Engine (Solar-Harness) | Event sourcing | JSON events (schema: ts/actor/event/severity) | Append-only `events.jsonl` per sprint, JSON-validated, lockdir-serialized, 30s stale-lock reclaim | Baseline (Sihao) |
| Core Engine (Solar-Harness) | Operator pool (logical→physical) | 16 logical operator types; `physical-operators.json` / `logical-operators.json` / `agent-actors.json` | Binding-indirected routing; atomic `fcntl` leases; runtime states idle/leased/running/cooldown/quota_exhausted/auth_expired/disabled; dead-lease recovery during selection; role-compatible selection | Baseline (Sihao) — hardened by Suraj |
| Core Engine (Solar-Harness) | Multi-task DAG runner | Task graphs (`task-graph.schema.json`), `multi-task-profiles.json` | Parallel tmux-backed DAG workers, dependency gating, quota backoff (900s), memory reserve (4 GB); self-advancing DAGs (auto eval+verdict+next); operator failure cooldown; structured-output validation on build dispatch | Baseline (Sihao) — extended by Suraj |
| Core Engine (Solar-Harness) | Pane orchestration & leases | Persona + workdir + pane id + dispatch_id | tmux pane launch (`claude`/`codex` runtime selectable); single-owner pane leases, TTL 600s, release requires matching dispatch_id | Baseline (Sihao) |
| Core Engine (Solar-Harness) | Codex operator bridge | `inbox/*.req.md` (YAML frontmatter) → `outbox/*.res.md` | chain-watcher daemon runs `codex exec -s read-only`; budget circuit breaker (`BUDGET_EXCEEDED`/`CIRCUIT_BREAKER_OPEN`); per-call ledger; provider routes fail closed; observable contract | Baseline (Sihao) — hardened by Suraj |
| Core Engine (Solar-Harness) | Capsules | 8-field capsule schema (goal/facts/changes/risks/questions/next/round/topology) | Structured handoff artifacts between recursion rounds; skill→capsule compiler; execution gate blocks on missing/invalid capsule | Baseline (Sihao) |
| Core Engine (Solar-Harness) | Evals & promotion gates | Eval packs (cmd + expect_exit + timeout); skill evals | Declarative gates before promotion; dispatch-evals through the operator pool; fenced repair-eval generations | Baseline (Sihao) — extended by Suraj |
| Core Engine (Solar-Harness) | TS actor-host runtime | Agent message protocol; 5-phase flow DAG (P1–P5, gates G1/G2) | `core/` orchestrator: buildGraph/executeGraph, pause/resume/reroute, debate + vote modes; TS coordinator **dual-write log-only** unless flag-enabled | Baseline (Sihao) |
| Dashboard / GUI | Status-server API | HTTP + SSE on loopback; `X-Solar-Token` / `?token=` | `/healthz`, sprints, event stream, per-sprint projection snapshot/delta, intake, gate-verdict endpoints; loopback auth token, auto-enforced beyond loopback | Baseline (Sihao) — security token & hardening by Suraj |
| Dashboard / GUI | React dashboard (WS1–WS6 overhaul) | Browser (Vite/React/TS bundle) | DAG plan view, narrative timeline (de-noise/de-dup/group), gate clarity cards, run-health strip, run-overview pipeline, SSE with poll fallback, session-switch stale-paint guards | Added by Suraj |
| Desktop App | Electron shell + runtime classifier | macOS dmg / Linux AppImage / Windows portable exe | Detects-or-spawns local runtime; classifier ladder (symlink-issue/bundled-sync/attach/WSL-state/not-installed/crashed/forwarding-broken) with one-click recovery; `app://` offline fallback | Added by Suraj |
| Desktop App | First-run bootstrap | Bundled `get-solar.sh` / `install.ps1` | Headless detached install, log tail + auto-advance; bundled-runtime version sync (refuses symlinked `~/.solar/harness`) | Added by Suraj |
| Desktop App | Autostart & diagnostics | launchd plist / systemd `--user` / per-user scheduled task | Login services per OS; telemetry-free redacted diagnostics bundle | Added by Suraj |
| Packaging & Distribution | Shell bootstrap (`get-solar.sh`) | `curl \| bash`; `SOLAR_REPO/CHANNEL/SRC` env overrides | Clones published channel, execs installer, 2-attempt retry, retains clone for `solar update`; bash-3.2-safe | Added by Suraj |
| Packaging & Distribution | POSIX installer + component system | 13 component manifests (`components.d/*/component.sh`); wizard or `--yes`; `--dry-run`, `--set`, `--components` | Orchestrated install to `~/.solar` + `~/.claude/solar`; dependency auto-add; receipts; doctor; residue-free uninstall; `--keep-data` contract | Added by Suraj |
| Packaging & Distribution | Windows installer (`install.ps1`) | PowerShell 5.1; WSL2 Ubuntu-24.04 | UAC self-elevation, RunOnce reboot-resume, systemd + mirrored-networking config, exit-code-checked `wsl.exe`; **experimental** | Added by Suraj |
| Packaging & Distribution | pipx / PyPI wrapper | `openjiuwen-solar` (Python ≥3.11) | Thin CLI: `install` fetches `get-solar.sh`; other subcommands delegate to `~/.solar/bin/solar`; native Windows refused in-code | Added by Suraj |
| Packaging & Distribution | Kernel overlay generator | `kernel/kernel.manifest` fragments + allowlists | Generates `~/.claude/solar/SOLAR.md` per selected components; single sentinel import block in `~/.claude/CLAUDE.md`, byte-preserving edits | Baseline (Sihao) — packaged by Suraj |
| Packaging & Distribution | Release gates & CI | `scripts/*.sh`; GitHub Actions | Privacy scans (repo + shipped payload), install-matrix smoke, installer contract, kernel-gen check, release-cut dry-run + gitleaks over history | Added by Suraj |
| Memory & Knowledge | MemPalace MCP server | Obsidian vault path (`--set VAULT_PATH`) | Semantic-memory MCP server in its own venv; registered as MCP `mempalace`; off by default | Baseline (Sihao) |
| Memory & Knowledge | Skills & agents packs | 38 skills, 135 agents; component-gated packs (md / office / obsidian / calendar darwin-only / browser cargo-gated) | Installable Claude Code skills/agents; kernel-gen includes only allowlisted, selected assets | Baseline (Sihao) — packaged by Suraj |

---

## 2. Test Strategy & Engineering Methodology

### The Developer's Approach (System & Integration Testing)

We test as the engineers who built the system, from both the **user point of view** (inputs/outputs: "I ask for a sprint, I get a gated, evaluated deliverable") and the **engineering point of view** (inner module contracts: lease atomicity, append-only event streams, idempotency markers).

- **Waterfall trace:** Requirement (sprint contracts, component manifests) → Design (schemas in `harness/schemas/`, ADRs) → Code → System Test. Every failed test maps back to an exact module (e.g. an install-matrix hook failure maps to one file in `hooks/`).
- **Module decomposition:** the system decomposes into Ingestion, Research & Synthesis, Model Providers, Core Engine, Dashboard, Desktop, Packaging, Memory — each with its own bench (49 `harness/test-*.sh` shell benches, Python suites under `harness/tests/` and `tests/`, JS suites under `desktop/`, and the `scripts/` release gates).
- **Test-bench execution:** each bench injects controlled inputs (fixture sprints, fake Claude CLI, sandbox `HOME=$(mktemp -d)`, mock browser backends) and asserts exact structural/exit-code expectations. The repo's own gates are the primary benches — run them, don't simulate them.
- **Edge-case & extreme stress testing:** end users won't run the installer on a host with no `sqlite3` CLI, restart the coordinator mid-dispatch, race two sprints on one pane, exhaust a provider's quota mid-DAG, or yank a WSL distro out from under the desktop app — we do. Environment-sensitivity defects (the software equivalent of "does the laptop still boot in a Montreal winter") are a first-class category here (see D-001).
- **Determinism boundary (critical to this product):** the harness deliberately splits **deterministic plumbing** (testable without model quota: preflight, dispatch artifacts, ledgers, gates — the GitHub CI surface) from **live behavior** (real Claude/Codex/GLM/DeepSeek calls, real browser sessions, real ingestion). Deterministic gates are pre-run in §5.0; the live half is the executor's manual matrix in §5.1.

---

## 3. Test Cases & Test Bench Specifications

For each module: the bench injects an input, checks output against specification, and logs a Defect on deviation. **Run commands are given per test in §5.1.**

### Module: Core Engine — Coordinator (L2: sprint state machine)
- **Test bench input:** fixture sprint `status.json` walked through `drafting→active→planning→approved→reviewing`; artifact files created/omitted per gate.
- **Expected output:** dispatch fires only on `last_state != current_state`; gates block when required artifact missing (planning⇒`plan.md`, reviewing⇒`handoff.md`); `handle_passed` idempotent via `.finalized` marker.
- **Extreme edge case:** stale/zombie pidfile (kill -9 the coordinator, restart); two sprints mutating state in the same poll tick; coordinator code edited while running (old code stays resident until restart — Bug #5 class).

### Module: Core Engine — Event sourcing (L2: events.jsonl)
- **Test bench input:** concurrent `session.sh append` writers + malformed JSON events.
- **Expected output:** append-only stream (never rewritten), invalid JSON rejected before append, writers serialized by lockdir, `ts`/`sid` auto-filled.
- **Extreme edge case:** stale lockdir older than 30s reclaimed, not deadlocked; writer killed mid-append leaves no torn line.

### Module: Core Engine — Operator pool & leases
- **Test bench input:** dispatch to a leased operator; operator process dies holding a lease.
- **Expected output:** busy lease → deferred (no double dispatch); dead lease recovered at next selection; release requires matching `dispatch_id`.
- **Extreme edge case:** all operators `quota_exhausted`/`cooldown` → dispatch queues/fails closed, never spins; `physical_operators.count` below requested workers.

### Module: Model Providers — routing, quota, fallback
- **Test bench input:** (a) `quota-providers.sh` probe per provider with key present / absent / invalid; (b) lab matrix `glm,glm,glm,deepseek` with one provider's CLI missing; (c) `no-zhipu.flag` set; (d) ThunderOMLX server down at 127.0.0.1:8002.
- **Expected output:** (a) probe emits structured JSON (`status: ok/warn`, cached 300s), no-key → `warn/no-key`, never a crash; (b) operator backend-health deprioritizes the missing-CLI operator and the DAG still completes on remaining providers; (c) builder falls back GLM→Sonnet per `persona-config.sh`; (d) local operators health-gated out, no dispatch to a dead endpoint.
- **Extreme edge case:** provider returns HTTP 200 with an error body (quota page); balance exactly 0; key expires mid-DAG (auth_expired state must be entered, node re-routed, not lost); **all** providers exhausted simultaneously → run parks in a recoverable, evidenced state.

### Module: Core Engine — Codex bridge budget
- **Test bench input:** req files exceeding `daily_call_limit` / `daily_token_limit`.
- **Expected output:** `BUDGET_EXCEEDED` / `CIRCUIT_BREAKER_OPEN`; per-call ledger append; half-written outbox (<10 bytes) cleaned on exit.
- **Extreme edge case:** `codex` CLI absent from PATH → route fails closed and observably (the exact class rc.8 hardening addressed).

### Module: Ingestion (L2: Research Papers via HF/arXiv)
- **Test bench input:** arXiv Atom XML with math-heavy abstract; HF paper JSON with missing/malformed repo assets; arXiv ID regex boundaries (4- vs 5-digit suffixes).
- **Expected output:** normalized PaperSnapshot/Canonical entities, deterministic SHA-256-based IDs, evidence packet only when gate criteria met.
- **Extreme edge case:** arXiv API timeout / empty Atom feed; withdrawn paper (`/abs/` 404); packet TTL expiry mid-run.

### Module: Ingestion (L2: Documents/PDF via MinerU)
- **Test bench input:** multi-column LaTeX-dense arXiv PDF.
- **Expected output:** Markdown into vault with provenance frontmatter + audit JSON mapping source→generated pages.
- **Extreme edge case:** corrupted PDF; scanned-image-only (zero-text) PDF; 2 GB memory cap hit mid-extraction — worker stops cleanly at idle priority, never wedges the host.

### Module: Ingestion (L2: Videos via YouTube)
- **Test bench input:** allowlisted channel with a >3h video carrying public captions; same video with captions disabled.
- **Expected output:** timestamped transcript Markdown within run caps (30/run, 3/channel, 60k chars); no-caption case degrades to browser capture or an honest metadata-only record — never fabricated text.
- **Extreme edge case:** geo-blocked/deleted video; RSS present but watch-page layout changed (selector break); ASR disabled + no captions + logged-out browser profile.

### Module: Ingestion (L2: X/Twitter both paths)
- **Test bench input:** Tier-1 account with fresh posts; account renamed/suspended; rate-limited scrape.
- **Expected output:** feed path walks DDG→scrape→RSS fallbacks in order and dedups via SQLite seen-state; browser path emits schema-valid `PostRecord`s and respects the 24h dedup window and hard-blocker gate.
- **Extreme edge case:** all three feed fallbacks fail for one account (must log-and-continue, not abort the whole digest); browser lease not released after a crash.

### Module: Research & Synthesis (L2: DeepResearch factuality gate)
- **Test bench input:** report AST with one deliberately uncited key claim and one citation span with off-by-one offsets.
- **Expected output:** gate fails naming the metric (`unsupported_claim_rate`, `citation_span_accuracy`); UTF-8 char+byte offset verification catches the off-by-one.
- **Extreme edge case:** source fetch error fails hard (silent degradation is forbidden by design); gate verdict consumable exactly once.

### Module: Research & Synthesis (L2: Gemini Deep Research)
- **Test bench input:** mock-mode request (default), then real run with `GEMINI_DR_REAL_CALLS=1` and a logged-in profile.
- **Expected output:** mock returns honest FAILED (never a fabricated report); O6 success only with terminal `done` + non-empty report + ≥3 valid http(s) references; append-only event log passes `verify_evidence`.
- **Extreme edge case:** logged-out Chrome profile; Gemini UI label change; browser killed at O4 → state machine lands in a recoverable, evidenced state.

### Module: Packaging (L2: installer + components)
- **Test bench input:** `smoke-install-matrix.sh minimal` and `check-installer-contract.sh` in sandbox `HOME`.
- **Expected output:** doctor `verdict==ok`; DB schema + FTS5 probe; kernel loadable (one import line, no dangling refs); every registered hook survives benign stdin; idempotent reinstall; residue-free uninstall; `--keep-data` keeps db/config/.env only; `--dry-run` writes zero files.
- **Extreme edge case:** host missing optional binaries (`bun`, `cargo`, **`sqlite3`**) must skip/degrade with actionable messages — this bench already surfaced **D-001**; paths with spaces; non-TTY without `--yes` fails loud.

### Module: Desktop (L2: runtime classifier)
- **Test bench input:** `SOLAR_SIMULATE` matrix over every classifier state (not-installed / crashed / WSL stopped / forwarding-broken / stale bundled runtime / symlinked runtime).
- **Expected output:** each state maps to its recovery screen; recovery IPC honored only from `data:`/control origins (privilege isolation from the runtime-served dashboard).
- **Extreme edge case:** WSL #9516 (localhost forwarding broken) → attach via WSL VM IP; version-mismatched bundled harness → sync; symlinked `~/.solar/harness` → refuse sync.

### Module: Dashboard (L2: status-server auth & streams)
- **Test bench input:** requests with/without `X-Solar-Token` on loopback vs non-loopback binds; SSE dropped mid-stream.
- **Expected output:** token enforced only when bound beyond loopback (auto); SSE reconnects with poll fallback; projection deltas consistent with snapshots; rapid session switching leaks no stale state.
- **Extreme edge case:** concurrent `/settings` writers; 210s shell-out endpoint timeout honored.

### Module: End-to-End (L2: full cockpit run — live)
- **Test bench input:** real `solar-harness start` with Claude auth; natural-language sprint request through intake; let coordinator drive plan→build→eval with the lab matrix (GLM/DeepSeek builders).
- **Expected output:** sprint reaches `passed` with all gate artifacts present (`plan.md`, `handoff.md`, `eval.md`, events.jsonl consistent per `verify-events`); dashboard reflects each transition live; deliverable lands in the deliverables rail.
- **Extreme edge case:** kill the coordinator mid-build and restart (must resume, not duplicate dispatch); revoke one provider's quota mid-run (self-advancing DAG must reroute or park recoverably).

---

## 4. Defect Categorization Framework

| Severity | Definition |
|---|---|
| **Blocker** | Cannot test the system at all — critical core crash or environment failure with no bypass |
| **Critical** | A major feature or distribution channel is completely broken; no workaround for the affected path |
| **Major** | Functionality impaired on a real class of hosts/paths; workaround exists |
| **Minor** | Cosmetic, drift, or dead-code issues; documented supersessions |

---

## 5. System Test Report & Evaluation

### 5.0 Pre-filled: deterministic CI-grade gates (already executed, 2026-07-08, Linux container)

These mirror the GitHub CI surface and were run during plan preparation. Re-run only if the tree changes.

| Gate | Command | Result |
|---|---|---|
| Repo hygiene | `git diff --check` | **PASS** |
| Privacy — repo | `bash scripts/check-privacy.sh` | **PASS** |
| Privacy — shipped payload | `bash scripts/check-installed-clean.sh` | **PASS** |
| Harness plumbing smoke | `bash scripts/check-harness-plumbing.sh` | **PASS** (doctor ok · preflight ok w/ fake Claude · missing-Claude refusal ok · auth/quota boundary ok · dispatch ledger ok · operator envelope plumbing ok) |
| Installer non-TTY contract | `bash scripts/check-installer-contract.sh` | **PASS** |
| Install matrix minimal | `bash scripts/smoke-install-matrix.sh minimal` | **FAIL** — 24 sub-checks pass, then hook crash rc=127 → **D-001** |

### 5.1 Detailed Test Results Table — **to be filled by the test executor**

| Feature ID | L1 Feature | L2 Feature | How to run | Status (Pass/Fail) | Found Defects / Fail Reason |
|---|---|---|---|---|---|
| FT-01 | Core Engine | Coordinator state machine + gates | `cd harness && bash test-coord-startup.sh && bash test-dispatch.sh && bash test-status-auto-advance.sh && bash test-plan-stuck.sh && bash test-passed-skip.sh` | | |
| FT-02 | Core Engine | Multi-sprint / race safety | `cd harness && bash test-multi-sprint-race.sh && bash test-save-state-race.sh && bash test-dispatch-overlap.sh` | | |
| FT-03 | Core Engine | Event sourcing | `cd harness && bash test-events-emit.sh && bash test-capsule-ledger.sh` | | |
| FT-04 | Core Engine | Operator pool / leases / routing | `cd harness && bash test-coordinator-routing.sh && bash test-role-dispatch-fallback.sh && bash test-lab-routing.sh && bash test-pidfile-lifecycle.sh` | | |
| FT-05 | Core Engine | Multi-task DAG runner (deterministic) | `cd harness && bash test-mixture-topology.sh && bash test-parallel-integrate.sh`; Python: `python3 -m pytest tests/graph/ -x` | | |
| FT-06 | Core Engine | Codex bridge + budget | `cd harness && bash test-codex-bridge.sh && bash test-chain-watcher-contract-regression.sh && bash test-chain-watcher-notify.sh` | | |
| FT-07 | Core Engine | Resilience / self-heal | `cd harness && bash test-harness-resilience.sh && bash test-heal-never-runs.sh && bash test-deadhead.sh && bash test-degrade-real.sh` | | |
| FT-08 | Model Providers | Quota probes (Claude/Codex/GLM/DeepSeek/Gemini/ThunderOMLX) | `bash harness/quota-providers.sh` with each key present/absent; inspect JSON per provider; `bash harness/codex-budget.sh status` | | |
| FT-09 | Model Providers | GLM lab builders (live) | Start harness with lab matrix `glm,glm,glm,deepseek` (see `harness/model-config.sh`, requires Zhipu access); dispatch a builder node; verify completion + attribution in dispatch ledger | | |
| FT-10 | Model Providers | DeepSeek reasoner (live) | Set `DEEPSEEK_API_KEY`; enable provider in `harness/config/model-scenario-routing.json`; dispatch a lab node; verify balance probe + completion | | |
| FT-11 | Model Providers | Gemini CLI + Antigravity (live) | Dispatch to `gemini-2.5-pro`/`flash` lab operator; verify route + output | | |
| FT-12 | Model Providers | ThunderOMLX local Qwen3.6 (live, Mac mini) | Start server on 127.0.0.1:8002 (`harness/scripts/thunderomlx_start_8002.sh`); run `mini-thunderomlx-qwen36-knowledge` operator; kill server mid-run to verify health-gating | | |
| FT-13 | Model Providers | Provider fallback / fail-closed | Remove one provider CLI from PATH mid-matrix; verify backend-health deprioritization + DAG completion on remaining providers; set `no-zhipu.flag` → GLM→Sonnet fallback | | |
| FT-14 | Ingestion | X/Twitter feed path (live) | `python3 harness/scripts/ai_influence_daily.py run` (network needed); verify Markdown in `~/Knowledge/_raw/ai-influence-daily-digest/` + SQLite dedup on second run | | |
| FT-15 | Ingestion | X/Twitter real-browser path (live) | Run social_browser_backend_x pipeline with a leased logged-in profile; mock backend first: `python3 -m pytest harness/tests/ -k social -x` | | |
| FT-16 | Ingestion | YouTube transcripts (live) | `python3 harness/scripts/youtube_influence_digest.py` (allowlisted channels); verify transcript caps + no-caption honest degradation | | |
| FT-17 | Ingestion | HF Papers / arXiv (live) | Run HF Paper Insight collector (`harness/lib/hf_paper_insight/collector.py` daily path); verify snapshots, R-scores, evidence packets | | |
| FT-18 | Ingestion | MinerU PDF→Markdown (live) | `python3 harness/lib/mineru_extract.py extract <arxiv.pdf>` (needs `vendor/mineru/.venv`); test corrupted + scanned-only PDFs | | |
| FT-19 | Ingestion | Tech Hotspot Radar (live) | `python3 harness/scripts/tech_hotspot_radar.py doctor && ... status`; then a seeded run; verify SQLite + report IR | | |
| FT-20 | Research & Synthesis | DeepResearch pipeline + factuality gate | `python3 -m pytest tests/research/ harness/lib/research/ -x`; then a CLI run: `init → add-source → extract → mine → outline → write → check → compile` | | |
| FT-21 | Research & Synthesis | Gemini Deep Research | Mock: `python3 -m pytest tests/gemini_deep_research/ -x`; Live: `GEMINI_DR_REAL_CALLS=1` + logged-in profile, one real question, verify O6 evidence | | |
| FT-22 | Research & Synthesis | YouTube deep-dive report (live) | Run the ai_influence_report flow over collected transcripts; verify T3-only rejection + validated sourced report | | |
| FT-23 | Research & Synthesis | Browser agents (ChatGPT/NotebookLM/diagram) | Run each `harness/scripts/browser_agent_*_wrapper.py` with a logged-in profile; verify honest failure when logged out | | |
| FT-24 | Dashboard | Status-server API + auth + SSE | `bash scripts/smoke-status-server-e2e.sh`; manual: curl `/healthz`, token on/off loopback, kill SSE mid-stream → poll fallback | | |
| FT-25 | Dashboard | React overhaul (visual + narrative contract) | `bash scripts/verify-webapp-session.sh` (includes visual desktop+mobile gates); live run against a real sprint | | |
| FT-26 | Desktop | Classifier + bootstrap + contract | `cd desktop && npm test` (or `bash autotest.sh`; xvfb on Linux); `SOLAR_SIMULATE` states matrix | | |
| FT-27 | Desktop | macOS package + first-run (manual) | Build dmg (`npm run build:mac`), `bash verify-macos-package.sh`; first-run install flow on real Mac | | |
| FT-28 | Desktop | Windows/WSL2 e2e (manual, experimental) | Real Windows 11: portable exe → `install.ps1` → reboot-resume → dashboard reachable; `powershell scripts/windows-evidence-doctor.ps1` | | |
| FT-29 | Packaging | Install matrix full | `bash scripts/smoke-install-matrix.sh full-non-rust` (after D-001 fix, re-run `minimal` too) | | |
| FT-30 | Packaging | Interactive wizard (PTY) | `python3 scripts/smoke-installer-wizard-pty.py` | | |
| FT-31 | Packaging | Update / repair / uninstall lifecycle | `bash scripts/check-update.sh`; sandbox: `solar repair`, `solar uninstall --keep-data` → verify keep-data contract | | |
| FT-32 | Packaging | pipx wrapper e2e | `bash distribution/pipx/smoke.sh` (sandbox HOME, file:// clone) — **will exercise D-002 pins** | | |
| FT-33 | Packaging | Daemons render + lifecycle | `bash scripts/check-daemons-render.sh && bash scripts/check-daemons-lifecycle.sh`; real launchd/systemd start is manual | | |
| FT-34 | Packaging | Release cut dry-run + gitleaks | `bash scripts/release-cut.sh --source HEAD` (dry-run default; owner-only for `--execute`) | | |
| FT-35 | Memory & Knowledge | MemPalace install + MCP registration | Install with `--components mempalace --set VAULT_PATH=...`; verify venv, config render (no `{{`), MCP registered, removed on uninstall | | |
| FT-36 | Core Engine (live) | Full cockpit e2e (Claude auth required) | `solar-harness start` → intake a real request → drive to `passed`; kill/restart coordinator mid-build; `solar-harness verify-events <sid>` | | |
| FT-37 | Core Engine | Symphony scheduler | `cd harness && bash test-symphony-scheduler-dry-run.sh && bash test-symphony-workspace.sh && bash test-symphony-hooks.sh && bash test-symphony-d6-guard.sh` | | |
| FT-38 | Core Engine | Telemetry / data plane | `cd harness && bash test-telemetry.sh && bash test-telemetry-real-data.sh && bash test-data-plane-db-concurrency.sh` | | |

### 5.2 Defect Log (found during plan preparation — static analysis + deterministic gates; executor appends below)

| ID | Severity | Module | Description | Reproduction / Evidence |
|---|---|---|---|---|
| **D-001** | **Major** | Packaging → hooks | `hooks/sma-session-start-preload.sh` crashes rc=127 when the **`sqlite3` CLI binary** is absent: `set -euo pipefail` + unguarded `INTEGRITY=$(sqlite3 …)` (stderr suppressed, but 127 kills the script). Fails the install-matrix "no-crash on benign stdin" gate on minimal hosts. Fix: `command -v sqlite3` guard (exit 0 with WARNING, matching missing-DB behavior) and/or add sqlite3 to dependency bootstrap. | Reproduced in sandbox HOME with DB present, no sqlite3 CLI → `exit=127`. §5.0 install-matrix log. |
| **D-002** | **Critical** (pipx channel) | Distribution → pipx | `distribution/pipx/opensolar_cli/cli.py:17` + `pyproject.toml` URLs point at **`Stellven/OpenSolar@v1.0.0-rc.3`** — wrong org, stale tag — while README says `suraj-subrahmanyan@v1.0.0-rc.6` and tree is rc.8. Published `openjiuwen-solar` would fetch `get-solar.sh` from the wrong origin. Other channels unaffected. | `grep -rn Stellven distribution/pipx/` — 5 hits. |
| **D-003** | Minor | Distribution → bootstrap | `get-solar.sh:20` default channel `v1.0.0-rc.6` vs `VERSION 1.0.0-rc.8`. Deliberate published-tag fallback, but needs a release-checklist item so the pin advances per cut. | `get-solar.sh:20`. |
| **D-004** | Minor | Ingestion | `harness/x_api` and `harness/manual_curated` are 0-byte tracked stub files — dead placeholders that mislead feature inventories. | `git ls-files` + size. |
| **D-005** | Minor | Ingestion | GitHub Trends runner retired (superseded by Tech Hotspot Radar) but `com.solar.github-trends-digest.plist` still ships → schedules a daily no-op at 07:37. | `harness/scripts/run_github_trends_digest.sh`. |
| **D-006** | Minor | Core Engine | Deprecated `harness/codex-bridge.sh` (hard `exit 0`) still ships alongside replacement `chain-watcher.sh`; harmless but confusing surface. | File header. |
| D-0__ | | | *(executor adds new defects here)* | |

### 5.3 Artifact Quality Assessment

Beyond raw pass/fail, we assess the artifacts the system produces (research reports, evidence graphs, sprint deliverables) on **Feasibility** and **Novelty**, using the system's *own quantitative gate criteria* rather than descriptions:

- **Feasibility — quantitatively enforced by design.** DeepResearch ships a 7-metric factuality gate (`unsupported_claim_rate`, `citation_span_accuracy`, `source_authority`, `freshness`, `contradiction_coverage`, `section_repetition`, `cross_section_consistency`) with character-and-byte-level citation-span verification; Gemini DR requires machine-checkable completion evidence (≥3 valid references) and refuses to fabricate in mock mode; the YouTube report line rejects T3-only runs. Executor: score live artifacts against these metrics and record the numbers, not impressions.
- **Novelty — moderate-to-strong at the system level.** Individual ingestors are conventional (RSS, scraping, caption extraction). The novel engineering is the composition: evidence-packet gating before high-reasoning spend, R0–R5 resonance triage, logical→physical operator indirection with leases and quota-aware admission, and the deterministic-vs-live test boundary. The rc.8 additions (self-advancing DAGs, fail-closed provider routes, honest-gate dashboard) materially raise process health.
- **Process health.** Event streams are append-only and schema-validated; verdicts are atomic; idempotency markers (`.finalized`, lease `dispatch_id`) exist at every re-entry point.

### 5.4 Current Limitations (What it doesn't do yet)

- **Ingestion is allowlist-only:** ~200 fixed X accounts, ~50 fixed YouTube channels; arbitrary handles/links not accepted. Research-paper ingestion is HF-Papers/arXiv metadata only — PubMed, IEEE, Springer etc. unsupported; full-text ingestion is PDF-via-MinerU only.
- **No official X API** — feed path is DDG/scrape/RSS and inherently fragile; the robust path needs a leased, logged-in real browser.
- **Model providers:** GLM/DeepSeek/Gemini/ThunderOMLX are **lab-only** (`main_allowed=false`); main pane is Claude-only. **Kimi/Moonshot, MiniMax, cloud Qwen, OpenRouter are not integrated.** DeepSeek and the Google API path ship disabled by default.
- **Browser-agent dependence:** Gemini DR, ChatGPT reasoner, NotebookLM, no-caption YouTube capture all require persisted logged-in Chrome profiles and break on UI redesigns; several selectors assume Chinese-language UI labels.
- **ASR shipped but disabled** — no-caption videos degrade to metadata-only by default. ThunderOMLX assumes a Mac-mini host at 127.0.0.1:8002.
- **DeepResearch ships only the internal Mirage VFS connector** — web/academic connectors are architecture, not shipped code.
- **Scheduling is macOS-biased** (launchd plists); Linux gets systemd units for daemons but digest schedules are launchd-templated.
- **TS coordinator is log-only** (dual-write compare) unless flag-enabled; Bash remains the single authoritative engine.
- **Windows is WSL2-experimental**; native Windows refused by design. Four documented manual-only gates: interactive `claude` kernel load, real daemon starts, Windows WSL2 e2e, mempalace heavy deps.

---

## 6. Final Recommendation: Go / No-Go Decision

**Status: [ TBD — pending executor's §5.1 results ]**
**Provisional from deterministic gates alone: [ NO-GO ] for a public rc.8 cut until D-001 and D-002 are fixed; conditional GO for continued internal/developer use on macOS/Linux.**

**Justification (provisional):**

- **No Blockers found.** The deterministic core surface is healthy: doctor, preflight, dispatch/ledger/operator plumbing, installer contract, both privacy gates all pass (§5.0).
- **Why provisional NO-GO:** (1) **D-001** fails the project's own release gate on any host without the `sqlite3` CLI — the exact fresh-container class the installer targets; one-line guard fixes it. (2) **D-002** means the published pipx channel would install from the wrong GitHub org at a stale tag — a broken distribution channel is release-critical even though curl-bash and desktop channels are unaffected.
- **Decision rule for the executor:** after fixing D-001/D-002 and completing §5.1 — **GO** requires: install matrix green on mac+Linux, FT-36 full cockpit e2e reaching `passed` at least once with a kill/restart survival, at least one lab provider (FT-09/FT-10) completing a builder node live, and no new Critical+ defects. Anything less: NO-GO with the specific FT rows cited.
