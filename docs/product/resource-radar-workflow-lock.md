# Resource Radar Workflow Lock

**Date:** 2026-07-06. Design (not built). Second workflow contract after the RSI DeepDive lock —
its job is to prove the contract layer *generalizes*, and to be the only sanctioned path to live web
research (the capability the 2026-06-30 live web demo tried and failed to reach through a software
epic — corpus F-037).

## 1. Product intent

A recurring "radar" scan of a resource landscape (e.g. "AI coding assistants 2026", "agent harnesses",
"LLM eval tooling") that produces a ranked, citation-grounded report from four evidence categories:
papers, media/coverage, companies/products, practitioner opinions. This is exactly the deliverable the
owner asked for on 2026-06-30 ("cite at least 8 source URLs, accessed_at timestamps in UTC, separate
official documentation from third-party analysis … Do not fabricate sources") — the prompt that the
generic path turned into `S01_requirements → S05_verification_release` and wedged.

## 2. Fixed stage list (deterministic; machine form in `workflow-contract-schema.example.json`)

```
R1 Scope          RadarScopeCapture        radar-scope.json
R2 Category Plan  RadarCategoryPlanner     category-plan.json   (must cover papers/media/companies/opinions)
R3 Papers         RadarPaperScout          papers.json     ┐
R4 Media          RadarMediaScout          media.json      │  parallel — all depend only on R2
R5 Companies      RadarCompanyScout        companies.json  │
R6 Opinions       RadarOpinionScout        opinions.json   ┘
R7 Ranking        RadarRankingSynthesizer  radar-report.md + ranking.json
R8 Export         RadarPublisher           radar-report.html + route-proof + validator gate
```

Same shape every run. R3–R6 are the fan-out; R7 is the only barrier; R8 publishes.

## 3. Contract essentials

- **Trigger:** explicit markers ("resource radar", "landscape scan", "资源雷达") or explicit
  `workflow_id`; never via epic decomposition.
- **Node kinds / capsules:** all stages are `artifact`/`analysis`/`publish` — research scout +
  synthesizer + audit capsules only; no implementation capsule, no patch obligations anywhere.
- **Evidence rules as validator, not prompt hope:** every collected entry must carry
  `url`, `accessed_at` (UTC), `category`, `official_vs_thirdparty`; ranking items must cite collected
  entries; the deterministic validator enforces "no fabricated sources" by checking every cited entry
  exists in R3–R6 output (and, at P6, that URLs were actually fetched — fetch log is a stage output).
- **Web gate is explicit:** `source_mode.network = gated` on `SOLAR_ALLOW_LIVE_WEB=1`. When the gate
  is closed, the workflow does not fake it: it runs from a seed pack, or R3–R6 produce a **blocker
  report** stating exactly which web step was unavailable — the honest-failure behavior the owner's
  2026-06-30 prompt explicitly requested.
- **Evaluator gates:** deterministic entry-validators on R3–R6 (no LLM eval → no singleton-evaluator
  contention on the fan-out); one LLM eval on R7 (ranking judgment is genuinely a content call) with
  `wait` on busy capacity; deterministic validator gate on R8.
- **Provider policy:** codex-only/OpenAI-only initially, per-stage-execution route records; the
  contract is provider-parametric so a Claude variant is a policy change, not a new workflow.
- **Timeouts:** every stage has a liveness budget with `ORCHESTRATION_WEDGE_NOT_PRODUCT_PROOF`
  classification — an S01-style silent wedge is structurally impossible to leave undiagnosed.

## 4. Why this workflow second (not first)

- It exercises the two contract features the RSI lock does not: **parallel fan-out stages** (R3–R6 —
  will stress operator capacity and the duplicate-dispatch guard `714eb781`) and the **gated live-web
  mode** (P6 of the validation ladder).
- It reuses the RSI lock's entire substrate (router, compiler, adapter, ledger) with zero new runtime
  concepts — a true generalization test: if writing this contract requires new engine code beyond a
  `validate_resource_radar.py`, the contract layer is not yet general and that's a finding.
- Its offline rung (seed pack) is fully deterministic, so it can climb the ladder P0→P3 without any
  network, then P6 turns on `SOLAR_ALLOW_LIVE_WEB` with the fetch-log requirement.

## 5. Failure classes this lock is designed against (from the corpus)

| Class | How the lock handles it |
|---|---|
| F-CLASS-02/03 (research → software epic) | trigger bypasses epic decomposition; stages are radar-semantic, not SDLC-semantic |
| F-CLASS-01 (per-run DAG reshuffle) | byte-identical instantiation |
| F-CLASS-08 (evaluator contention) | LLM eval on exactly one stage; fan-out gated deterministically |
| F-CLASS-16 (artifact roots) | canonical `workspace/resource-radar/` + publish rule |
| F-CLASS-17 (route proof missing on failure) | per-stage-execution route records |
| F-CLASS-25/26 (fabrication/boilerplate/wording) | citation-existence validator; blocker-report mode instead of fabricated sources |
| F-CLASS-28 (silent wedges) | per-stage liveness budgets with wedge classification |

## 6. Open prerequisites

- `scripts/validate_resource_radar.py` does not exist yet (new, deterministic, test-first).
- Live-web fetching mechanics under codex (`SOLAR_CODEX_EXTRA_FLAGS --search` per memory
  `runtime-equals-rc4-human-search-by-design`) must be preflight-checked at P6; the P6 rung is the
  *only* place this is exercised.
- Operator capacity for 4 parallel scouts: either accept serialized fan-out under current capacity
  (contract still valid — scheduler order is free) or add builders in the registry (owner-gated,
  separate registry-hygiene track).
