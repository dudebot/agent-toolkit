# Tracking Issue Draft

Title: Build intent-to-workflow factory skill/package

Labels:

- workflow
- skills
- orchestration
- bootstrap

## Body

Build a reusable `workflow-factory` package for `agent-toolkit` that turns messy project intent into durable, reviewable workflow artifacts before execution.

### Problem

Project intent currently lives across chats, GitHub issues, repos, notes, and memory. Turning one messy project idea into high-quality workflow prompts takes too much human energy and does not scale across many active or parked projects.

### Goal

Create a reusable package that supports:

- intent capture
- problem clarification
- workflow drafting
- adversarial review
- implementability review
- final runnable prompts
- child-intent backlog extraction
- handoff artifacts

### Non-Goals

- No dashboard or full PM SaaS.
- No automatic execution of newly created workflows.
- No private project details in public examples.
- No requirement that GitHub issues become canonical state.

### Deliverables

- `plugins/workflow-factory/.claude-plugin/plugin.json`
- `plugins/workflow-factory/README.md`
- `plugins/workflow-factory/skills/workflow-factory/SKILL.md`
- role prompts under `plugins/workflow-factory/prompts/`
- schemas under `plugins/workflow-factory/schemas/`
- templates under `plugins/workflow-factory/templates/`
- generic project registry/state templates for control repos
- bootstrap work item under `plugins/workflow-factory/work-items/`
- marketplace entry in `.claude-plugin/marketplace.json`

### Acceptance Criteria

- A messy intent can be saved as a structured intent file.
- A problem brief can be generated without requiring polished requirements.
- Candidate workflows include inputs, outputs, stop conditions, red lines, and handoff artifacts.
- Reviews are durable and actionable.
- Child work is captured as inbox/deferred child intents.
- The package composes with `plan-project` and `orchestrate-workplan`.
- Another fresh agent session can continue from the files alone.
