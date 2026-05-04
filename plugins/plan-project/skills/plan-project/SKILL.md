---
name: plan-project
description: Use when an architecture document is settled and the build is large enough to parallelize, but before any code is written. Produces a dispatch-ready workplan — INDEX.md, phase-tagged task files, paired test tasks, deterministic runbooks, and an annotated reference exemplar — that an orchestrator session can fan out from. Slots between assess-project (design) and deliver-project (execution); composes with them rather than reimplementing.
---

# plan-project

This skill turns a frozen architecture into a workplan. It is **not** the architecture pass and **not** the execution pass — it is the layer between, where strategy becomes a graph the harness can dispatch from.

The skill produces artifacts. It does not run the workplan. Continuation across sessions is the harness's job; this skill leaves a clean handoff and exits.

## The lifecycle this slots into

```
assess-project   →   plan-project   →   deliver-project
  (design)            (workplan)          (execute)
```

- `assess-project` produces a design plan (architecture, requirements, risks).
- `plan-project` (this skill) decomposes that into a dispatch graph: phases, tasks, runbooks, paired tests, validator triggers.
- `deliver-project` consumes the workplan and runs parallel teams.

If sibling skills with those names exist in the same plugin namespace or workspace, **compose with them at phase boundaries** — call `assess-project` if architecture is incomplete; call `deliver-project` to execute a phase. Don't duplicate their logic. If they don't exist, leave seams as comments (`# TODO: invoke assess-project if available`) rather than guessing at their interfaces.

## When to use this skill

Use when **all three** are true:

- An architecture / design document exists and is reviewed (not draft).
- The build is large enough to parallelize — multi-phase, multi-component, multi-week.
- The user wants async / fully-automated execution where they're in the loop only for genuinely durable decisions.

## When NOT to use this skill

- Architecture is still in flux → use `assess-project` first. Don't plan on top of a moving foundation.
- Build is small enough for a single session → just do it. A workplan adds overhead that's only worth it past ~3–5 sessions of work.
- User wants to be in the loop on each step → workplans optimize for getting the user out of the loop. Wrong tool.

---

## Core principles

These are the non-negotiable invariants. Everything else in the skill serves them.

### 1. Closed-loop development

Any verification that **could** be done by a deterministic script **must** be done by a script, not a user check. Whisper transcription, mel-spectrogram comparison, energy-conservation invariants, snapshot diffs, schema validators — all runbooks. The skill's primary value is eliminating "hey user, can you verify this WAV / log / output?" round-trips.

If a runbook doesn't exist for a verification someone wants to do, the skill's response is to **author the runbook**, not to escalate to user. User checks are reserved for genuinely subjective calls (final A/B suites, multi-month research direction commits) — not "is this output gibberish."

### 2. Decision-point discipline

Every task is tagged with one of three `user_input` values:

- `none` — fully automated; user never enters the loop.
- `review` — user check adds value but does not block; task ships either way.
- `decision` — fires only on genuinely durable architectural choices that cannot be made mechanically (picking a final dimensionality from a sweep report, accepting/rejecting an external dependency, committing to a multi-month research branch).

`decision` tasks are surfaced separately in INDEX.md so the user can see at a glance what their actual synchronous obligations are.

**Per-phase budget, not a global ratio.** Target zero in-phase blocking decisions. Tolerate ~one durable decision per phase. The global ratio (≤ 5–10% across all tasks) is a smell-test heuristic surfaced by the workplan validator, not a hard gate — what matters is whether decisions block the critical path within a phase, not whether they're a small fraction of total tasks. Trigger a review when:

- any single phase has more than one blocking decision,
- decisions cluster on the critical path,
- or decision count exceeds the user's stated async availability.

When in doubt about a check: argue against your own instinct to ask the user. Most "user input" requirements are mechanizable with a runbook.

### 3. Roles are separated, code review splits

Three roles, with explicit boundaries:

- **Creator / validator** (the session that wrote the architecture) — owns **design coherence**, not code review. Triggered at phase boundaries to verify deliverables still match the design and to author refinement tasks if not. The "validator" name in this skill always refers to this architecture validator, never to a per-task code reviewer.
- **Orchestrator** — owns dispatch and **per-task code review** (lint, type-check, structural review of worker output). Mechanical, high-frequency. If `deliver-project` is the orchestrator, its existing two-stage review pipeline (spec compliance + code quality) fills this role; plan-project does not duplicate that prose.
- **Worker** — implements one task in a fresh session. Has no design context beyond what's in the task file.

The architect/validator and the orchestrator do **different** reviews. Don't collide them. Orchestrator-level review is mechanical and runs on every task. Validator-level review is architectural and runs once per phase.

### 4. Phase boundaries are validation triggers, not status flags

When a phase closes (per its entry/exit criteria), the **orchestrator automatically triggers the validator session** — not the user. The validator runs adversarial review against the phase's deliverables and either:

- signs off → next phase unlocks, or
- files refinement tasks → phase reopens with specific fixes.

The user enters the loop only if the validator surfaces a `decision` task during refinement.

### 5. Test tasks are first-class, paired with feature tasks

Every feature task has a paired test task, authored at the same time as the feature task. Test tasks are dispatched independently, often to a different worker. **Acceptance gate: a feature task cannot be marked done until its paired test task lands AND the test runs against the feature deliverable.**

This is a structural defense against "we'll test it later." Workers under pressure cut tests first when tests are folded into feature tasks; pairing them as siblings makes the cut visible.

The `pair_test` field in task frontmatter is **only enforcement if something checks it**. The workplan-validator runbook (below) is what makes it enforcement instead of decoration.

---

## Input/output contract

This skill is one node in a chain. Its inputs and outputs are typed; the chain breaks if either end is fuzzy.

### Input — what assess-project (or any design pass) hands in

A design document containing, at minimum:

- Executive summary with original user request preserved.
- Functional requirements with acceptance criteria.
- Non-functional requirements (performance, security, reliability targets).
- Architecture & detailed design with explicit component boundaries.
- Risk assessment with mitigation strategies.
- Identified information gaps, classified Critical / Important / Nice-to-have.

If any of these are missing, **stop and call `assess-project` (or its equivalent)** rather than planning on top of an incomplete design. Do not infer.

### Output — what this skill hands to deliver-project (or any execution pass)

`deliver-project` today expects a single design-plan-shaped document and decomposes it itself. This skill produces a richer artifact and must hand off in a shape `deliver-project` can read **without reinterpretation**. The adapter is concrete, not prose:

For each phase, the skill emits a **dispatch brief** at `dispatch/<phase-name>/brief.md` shaped to pass `deliver-project`'s Phase 1.0 design-plan validation. The required headings are non-negotiable — `deliver-project` checks for them — so the brief carries them all, with phase-scoped content nested inside, plus plan-project's task/runbook/validator additions:

```markdown
# <phase-name> dispatch brief

> Status: Ready for Implementation
> Scope: phase-scoped slice of the parent design plan at <path-to-architecture-doc>

## Executive Summary
### Original User Request
[Copy verbatim from the parent design plan. Same text in every phase brief.]
### Phase Overview
[One-paragraph definition-of-done for THIS phase, copied from INDEX.md phase entry criteria.]

## Functional Requirements
[Phase-scoped FRs from the parent design plan — only the requirements this phase delivers, with acceptance criteria. Copy from the parent; do not invent.]

## Non-Functional Requirements
[Phase-scoped NFRs — performance, security, reliability targets that bind THIS phase. Copy from the parent.]

## Architecture & Detailed Design
[Component boundaries for THIS phase. Reference the parent architecture doc for the full system view; this section names only the components touched in this phase.]

## Risk Assessment
[Risks scoped to this phase, with mitigation strategies. Copy from the parent risk register; filter to phase-relevant rows.]

## Implementation Strategy
### Tasks (already atomic — do not re-decompose)
- tasks/<phase>/001_<title>.md — effort: M, user_input: none, pair_test: tasks/<phase>/tests/001_<title>.md
- tasks/<phase>/002_<title>.md — ...
[Generated from frontmatter; do not edit by hand.]
### Team decomposition (suggested)
[Group atomic tasks along the dependency graph into team buckets. Thin pass — tasks are already TDD-granular.]
### Acceptance gates
- runbooks/<name>.sh — gates tasks 001, 003
- runbooks/<other>.py — gates tasks 002
[Each runbook has a sibling .md contract; the orchestrator calls exit-0 on the runbook, not "npm test".]

## Architecture Validator (plan-project addition)
- Session name: <project>-validator
- Trigger condition: all tasks in this phase pass acceptance gates
- Sign-off contract: validator emits either `phase-<name>-signoff.md` (next phase unlocks) or `phase-<name>-refinements.md` (new tasks landed, phase reopens)
- This step is NOT in deliver-project's default flow; the orchestrator must invoke it explicitly at phase close.

## Invocation
Invoke deliver-project with this brief as the design plan input:
  "Implement the <phase-name> phase using the details from dispatch/<phase-name>/brief.md"
The brief carries all sections deliver-project's Phase 1.0 validation requires; it will pass without modification.
```

This is the contract. If a phase brief doesn't exist or is missing any of the required headings, deliver-project's Phase 1.0 validation will reject it; the skill MUST emit one per phase with all sections populated.

Three deliver-project behaviors plan-project relies on but does not require deliver-project to be aware of:

1. **Tasks are already atomic** — deliver-project's "decompose into 3-5 teams" step becomes thin (group atomic tasks along the dependency graph), not generative.
2. **Acceptance gates cite runbooks**, not "tests pass" — deliver-project's verification iron law resolves to runbook exits, not handwritten checks.
3. **Phase boundaries trigger the architecture validator** — this is what plan-project uniquely contributes and is NOT in deliver-project's current behavior. The orchestrator session must invoke the validator at phase close even if deliver-project doesn't prompt for it.

If deliver-project is invoked **without** the dispatch brief, the workplan's value is partially preserved through the runbooks (which gate verification regardless of who dispatches them), but the architecture-validator step is lost. Don't ship without the brief.

---

## Output structure

The skill produces this filesystem layout (relative to the project root, or a `workplan/` subdirectory if the project isn't workplan-shaped):

```
INDEX.md                              # the single living dispatch document
tasks/
  _reference/
    exemplar.md                       # annotated reference task (see below)
  <phase-name>/
    NNN_<title>.md                    # feature task
    tests/
      NNN_<title>.md                  # paired test task, mirrors feature path
runbooks/
  <name>.{sh,py,...}                  # deterministic verification scripts
  <name>.md                           # contract: inputs, outputs, exit codes
handoff/
  YYYY-MM-DD_<topic>.md               # dated handoff documents
```

### Naming rules

- **Phase directories** use names, not numbers: `correctness/`, `smoke/`, `inversion/` — not `P0/`, `P1/`. Numbers without names are forgettable; named directories are searchable.
- **Task filenames** use 3-digit zero-padding: `001_fp32_audit.md`, not `1_fp32_audit.md` or `task-1.md`. Zero-padding keeps `ls` ordering stable past 9 tasks.
- **Paired tests** mirror feature paths under a `tests/` subdir: feature `tasks/correctness/001_fp32_audit.md` ↔ test `tasks/correctness/tests/001_fp32_audit.md`. Same NNN, same title.
- **No `_test.md` suffix** — `_test.{py,go,ts}` already means "this IS a test" in every other context. A task spec about authoring tests is a different concept; the `tests/` subdir carries the relationship without the semantic collision.
- **Reference exemplar** lives at `tasks/_reference/exemplar.md` — leading underscore so it sorts first and is visibly out-of-band.
- **Handoff filenames** are the only place dates belong (`handoff/2026-05-04_phase-correctness-sign-off.md`). Everywhere else, git carries history.

---

## INDEX.md required sections

INDEX.md is the live runway. The architecture document points at it. Required sections, in this order:

1. **Phase symbol legend** — explicit P0=correctness, P1=smoke, etc. mapping. Without this, search-by-P3 doesn't work.
2. **How to dispatch a task** — three modes (fresh session / Agent subagent / local execution).
3. **Roles** — creator/validator, orchestrator, worker, with explicit boundaries (including the code-review split).
4. **Phase order and gating** — which phase blocks which.
5. **Dependency graph** — ASCII or Mermaid. Just essential edges; do not try to render every task.
6. **Status table** — per-phase, with columns: `Status / Effort / User-input / Blocks / Blocked by`.
7. **Decision points** — explicit list of the user's actual synchronous obligations, separated from routine `review` tasks.
8. **Runbook inventory** — script → what it gates → which tasks use it.
9. **Phase entry criteria** — definition-of-done for each phase.
10. **Validator session naming convention** — state the resumable session name (default: `<project>-validator`). Without a stable name, "bring back the named session" doesn't have an address.
11. **House rule** — re-state the bottleneck-elimination principle: every "user, please verify" check is a candidate for a runbook.

---

## Task spec structure

Every task file uses this structure. Frontmatter is enforced; the dependency graph is rendered from it.

```markdown
---
phase: correctness
effort: M                       # S | M | L (see calibration below)
user_input: none                # none | review | decision
blocks: [smoke/002_inversion_smoke]
blocked_by: [correctness/000_fp32_baseline]
pair_test: correctness/tests/001_fp32_audit
runbook: runbooks/fp32_audit.sh # optional; required if acceptance gate uses one
---

# 001 — fp32 audit

## Context
[What the task is, why it exists, where it sits in the phase. Two paragraphs max.
Worker has no design context; this section is their entire briefing.]

## Deliverable
[Concrete artifacts. File paths. Function signatures. Numeric thresholds.
Not "fix the bug" — "function `audit_fp32(x)` in src/foo/audit.py returns
`AuditReport` with `max_abs_error < 1e-3` against the reference set."]

## Acceptance gates
- [ ] runbook `runbooks/fp32_audit.sh` exits 0 on input set X
- [ ] JSON output `reports/fp32_audit.json` validates against schema Y
- [ ] paired test `correctness/tests/001_fp32_audit` lands and runs green

## Anti-deliverable
[Explicit guardrails — what the worker MUST NOT do. "Do not loosen the 1e-3
threshold to make the gate pass. If the threshold is unreachable, file a
follow-up to reclassify the task; do not relax the contract."]

## Notes
[Decision authority for ambiguous calls. Pointers to relevant docs.
"For metric disagreements between runbook and reference, runbook wins —
the reference set is older than the current op. Escalate to validator
session `<project>-validator` if disagreement exceeds 1%."]
```

### Why each section earns its place

- **Context** is the worker's briefing. Without it, the worker reads the architecture document and burns context window.
- **Deliverable** is the contract. Vague deliverables produce vague output.
- **Acceptance gates** cite runbooks and numeric thresholds, not "tests pass." Specificity is the contract.
- **Anti-deliverable** is the structural defense against tired-worker corner-cutting. Without it, a worker quietly relaxes a threshold to make the gate green.
- **Notes** carries decision authority and pointers, so the worker doesn't need to escalate for routine ambiguity.

The annotated reference at `tasks/_reference/exemplar.md` walks through one real task with inline annotations on what makes each section work. **One annotated exemplar is worth more than ten lines of instruction.** Always bundle it.

---

## Effort calibration

S/M/L is calibrated against **token budget + context-window cost + irreversibility risk**, not wall-clock. Wall-clock varies wildly by worker; the structural shape doesn't.

- **S** — single bounded change, fits comfortably in one session's context, low blast radius if done wrong (revert-and-retry costs little). Examples: precision audit, NaN bisect, single-runbook authoring.
- **M** — multi-step but design-clear; one session is plausible but two is realistic; moderate blast radius. Examples: a module retool, a controller pretrain.
- **L** — design questions surface during execution; almost certainly needs splitting; high blast radius if done wrong (downstream tasks depend on choices made here). Examples: dimensionality discovery, surrogate vocoder training, frication modeling.

### Bump-up rule

Any task where a worker hits "oh shit, this is bigger than the brief" stops, files a follow-up to reclassify, and splits. **Bumping S→M or M→L mid-task is an expected signal that the original brief under-specified, not a failure of the worker.** The skill normalizes this so workers don't push through under-specified tasks just to honor the original effort tag.

---

## Runbook contract

Runbooks are the closed-loop principle made concrete. Every runbook MUST:

- Take a single argument or read from a known input path.
- Emit JSON for machines (write to a documented output path) **and** a one-line summary for humans (stdout).
- Return exit code 0 (pass) or non-zero (fail).
- Have **no LLM in the loop** — these run unattended, possibly via cron / CI.
- Document its contract in a sibling `runbooks/<name>.md`: inputs, outputs, exit codes, what tasks gate on it.

Tasks invoke runbooks in their acceptance gates. A worker session can self-verify before reporting "done." Whenever a runbook can replace a "user, please listen and tell me if this sounds right" check, prefer the runbook.

If an LLM is in the loop, it's a **task**, not a runbook. Runbooks are deterministic.

---

## The workplan-validator runbook

The skill ships **one mandatory runbook**: `runbooks/validate_workplan.{sh,py}`. This is what turns frontmatter from decoration into enforcement. Without it, `pair_test`, `blocks`, `blocked_by`, and `runbook` fields are just hints.

### What it checks (all blocking unless marked report-only)

- **Frontmatter parses** for every task file under `tasks/` (excluding `_reference/`).
- **Enum values are valid:** `effort ∈ {S, M, L}`, `user_input ∈ {none, review, decision}`, `phase` matches the phase-symbol legend in INDEX.md.
- **Phase-symbol legend is present** in INDEX.md and lists every phase that has tasks on disk.
- **Dependency graph is sound:** no cycles, no dangling references in `blocks` / `blocked_by` (every referenced task exists).
- **`blocks` / `blocked_by` reciprocity:** for every `blocks: [X]` on task A, X's `blocked_by` must contain A (and vice versa). Asymmetric edges fail.
- **Every feature task has a `pair_test` field.** Feature tasks are tasks living directly under `tasks/<phase>/` (not under `tasks/<phase>/tests/`). Missing `pair_test` is a hard fail; this is what makes the field enforcement instead of decoration.
- **`pair_test` resolves and is reciprocal:** the referenced file exists at `tasks/<phase>/tests/NNN_<title>.md`, has the same NNN and phase as the feature, and no two feature tasks share the same `pair_test`.
- **No orphan tests:** every file under `tasks/<phase>/tests/` has exactly one feature task pointing at it via `pair_test`.
- **Runbook references resolve:** every `runbook` field points to a file that exists in `runbooks/`, and that runbook has a sibling `<name>.md` contract.
- **INDEX.md graph matches frontmatter:** the dependency graph and status table reflect the on-disk task set (no orphans, no phantom rows). Drift is a hard fail; the validator is what keeps INDEX honest.
- **Dispatch briefs exist** for every phase that has tasks on disk: `dispatch/<phase>/brief.md` is present and references all tasks in the phase.
- **Decision-point counts (report-only):** output per-phase decision count and global ratio. Does not block.

### Output contract

- Exit 0 on full pass, non-zero on any failure.
- Write a JSON report to `reports/workplan_validation.json` with per-check results.
- One-line stdout summary: `validate_workplan: 47 tasks, 0 errors, 3 decisions (6.4%) — pass`.

### Where it gates

- **Skill exit gate:** the skill does not ship a workplan unless this runbook passes.
- **Orchestrator pre-dispatch:** the orchestrator runs it before each phase dispatch as a sanity check that no out-of-band edits broke the graph.
- **CI:** if the project has CI, this runbook should run on every commit that touches `tasks/` or `INDEX.md`.

Authoring this runbook is part of the skill's output, not optional. If the skill ships without it, the rest of the structure is unenforceable.

---

## Process when running this skill

1. **Read the architecture document fully.** Identify phases, modules, validation gates, risks.
2. **Audit existing tests / infra.** Dispatch a subagent if the codebase is large. Know what's stale, what's reusable, what's missing — don't plan tasks for work that already exists.
3. **Inventory the natural dispatchable units of work.** Each unit becomes a task. Aim for unit-of-work, not unit-of-time.
4. **Identify the dependency edges.** Most tasks have one or two; flag the ones that block many. Render in the graph.
5. **Surface decision points.** Be ruthless — argue against your own first instinct to ask the user. Most "user input" is mechanizable.
6. **Build the runbook inventory before the tasks**, so tasks can reference it. Even stub-only runbooks are valuable; a worker can flesh out the implementation while still meeting the contract.
7. **Author `runbooks/validate_workplan.{sh,py}` early** — the structural-enforcement runbook for the workplan itself. The skill cannot pass its own hard gates without it.
8. **Write tasks in dependency order.** P0 / INFRA fully fleshed; later phases can be skeletons that get authored as their dependencies clear (the world will have more information by then). **Fully flesh out the next 1–2 phases; later phases can wait.** Pre-committing detail that will rot is worse than under-specifying.
9. **Pair every feature task with a test task.** Mirror the path under `tests/`. Same NNN. Set `pair_test` in frontmatter. The validator runbook will fail if the pair file is missing.
10. **Write the annotated reference exemplar.** Pick a representative medium-effort task, include it verbatim at `tasks/_reference/exemplar.md`, annotate inline what makes each section work.
11. **Emit a dispatch brief per phase** at `dispatch/<phase>/brief.md`. Each brief is the design-plan-shaped artifact `deliver-project` consumes; without it, the handoff is fuzzy.
12. **Run `validate_workplan` against the skill's own output.** If it exits non-zero, fix and re-run. The skill does not ship a workplan that fails its own validator.
13. **Write the handoff document.** What landed, what's next, what the architecture validator should ask Codex when phases return.
14. **Update the architecture document** to point at INDEX.md as the live runway. Architecture is strategy; workplan is execution.
15. **Commit + push** in a single clean atomic commit. The skill leaves no half-finished state.

---

## Self-stress-test before generalizing

The first time the skill produces a workplan for a new project, **run that workplan through one full phase-completion cycle** before generalizing. The cycle is complete when all of these have happened:

1. P0 tasks dispatched (orchestrator session reads INDEX.md, fans out per the dependency graph).
2. At least one feature/paired-test pair runs through to completion: feature lands, test lands, test runs green against feature deliverable, runbook acceptance gate exits 0.
3. `validate_workplan` runs as a pre-dispatch sanity check and exits 0; if it doesn't, the skill itself is broken and gets patched before continuing.
4. Phase-close trigger fires: orchestrator hands control to the architecture validator session.
5. Validator emits either sign-off (in which case P1 unlocks) or refinement tasks (in which case the loop repeats on the new tasks).
6. A postmortem document lands at `handoff/<date>_p0-postmortem.md` capturing what broke in the skill itself and what got patched.

The skill is unproven until step 6 lands. Skipping this loop ships a structural artifact that hasn't been compiled.

---

## Anti-patterns to avoid

- **One giant task file.** Split anything > 1 session of effort.
- **User-input default.** If a check could be mechanized, it should be.
- **Phase numbers without names.** P3-2 is forgettable; `pretraining/002_body_model_pretrain.md` is not.
- **Validator/orchestrator collision.** Don't assume the orchestrator has design context — only the creator/validator does.
- **Skeleton tasks for the immediately-dispatchable phase.** Fully flesh out the next 1–2 phases; later phases can wait. World changes; don't pre-commit detail that will rot.
- **Runbooks that secretly call an LLM.** If an LLM is in the loop, it's a task, not a runbook. Runbooks are deterministic.
- **`_test.md` suffix on test tasks.** Collides with `_test.{py,go,ts}` semantics. Use the `tests/` subdir mirror instead.
- **Tests folded into feature tasks.** Workers under pressure cut tests first. Pair them as sibling tasks so the cut is visible.
- **Date in filenames except handoffs.** Encourages forking instead of updating. Single living INDEX.md with dated entries inside; git carries history.
- **No phase-symbol legend.** Without one, P0/P1/P2 are unsearchable noise.
- **No paired-test edge in the graph.** Naming alone makes the link discoverable but not enforceable. Surface `pair_test:` from frontmatter in the rendered graph.
- **Skipping the self-stress-test.** A workplan that hasn't been around the loop once is a hypothesis, not a tool.

---

## Composition with sibling skills

If this plugin's neighbors `assess-project` and `deliver-project` (or equivalents) are present:

- At skill entry, if the architecture document is missing required sections (executive summary, requirements, risks), **call `assess-project`** rather than planning on top of a partial design.
- At phase close, the validator session **calls the equivalent of `assess-project`'s phase-close review** (definition-of-done, risk-register check) rather than reimplementing.
- After the workplan is written, the harness can hand off to **`deliver-project`** to execute. The workplan owns the dispatch graph and runbook layer; `deliver-project` owns worktrees, parallel team launch, and PR consolidation.

If sibling skills are absent, leave seams as comments rather than guessing their interfaces. Don't fail closed — produce the workplan with `# TODO: invoke deliver-project if available` markers.

---

## Hard gates

Non-negotiable preconditions for skill output. Do not ship the workplan if any of these are unmet:

- **<HARD-GATE>** Architecture document exists, is reviewed (not draft), has been read in full, and contains the sections listed in *Input contract* above.
- **<HARD-GATE>** `runbooks/validate_workplan.{sh,py}` exists, runs against the workplan, and exits 0. This is the gate that makes every other structural check enforceable.
- **<HARD-GATE>** Every task with a runbook acceptance gate has a runbook file (even a stub) on disk with a documented contract.
- **<HARD-GATE>** The next 1–2 phases are fully fleshed out; later phases may be skeletons.
- **<HARD-GATE>** `tasks/_reference/exemplar.md` exists and walks through one task with inline annotations.

If any hard gate is not met, **the skill stops and reports what's missing**. It does not ship a partial workplan and hope.

### Soft checks (report-only; surfaced by the validator, do not block ship)

- Decision-point counts: zero blocking decisions per phase, ~one durable decision per phase, global ratio ≤ 5–10%. The validator emits the numbers; the human decides whether to restate the workplan.
- Validator session name documented in INDEX.md (omitting it just makes the orchestrator have to ask once on first dispatch).

The hard/soft split is consistent: anything `validate_workplan` blocks on is a hard gate. Anything it merely reports is a soft check. There is no third category.

---

## Communication style

When running this skill:

- Announce the entry to each major step (read architecture → audit infra → inventory tasks → ...).
- Surface the decision-point ratio explicitly before shipping (e.g., "47 tasks, 3 decisions, 6.4% — within target").
- Flag any runbook stubs you authored without implementations, so the orchestrator knows where the seams are.
- End with a one-paragraph handoff: workplan location, validator session name, recommended first dispatch.

The skill produces an artifact; it does not narrate. Save commentary for the handoff document.
