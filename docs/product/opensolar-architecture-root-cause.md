# OpenSolar / AI4Research — Architecture Root-Cause Report

**Date:** 2026-07-06. Grounded in `opensolar-failure-corpus.md` (59 failure records, F-xxx) and
`opensolar-failure-taxonomy.json` (28 classes). Claims below cite corpus records; inference is marked.

## The one-paragraph diagnosis

OpenSolar does not have one workflow. It has **five semi-independent authorities** that each decide part of
"what should run and what counts as done": (1) intake/epic decomposition decides the task's *shape*;
(2) the LLM planner decides node identities, capsule bindings, task_types, and write_scope paths *per run*;
(3) capability capsules decide admission and proof obligations from *static defaults*; (4) the
evaluator/repair machinery decides gate semantics with its *own* status writes; (5) the wrapper/dashboard
decide expectations (artifacts, roots, terminal states) from *heuristics*. Nothing binds these five
together, so every live run is a fresh negotiation between them — and every negotiation that goes a new
way exposes a new seam. That is why the bugs "feel never-ending": they are not one bug, they are the
combinatorial surface of an uncontracted pipeline being sampled one run at a time.

## Q1 — Why does every run expose a new bug?

Because the planner re-rolls the contract every run and the rest of the system was built assuming a stable one.

Direct evidence of the mechanism, not just the pattern:

- v2 → v3: the *same* prompt resolved S1 to the implementation capsule in v2 and the audit capsule in v3.
  The v1 fix (`a3d39ca2`) was correct for v2's shape and wrong for v3's. The diagnosis says it outright:
  "**Why v2 passed and v3 failed: planner non-determinism … v2 succeeded by luck**" (F-046).
- v8 → v9: the same prompt emitted `workspace/rsi-deep-research-report/...` in v8 and a relative
  `rsi-deep-research-report/...` in v9, so v9's perfectly valid artifacts "went missing" (F-051).
- v4 → v7: R1–R5 one run, S1–S4 the next; the proof-contract bug only exists in the shapes where the
  static capsule default wins (F-049, F-053).

When the DAG shape, capsule binding, task_type, and artifact paths are all sampled per run, a fix
verified on run N is only a fix for run N's sample. The fix chain (F-044…F-051: eight fixes in ~24
hours, each live-verified against the *previous* failure and then bypassed by a *new* shape) is the
signature of patching samples instead of the distribution. Meanwhile the **content was fine** — v8/v9
produced valid 5/5 artifacts and the validator passed on the final files. The product never had a
content problem in this period; it had an orchestration-substrate problem.

## Q2 — Why did Sihao's original harness work better for him?

Three reasons, all evidenced:

1. **He had the workflow contract we lost.** The original `lisihao/Solar` ships
   `deepdive_requirement_compiler.py`: an explicit trigger (`is_explicit_deepdive_request`), a fixed
   D1–D9 DAG builder (`build_deepdive_evidence_dag`), a `dag_variant=deepdive_research` guard, and an
   `OPERATOR_MAPPING` that literally says "never returns standard/research PM DAG." OpenSolar packaging
   kept the downstream research engine but **dropped the router** (F-054). Research requests therefore
   fall through to generic PM/epic decomposition — the source of F-CLASS-01/02/03.
2. **He was the missing runtime supervisor.** The rc3-era system "worked" with hidden Claude panes,
   manual restarts, and a human watching: "pane state instead of operator lease state … manual restarts
   instead of deterministic env propagation … human observation instead of structured route proof"
   (arch gap audit, "Why Codex mostly worked before"). Productizing removed the human, and every
   function the human had been silently performing (capacity, cleanup, generation fencing, route truth)
   surfaced as a "new" bug.
3. **He ran one provider on one machine.** Codex-only, clean-user, packaged-artifact, and WSL/macOS
   paths simply did not exist as constraints for the original. Most Phase B/C classes (aliases, auth,
   contamination, fail-closed routing) are constraints the original never had to satisfy.

So "his worked better" is mostly survivorship: the original had a narrower contract surface *and* a
human filling the gaps — plus, for research specifically, an actual fixed pipeline we deleted.

## Q3 — Why is generic PM decomposition wrong for deep research?

Because it imposes a software-engineering lifecycle on an evidence-production task, and every stage of
that lifecycle then applies software proofs to non-software work:

- The live web-research demo decomposed a citation-heavy research request into
  `S01_requirements → S02_architecture → S03_core_runtime → S04_orchestration_ui →
  S05_verification_release` and wedged at S01 for the entire run (F-037). "Architecture" and
  "core-runtime" are meaningless stages for a report; they exist only because the epic template is
  a software template.
- The PRD gate then blocks on a *software PRD schema* (7 of 11 sections missing — a true negative
  against the wrong contract, F-040).
- When a single-sprint bypass avoids the epic, the LLM planner still invents software-shaped nodes:
  `ImplementationWorker` logical operators and implementation capsules with `patch_diff` obligations
  for nodes that write `sources.json` (F-044, F-049).
- The research lane's correct machinery — research capsules with `output_present source_manifest`
  proofs and the deterministic `research eval-artifacts` quality gate — already exists in-repo and was
  simply never on the path (F-054; `rsi-deepdive-vs-original-solar.md` §2 traces every v5–v10 failure
  to the generic path and shows the DeepDive pipeline would not have hit it).

Deep research needs *evidence gates* (source count, claim grounding, contradiction scan, citation
accuracy), not *code gates* (patch diff, write-scope, PRD). Generic PM gives it code gates.

## Q4 — Why are operator contracts brittle?

Because "which task_type / capsule / operator runs this node" has **no single owner**. The corpus shows
four different authorities being consulted at four different failure sites of the same class
(F-CLASS-04): a freeform label (`analysis`, F-019), an alias (`tests`, F-030), the logical-operator
*name* (`implementationworker`, F-044), and a stale logical-op→type map that ignored the resolved
capsule (F-046). Each fix moved the authority one step closer to the resolved capsule, and `34d5c921`
finally made the resolved capsule authoritative — **but only for the builder-pool dispatch path in
bounded mode's vicinity**. The same divided-authority pattern exists elsewhere:

- Registry vs reality: operators marked enabled/available with dead CLIs, wrong provider labels
  (`codex-gpt55` tagged `anthropic`), deprecated-but-dispatchable (F-005, G7/G8).
- Plan artifacts vs execution: `selected_operator_id=mini-claude-sonnet-builder` recorded while
  execution was OpenAI (F-031) — the plan is a *suggestion* pretending to be a *route*.
- Two dispatch paths (PM/pane vs graph/pool) with different envelopes; the graph path got
  `work_dir`/`graph_path` fixed and the PM path lagged (arch audit P0-3).
- Admission rejection had no failure mode: `operator_pool_submit_failed` silently fell back to a busy
  tmux pane and the node sat `assigned` forever (F-044) — a contract violation degraded into a hang.

Brittleness is the direct consequence: any component may assert an operator/task_type fact, no
component is obliged to check it against the others, and violations degrade silently.

## Q5 — Why are proof obligations mismatched?

Because obligations are attached to the **capsule static default**, while what a node must prove is a
function of **what the stage produces**. The chooser (`DEFAULT_CAPSULE_BY_LOGICAL_OPERATOR`) maps
role-identity → capsule; the capsule carries a fixed proof contract; nobody checks the contract against
the node's declared outputs:

- A node whose `write_scope` is `["…/sources.json", "…/evaluation-checklist.md"]` — zero code targets —
  carried `output_present patch_diff` + `check.patch_within_scope` (F-049). Unsatisfiable by
  construction; the runtime even wrote the confession sidecar
  (`patch_diff_not_emitted_no_write_scope_targets`) and then failed the node for it.
- The mirror image: code nodes that *should* prove a patch had no reliable patch sidecar pipeline —
  three separate fixes (discovery `ff35c302`, synthesis `a8203924`, obligation-shape `92c5615d`)
  were needed to make one true obligation satisfiable (F-024).
- The research quality gate demanded `research_eval_json` on a path where the evaluator had been
  deliberately bypassed — a proof input the flow could never have produced — and its mechanical FAIL
  was indistinguishable from a content FAIL (F-048).

The rule that was never enforced anywhere: **a stage's proof obligations must be satisfiable by the
stage's declared outputs and gate inputs.** That is a compile-time check, and it did not exist.

## Q6 — Why are wrapper failures recurring?

Because the wrapper has to *guess* the runtime's intentions. It guessed parent-epic status was enough
(paperfilter, F-038 → `c8bda26e`); it guessed file presence meant file finished (v8's 18 ms TODO race,
F-050 → `fd83ee51`); it guessed artifacts live under `workspace/` (v9, F-051 → `1240285a`); it guessed
its tmux teardown covered the daemons (watchdog respawns coordinator — F-043, still open). Each guess
was reasonable and each was falsified by runtime behavior the wrapper had no way to know, because there
is no shared artifact that says "this run has stages X, producing artifacts Y at roots Z, terminal
states W, route policy P." The wrapper fixes are good engineering, but they are the observer converging
on the runtime by trial and error. Give both sides the same contract file and the whole category
collapses into "wrapper reads the contract."

## Q7 — Which bugs are symptoms of missing workflow contracts?

Sorting the 28 classes by relationship to the missing contract layer:

**Direct symptoms (a workflow contract removes the cause):**
F-CLASS-01 (planner nondeterminism), 02 (generic PM for research), 03 (epic over-decomposition),
04 (task_type admission — 4 fixes for 1 class), 05 (artifact node × patch proof), 07 (obligation vs
artifact type), 16 (artifact roots), and the expectation half of 14/15/17 (wrapper observation, timing,
route-proof capture) plus 23's projection half (dashboard renders guesses instead of a contract).

**Made worse by the missing contract, but real runtime engineering in their own right:**
F-CLASS-08 (evaluator capacity — a capacity model is needed regardless; the contract decides *which*
gate a stage uses), 09/10 (gate decisions stored as clobberable status — needs a ledger), 12/13
(repair/eval generations — largely fixed, must be schema-locked), 18 (route truth), 28 (supervision
timeouts/heartbeats).

**Not contract symptoms (separate tracks):**
F-CLASS-19/24 (registry hygiene, installer/packaging), 20 (auth), 21/22 (contamination/cleanup —
run-scoped process registry), 25/26 (content quality: synthesizer boilerplate, PRD quality, wording),
27 (live capacity operations).

That partition is the refactor plan: build the contract layer for the first group, schema-lock the
second, and explicitly *do not* entangle the third (see `no-touch-list.md`).

## The top 5 architectural causes (ranked)

1. **No workflow contract layer** — trigger → fixed stage list → capsule/task_type → outputs →
   proof obligations → gates → artifact roots → route policy is decided by five uncoordinated
   authorities per run. (Umbrella cause; ~60% of corpus records.)
2. **The DeepDive router was dropped in packaging** — the one workflow that *was* contracted upstream
   lost its front door, sending all research through the generic path (F-054).
3. **Gate/status decisions are mutable shared state, not an append-only ledger** — direct
   `node["status"]` writes bypassing rank guards, canonical eval files keyed only by node, policy
   decisions stored as clobberable statuses (F-021, F-048, F-CLASS-09/12/13).
4. **Dual execution paths with unequal contracts** — PM/pane vs graph/pool envelopes, lib/ vs tools/
   module copies, legacy planner pane racing the role pool, installed vs worktree harness
   (F-028, F-029, F-059, arch audit P0-3).
5. **Observation is heuristic, not contractual** — wrapper, dashboard, and route proof each
   reconstruct expectations independently and disagree with runtime truth (F-031, F-032, F-050,
   F-051, split-brain P0-4).

"Use a stronger model" is explicitly not on this list: the strongest available models produced valid
content throughout Phase E while the substrate failed around them. "Run E2E again" is also not on the
list: 25+ live runs are what *generated* this corpus; the next live run is justified only as the final
rung of the validation ladder after deterministic contract checks pass.
