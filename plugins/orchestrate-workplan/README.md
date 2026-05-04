# orchestrate-workplan

A skill that drives a workplan (produced by `plan-project` or any compatible workplan layout) to completion. Designed to run on a cheap, fast model (e.g. Haiku) that stays on rails via mandatory TodoWrite usage and delegates verification to a more capable model on demand.

## What it does

```
workplan on disk           → orchestrate-workplan          → done phases
(INDEX.md, tasks/, runbooks)   (this skill, on Haiku)         (validator-signed)
```

Per task:

1. Pick the next task from the dependency graph in `INDEX.md`.
2. Mark it in TodoWrite.
3. Dispatch a worker subagent with the task spec.
4. When the worker reports done, run the task's runbook acceptance gates (deterministic, no LLM).
5. If runbook passes → mark done in TodoWrite, advance.
6. If runbook fails → dispatch a verification subagent (more capable model) to diagnose, then either retry with a fix or escalate.

Per phase:

- When all phase tasks are complete, trigger the architecture validator session (named per the workplan's convention).
- Validator emits sign-off (next phase unlocks) or refinements (phase reopens with new tasks).

## Why Haiku

The orchestrator is mostly bookkeeping: pick task, dispatch, check runbook exit, update TodoWrite, advance. Capability isn't the bottleneck; cost and speed are. Haiku is the right tier — and the skill's structure (TodoWrite as rails, runbooks as deterministic gates, more-capable verifier on failure) is designed to keep Haiku reliable.

## Configurability

The skill reads (in priority order):

1. `ORCHESTRATE_VERIFIER_MODEL` env var — explicit override of the verification subagent model
2. The harness's CLAUDE.md and tool inventory — picks the most capable available
3. Falls back to an `Agent` subagent with no model override

This means publishers don't bake a model choice into the skill, and end-users can configure via `settings.json`'s `env` block or shell rc.

## Companion skill

This skill consumes the output of [`plan-project`](../plan-project/README.md). You can use it standalone on any workplan that follows the same on-disk shape (INDEX.md + tasks/ + runbooks/ + dispatch/).

## Install

```
/plugin marketplace add dudebot/agent-toolkit
/plugin install orchestrate-workplan@agent-toolkit
```

## Status

v0.1.0 — first cut. Like `plan-project`, this skill is unproven until it's been around the loop once on a real workplan.
