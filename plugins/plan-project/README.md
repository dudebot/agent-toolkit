# plan-project

A skill that turns a settled architecture into a dispatch-ready workplan. Slots between an architecture / design pass and a parallel-execution pass:

```
assess-project   →   plan-project   →   deliver-project
  (design)            (workplan)          (execute)
```

The skill produces an artifact (INDEX.md, phase task tree, runbooks, paired tests, annotated reference). It does not run the workplan — continuation across sessions is the harness's job.

## What it produces

```
INDEX.md                          # live dispatch document
tasks/
  _reference/exemplar.md          # annotated reference task
  <phase-name>/NNN_<title>.md     # feature task
  <phase-name>/tests/NNN_<title>.md   # paired test, mirrors feature path
runbooks/
  <name>.{sh,py,...}              # deterministic verification scripts
  <name>.md                       # runbook contract
handoff/
  YYYY-MM-DD_<topic>.md           # dated handoff
```

## When to use

All three must be true:
- Architecture is reviewed and frozen (not draft).
- Build is large enough to parallelize (multi-phase, multi-component).
- User wants async execution where they're in the loop only for genuinely durable decisions.

## Core invariants

1. **Closed-loop development** — any check that could be mechanized must be a runbook, not a user prompt.
2. **Decision-point discipline** — tasks tagged `none` / `review` / `decision`; `decision` ≤ 5–10% of tasks.
3. **Role separation with code-review split** — orchestrator does mechanical per-task review; validator does architectural per-phase review.
4. **Phase boundaries trigger the validator session, not the user.**
5. **Test tasks are first-class, paired with feature tasks** — feature can't ship without paired test landing and running.

See `skills/plan-project/SKILL.md` for the full skill body.

## Install

Via this marketplace:

```
/plugin marketplace add dudebot/agent-toolkit
/plugin install plan-project@agent-toolkit
```

## Composition

If sibling skills `assess-project` and `deliver-project` are present in the same workspace, this skill calls into them at the right boundaries (assess for incomplete architecture, deliver for execution) rather than reimplementing. If they're absent, the workplan ships with `# TODO: invoke <skill>` seams rather than guessing at their interfaces.

## Status

v0.1.0 — first cut. The skill is unproven until it's been around the loop once on a real project; first run should treat the workplan itself as a hypothesis to stress-test.
