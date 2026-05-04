---
name: orchestrate-workplan
description: Use to drive a workplan (INDEX.md + tasks/ + runbooks/ + dispatch/) to completion. Designed for cheap, fast models — keeps itself on rails via mandatory TodoWrite, dispatches workers per task, runs deterministic runbook gates, escalates failures to a more capable verifier subagent, and triggers the architecture validator at phase boundaries. Consumes plan-project output but works with any workplan in the same shape.
---

# orchestrate-workplan

This skill is the runner for a pre-existing workplan. It does not plan, design, or write architecture. It executes a graph someone else built.

The skill is structured so a small, fast model can run it reliably. Capability isn't the bottleneck — bookkeeping is. The rails are:

- **TodoWrite** is mandatory. Every task transition (queued → in_progress → completed) is reflected in the todo list.
- **Runbooks** gate verification deterministically. No "looks good to me" — exit code 0 or fail.
- **A more capable verifier subagent** is dispatched on runbook failure. The orchestrator does not attempt to diagnose complex failures itself.

## Inputs

A workplan on disk in this shape (produced by `plan-project` or any compatible source):

```
INDEX.md                              # dispatch document with phase order, dep graph, status table
tasks/<phase>/NNN_<title>.md          # feature tasks
tasks/<phase>/tests/NNN_<title>.md    # paired test tasks
runbooks/<name>.{sh,py,...}           # deterministic verification scripts
runbooks/<name>.md                    # runbook contracts
dispatch/<phase>/brief.md             # per-phase dispatch brief
```

If `INDEX.md` is missing or the directory shape doesn't match, **stop and report**. Do not improvise.

## Outputs

- TodoWrite list reflecting workplan progress at all times.
- Runbook execution reports under `reports/`.
- Phase sign-off documents under `handoff/<date>_<phase>-signoff.md` (or refinement task files when validator rejects).
- A clean exit when the final phase is signed off.

## The dispatch loop

This is the core loop. Run it until all phases are signed off or you hit a hard stop.

```
0. On session start: replay orchestrate.ledger.jsonl if present (see "Resume protocol").
1. Run runbooks/validate_workplan.{sh,py}; if non-zero, stop and report.
2. Read INDEX.md.
3. Identify the current phase (lowest-numbered phase not yet signed off).
4. Read the phase's dispatch brief at dispatch/<phase>/brief.md.
5. Build/restore the TodoWrite list for this phase from the brief's task list and the ledger.
6. For each task in dependency order (parallelizing where the graph allows):
   a. Mark todo in_progress, append ledger entry, set worker id and attempt.
   b. Dispatch a worker subagent (see "Dispatching a worker").
   c. Branch on worker status (see "Failure handling"):
        - bumped-up / blocked → mark todo blocked, write handoff doc, advance.
        - done                → proceed to runbook.
   d. Run the runbook(s); branch on exit code:
        - 0     → mark todo completed, append ledger entry, advance.
        - != 0  → enter the verifier-and-retry loop (see "Failure handling").
7. When all phase tasks are completed or blocked, trigger the architecture validator.
8. If validator signs off → write phase signoff handoff, next phase becomes current, GOTO 1.
   If validator emits refinements → integrate refinement tasks into TodoWrite, re-run
   validate_workplan, GOTO 6.
9. When the final phase is signed off, write a top-level completion handoff and exit.
```

## Dispatching a worker

A worker is a fresh subagent that implements one task. Workers have no design context beyond what's in the task file.

For each task:

- Read the task file in full. Pass its content to the worker as the prompt.
- Worker implements per the `Deliverable` section, respects the `Anti-deliverable`, and runs the runbook in `Acceptance gates` to self-verify before reporting.
- Worker reports back with: status (done / blocked / bumped-up), files changed, verification evidence (runbook stdout summary).

**Worker self-reports are not trusted.** The orchestrator runs the runbook independently after the worker reports done. This is non-negotiable — workers under pressure rationalize completion claims.

## Runbook gates

After every worker reports done, run the task's runbook(s):

```
bash runbooks/<name>.sh   # or python, etc., per the runbook contract
```

- Exit 0 → pass.
- Non-zero → fail. Capture stdout/stderr to `reports/<task>-<timestamp>.log` for the verifier subagent to read.

Runbooks are deterministic. The orchestrator does not re-interpret their output — it reads the exit code. If you find yourself reasoning about whether a runbook "kind of passed," that's a bug; the runbook contract is incomplete and needs sharpening.

## Failure handling

The flow has two branch points: **worker status** (before the runbook) and **runbook result** (after).

### Branch 1 — Worker status check (before runbook)

When the worker returns, inspect its status before doing anything else:

- **`done`** → proceed to runbook gates.
- **`bumped-up`** → the worker says "this task is bigger than the brief." Do NOT run the runbook; the worker hasn't implemented the task. Mark the todo `blocked`, write a follow-up file at `tasks/<phase>/<NNN>_followup.md` describing the scope the worker discovered, and continue with the next task in the dependency graph. The validator session picks this up at phase close and decides whether to split, defer, or rescope. Bump-up is not a failure of the worker — it's a signal that the original brief under-specified. Do not pressure the worker to push through.
- **`blocked`** → worker hit an external dependency it can't resolve (missing service, missing data). Mark the todo `blocked` with the reason, continue.

### Branch 2 — Runbook result (after a `done` worker)

Run the task's runbook(s). The orchestrator does not interpret output beyond the exit code.

- Exit 0 → mark todo `completed`, advance.
- Non-zero → enter the verifier-and-retry loop below.

### The verifier-and-retry loop

```
attempt = 1
while attempt <= 3:
    1. Dispatch verifier subagent (more capable than orchestrator) with:
         - task file (Deliverable, Acceptance gates, Anti-deliverable, Notes)
         - worker diff (git diff in task scope)
         - runbook stderr/stdout from reports/<task>-<attempt>.log
    2. Verifier returns one of:
         - RETRY_WITH_FIX <fix description>
         - ESCALATE_TO_VALIDATOR <reason>
    3. If RETRY_WITH_FIX:
         - Dispatch a fix subagent with the verifier's fix description
         - Re-run the runbook → reports/<task>-<attempt+1>.log
         - If runbook now exits 0: mark completed, exit loop
         - Otherwise: attempt += 1, continue
    4. If ESCALATE_TO_VALIDATOR:
         - Mark todo blocked
         - Write handoff/<date>_<task>-escalation.md with the verifier's reason
         - The architecture validator picks this up at phase close
         - Exit loop

if attempt > 3:
    # Three-strikes rule fires
    Mark todo blocked
    Write handoff/<date>_<task>-three-strikes.md summarizing all three attempts
    The architecture validator picks this up at phase close
```

**Three-strikes is a hard stop, not a recommendation.** Do not attempt a fourth fix. The pattern of repeated failed fixes almost always means the symptom is being patched, not the root cause — at that point the validator (which has design context) is the right escalation, not another fix attempt.

### Choosing the verifier model

Priority chain — first match wins:

1. **`ORCHESTRATE_VERIFIER_MODEL` env var** — if set, use it verbatim. This is the universal, harness-agnostic override; end-users configure it via `settings.json`'s `env` block, their shell rc, or any equivalent in non-Claude-Code harnesses.
2. **Harness-registered verifier capability** — if your harness exposes a dedicated review tool (e.g. an MCP review tool, a registered subagent type), prefer it. The skill targets Claude Code today, where this surface is `mcp__*` tools and `Agent` subagent_type entries; other harnesses register equivalents.
3. **Fallback dispatch** — generic Agent-style subagent with no model override, letting the harness pick the most capable available.

Do not hardcode a model name in the skill. Do not fall back to "yourself" — the whole point of dispatching the verifier is to step up in capability. If none of the three priority entries resolve, **stop and report**; do not silently self-verify.

## Phase boundary triggers

When every task in a phase is either `completed` or `blocked` (per TodoWrite — no `pending` or `in_progress` remaining), the orchestrator triggers the **architecture validator session**, not the user. The validator:

- Is named per the workplan's convention (default: `<project>-validator` — read from INDEX.md).
- Reviews the phase's deliverables against the architecture document.
- Reads any three-strikes notes and bump-up follow-ups in `handoff/`.
- Emits one of:
  - **Sign-off** → writes `handoff/<date>_<phase>-signoff.md`. Next phase unlocks.
  - **Refinements** → writes `handoff/<date>_<phase>-refinements.md` and adds new task files under `tasks/<phase>/`. Phase reopens; orchestrator integrates new tasks into TodoWrite.

The user only enters the loop if the validator surfaces a `decision`-tagged refinement task during refinement.

## TodoWrite contract

The orchestrator's todo list is one of two state surfaces (the other is the durable ledger — see "Resume protocol" below). Every state change goes through TodoWrite immediately — not at the end of a batch.

### Todo item schema

Each todo item carries a structured `content` field with these required components, formatted so they're machine-readable on resume:

```
[<task-path>] <one-line title>
  deps: <comma-separated task paths>
  pair_test: <test task path>
  runbook: <runbook path>
  attempt: <N>
  worker: <subagent dispatch id, set when in_progress>
  report: <path to latest reports/<task>-<N>.log, set after runbook>
```

Example:
```
[tasks/correctness/001_fp32_audit] fp32 audit
  deps: tasks/correctness/000_fp32_baseline
  pair_test: tasks/correctness/tests/001_fp32_audit
  runbook: runbooks/fp32_audit.sh
  attempt: 2
  worker: agent_8a2f1c
  report: reports/001_fp32_audit-2.log
```

This schema is what makes the todo list a recoverable ledger, not just a progress display.

### Status transitions

- `pending` → `in_progress`: when a worker is dispatched. Set `worker` and `attempt`.
- `in_progress` → `completed`: only after the runbook exits 0. Worker self-report is not enough.
- `in_progress` → `blocked`: when worker reports `bumped-up` / `blocked`, or three-strikes fires, or verifier returns `ESCALATE_TO_VALIDATOR`. Always paired with a handoff document.
- `blocked` → `pending`: only when the validator session emits refinements that resolve the blocker.

Only one `in_progress` per task slot. Parallelism is achieved by dispatching multiple workers where the dependency graph allows; each parallel slot has its own todo.

The user can read the todo list at any time to see exactly where the orchestrator is. This is what makes a Haiku-driven orchestrator auditable.

## Resume protocol

The orchestrator MUST be resumable across session boundaries. Sessions die — quota exhaustion, disconnects, harness restarts. A workplan that requires a single uninterrupted session is not orchestratable on a small model.

### The ledger

Append-only, one line per state transition: `orchestrate.ledger.jsonl` at the workplan root.

Each entry:

```json
{"ts": "2026-05-04T12:34:56Z", "task": "tasks/correctness/001_fp32_audit", "from": "pending", "to": "in_progress", "attempt": 1, "worker": "agent_8a2f1c", "report": null}
{"ts": "2026-05-04T12:38:12Z", "task": "tasks/correctness/001_fp32_audit", "from": "in_progress", "to": "completed", "attempt": 1, "worker": "agent_8a2f1c", "report": "reports/001_fp32_audit-1.log"}
```

Append on every transition, immediately, before the next action. This is the orchestrator's only durable record — TodoWrite state is in-memory.

### On session start

1. Check for `orchestrate.ledger.jsonl` at the workplan root.
2. If present: replay it to reconstruct the current TodoWrite state, attempt counts, and which tasks are in flight / blocked / completed.
3. Read `reports/` and `handoff/` for the artifacts referenced in the ledger.
4. Resume the dispatch loop from the current phase.
5. If the ledger references a worker that was `in_progress` at session death: treat it as a failed dispatch (assume the worker did not complete), advance attempt count, and re-dispatch on the same task.

If no ledger exists, this is the first session — initialize and proceed.

### Why this matters

Without a ledger, three-strikes loses count across sessions, in-flight workers become orphans, and the orchestrator can repeat work or skip work. With it, a Haiku session can die mid-phase and the next session picks up exactly where the last left off.

## Configurability

The skill reads these env vars at start:

| Variable | Purpose | Default |
|---|---|---|
| `ORCHESTRATE_VERIFIER_MODEL` | Explicit verifier subagent choice (passed verbatim to the dispatch call) | unset — use harness inference |
| `ORCHESTRATE_WORKPLAN_ROOT` | Path to workplan root if not the current directory | `.` |
| `ORCHESTRATE_MAX_PARALLEL` | Maximum parallel worker slots within a phase | `3` |

These are the only configuration surfaces. Everything else is read from the workplan on disk.

## Hard gates

- **<HARD-GATE>** Workplan structure on disk matches the expected shape. If `INDEX.md` is missing or `dispatch/<phase>/brief.md` doesn't exist for the current phase, stop and report.
- **<HARD-GATE>** `runbooks/validate_workplan.{sh,py}` runs and exits 0 before phase dispatch starts, and again after the validator session emits refinements (refinements add tasks; they need to pass the same structural checks as the original).
- **<HARD-GATE>** TodoWrite is initialized before any worker dispatches. No dispatching without a todo entry.
- **<HARD-GATE>** Ledger (`orchestrate.ledger.jsonl`) is appended to before every state transition. No transition without a ledger entry.
- **<HARD-GATE>** Runbook acceptance gates run after every `done` worker. No "the worker said it's done" shortcuts.
- **<HARD-GATE>** Verifier subagent resolves to a more capable model than the orchestrator. If the priority chain returns nothing, stop and report — do not silently self-verify.
- **<HARD-GATE>** Three-strikes rule fires hard. After 3 failed fixes on the same task, stop and write the handoff note. Do not attempt a fourth.
- **<HARD-GATE>** Architecture validator is triggered at every phase close, not skipped.

## Anti-patterns

- **Skipping TodoWrite "for speed."** TodoWrite is what makes the orchestrator auditable and recoverable. Skipping it means losing all state on session end.
- **Trusting worker self-reports.** Workers rationalize. Run the runbook.
- **Self-verifying instead of dispatching the verifier.** The orchestrator is intentionally cheap; complex diagnosis is what the verifier subagent is for.
- **Hardcoding a verifier model name.** Breaks portability across harnesses. Use the priority chain.
- **Pushing past three strikes.** The pattern of repeated failed fixes is the rule's diagnostic signal. Stop, escalate, let the validator decide.
- **Triggering the user instead of the validator.** Phase boundaries trigger the architecture validator session. The user only sees a `decision`-tagged refinement.

## Communication style

- Announce phase entry and exit.
- Report task transitions concisely (`task X dispatched`, `task X passed`, `task X failed → verifier`).
- Surface runbook failure summaries verbatim (orchestrator does not interpret).
- End each phase with a one-paragraph summary written to `handoff/`.

The skill drives bookkeeping, not narration. Save commentary for the handoff documents.
