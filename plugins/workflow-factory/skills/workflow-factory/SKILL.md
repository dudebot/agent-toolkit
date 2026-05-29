---
name: workflow-factory
description: Use when the user provides messy project intent and wants it converted into durable, reviewable workflow prompts before implementation. Produces structured intent records, problem briefs, candidate workflows, adversarial review, implementability review, finalized runnable prompts, handoff files, and child intent backlog items. Best for multi-session or multi-project work where state must survive outside chat.
---

# workflow-factory

This skill turns rough intent into workflow artifacts. It does not execute the resulting workflow unless the user explicitly asks for execution after approval.

## Driver

When the repository includes `scripts/workflow_factory.py`, prefer it for deterministic run setup, preflight, prompt rendering, telemetry, and validation instead of hand-writing long runner prompts. Use the prompt workflow directly only when the driver is unavailable or the user asks for manual operation.

Common flow:

```text
python3 plugins/workflow-factory/scripts/workflow_factory.py init-run --control-root <admin> --intent <intent.md>
python3 plugins/workflow-factory/scripts/workflow_factory.py run-stage --run <run-dir> --stage propose --runner codex --add-dir <target-repo>
python3 plugins/workflow-factory/scripts/workflow_factory.py validate-run --run <run-dir>
```

Add `--execute` to `run-stage` only when the user explicitly wants the stage launched. Without `--execute`, the driver renders the prompt and trace artifacts only.

## Core contract

Preserve the user's original intent, then make the next agent's job bounded:

```text
messy intent
-> intent record
-> clarified problem brief
-> candidate workflows
-> adversarial review
-> implementability review
-> final workflow prompt(s)
-> child intent backlog
-> handoff
```

The output is good only if a fresh session can continue from disk without chat memory.

## Portfolio intake

When the user wants to process many projects or mine open issues for likely work, start with `../../prompts/00_portfolio_intake.md`.

Use portfolio intake to create a project registry and intent inbox. It may infer candidate intents from issues, but inferred intents must be marked for user review and must not be approved automatically.

## Default output layout

If the user has a control repo, use its project layout. Otherwise create a local run folder:

```text
workflow_factory/runs/<date>-<slug>/
  intent.md
  problem_brief.md
  workflows/
    proposed/
    approved/
  reviews/
    adversarial_review.md
    implementability_review.md
  trace/
    trace_ledger.jsonl
    artifact_index.md
  child_intents/
  final_prompts.md
  handoff.md
```

For a control repo, prefer:

```text
projects/<project>/
  intents/inbox/
  workflows/proposed/
  workflows/approved/
  runs/<date>-<slug>/
    trace/
      trace_ledger.jsonl
      artifact_index.md
    factory_feedback/
  decisions.md
  project_state.md
```

For portfolio/bootstrap work that creates or updates multiple project entries, use:

```text
projects/_runs/<date>-<slug>/
  trace/
    trace_ledger.jsonl
    artifact_index.md
  factory_feedback/
  handoff.md
```

Use `projects/_runs/` only for cross-project control-plane runs. Use `projects/<project>/runs/` for
project-specific workflow runs. Do not create ambiguous `projects/runs/`.

The control repo is where project-management state lives. Target implementation repos should be referenced as metadata unless the user explicitly asks to write workflow artifacts there.

## Traceability contract

Every run must be auditable. Create:

- `trace/trace_ledger.jsonl`: append-only event log, one JSON object per meaningful transition.
- `trace/artifact_index.md`: map generated artifacts back to inputs, prompt refs, reviews, and decisions.
- `trace/rejections/*.md` when an artifact, workflow, assumption, or child intent is rejected or superseded.

Use `../../schemas/trace_event.schema.yaml` for trace event shape and `../../templates/trace_event.json` as the line template.

Record trace events for:

- original intent capture
- problem brief creation
- workflow draft creation
- adversarial review
- implementability review
- finalization
- user decisions
- child intent creation
- rejection, deferral, or supersession

The trace must be good enough to answer:

- Which source input produced this artifact?
- Which role prompt or runner produced it?
- Which review accepted, rejected, or changed it?
- Where did a bad assumption first enter?
- Which gate should have caught it?
- What child work was spawned and why?

When auditing a bad artifact, use `../../prompts/07_traceability_auditor.md`.

## Factory feedback

If the factory's own instructions, schemas, templates, or prompts are wrong or insufficient, create a feedback artifact instead of silently working around it.

Use `../../prompts/08_factory_feedback.md` and write to `factory_feedback/<id>.md` in the current run. Do not open a GitHub issue automatically. Mark whether the feedback should become an `agent-toolkit` issue after user approval.

## Required workflow

1. **Capture intent**
   - Save the user's raw words or a faithful excerpt.
   - Record outcome, why it matters, must-not-happen constraints, known inputs, urgency, and open questions.
   - Do not polish away uncertainty. Ambiguity is input data.

2. **Clarify problem**
   - Use `../../prompts/01_intake_clarifier.md`.
   - Output `problem_brief.md`.
   - Append a trace event for the transformation.
   - Do not design the implementation yet.

3. **Draft workflows**
   - Use `../../prompts/02_workflow_architect.md`.
   - Produce one or more candidate workflows with required inputs, allowed outputs, stop conditions, gates, and artifacts.
   - Add workflow draft entries to the artifact index.
   - Prefer several small staged workflows over one giant prompt when execution risk is high.

4. **Review**
   - Use `../../prompts/03_adversarial_reviewer.md` for failure modes and scope drift.
   - Use `../../prompts/04_implementability_reviewer.md` for repo/tool/file feasibility.
   - Require a capability preflight for workflows that depend on GitHub, private repos, network access, browser automation, Playwright, external services, writable directories, credentials, or broad filesystem permissions.
   - Reviews must produce actionable changes, not vibes-only commentary.
   - Rejections and required edits must be trace events, not only prose.

5. **Finalize**
   - Use `../../prompts/05_finalizer.md`.
   - Merge the brief, workflow draft, and reviews into approved workflow prompt(s).
   - Include exact artifacts, acceptance criteria, non-goals, and handoff expectations.
   - Mark approved, rejected, deferred, or superseded artifacts in the artifact index.

6. **Extract child intents**
   - Use `../../prompts/06_child_intent_extractor.md`.
   - New work discovered during design becomes child intent files, not hidden bullets.
   - Child intents default to inbox/deferred until the user approves them.
   - Each child intent must link to the trace event that spawned it.

7. **Gate**
   - Ask the user only for durable decisions: approve, reject, defer, split, merge, or prioritize.
   - Do not ask the user to supply implementation details that can be discovered from repo context.

8. **Feedback**
   - If a workflow exposes a defect in workflow-factory itself, write a factory feedback artifact.
   - Keep factory feedback separate from target-project child intents.

## Quality bar

A workflow is ready only when it has:

- A preserved original intent.
- A clear desired outcome and why-now reason.
- Required inputs and explicit missing-input behavior.
- Allowed outputs and forbidden outputs.
- Stop conditions and escalation conditions.
- Durable handoff artifacts.
- Trace ledger and artifact index.
- A child-intent policy.
- A capability preflight for every external dependency or permission boundary.
- Acceptance criteria that a reviewer can check.
- A statement of what must not be done.

## Hard gates

- Do not execute the workflow while producing it unless the user explicitly asks.
- Do not depend on chat history as canonical state.
- Do not produce untraceable final prompts. Every final prompt must trace back to source intent, intermediate brief, reviews, and approval state.
- Do not close, delete, or supersede source work without preserving durable content.
- Do not make child work auto-execute. It must enter an inbox or approval queue.
- Do not include private project details in reusable examples or public docs.
- Do not hide defects in workflow-factory itself. Create `factory_feedback/` items for upstream review.
- Do not silently skip missing GitHub auth, repo access, Playwright/browser access, network access, credentials, or writable paths. Fix them if explicitly allowed; otherwise write a durable blocked artifact and stop.

## Composition

- If the finalized workflow needs a dispatch-ready task graph, hand it to `plan-project`.
- If a workplan already exists and the user wants execution, hand it to `orchestrate-workplan`.
- If architecture is missing or unstable, keep the output at problem brief / workflow spec level.
