# Work Item: Intent-To-Workflow Factory

## Status

Naked work item for manual adversarial review.

## Premise

The user has many parallel projects and too much state spread across chats, GitHub issues, repos, and memory. They need a reusable AI-assisted workflow factory that turns messy intent into durable, reviewable workflows with minimal user effort.

The user should be able to provide:

- what they want
- why it matters
- what must not happen
- known inputs or repos
- urgency

Agents should then produce:

- a clarified problem brief
- proposed workflow(s)
- adversarial review
- implementability review
- final runnable workflow prompt(s)
- child intent backlog
- handoff artifacts

## Scope

Build an installable `agent-toolkit` package for intent intake and workflow generation. It should be reusable across a personal control repo and many implementation repos.

## Non-Goals

- Do not build a full PM SaaS or dashboard.
- Do not replace GitHub issues entirely.
- Do not run implementation workflows automatically.
- Do not require polished requirements from the user.
- Do not make project state depend on chat history.
- Do not include private project details in reusable examples or public docs.

## Proposed Package Shape

```text
plugins/workflow-factory/
  .claude-plugin/plugin.json
  README.md
  skills/workflow-factory/SKILL.md
  prompts/
  schemas/
  templates/
  work-items/
```

## Control Repo Shape

```text
projects/
  registry.yaml
  <project>/
    intents/
      inbox/
      accepted/
      rejected/
      deferred/
    workflows/
      proposed/
      approved/
      queued/
      completed/
    runs/
    decisions.md
    project_state.md
```

## Workflow

1. User drops messy intent.
2. Intake clarifier writes a structured intent and problem brief.
3. Workflow architect drafts one or more workflows.
4. Adversarial reviewer finds failure modes.
5. Implementability reviewer checks repo/tool feasibility.
6. Finalizer writes approved workflow prompt(s).
7. Child-intent extractor captures follow-up work.
8. User approves, rejects, defers, splits, or merges child intents.

## Acceptance Criteria

- A messy project idea can become a structured intent file.
- A structured intent can produce a workflow spec without further user effort.
- Every workflow has success criteria, stop conditions, artifacts, and non-goals.
- Reviews are saved as durable files.
- Child work is captured as new intent files.
- Another agent/session can continue from disk artifacts.
- GitHub issues can mirror approved workflows later, but are not canonical state.

## Manual Adversarial Review Questions

1. Does this solve the actual bottleneck, or just add another layer of process?
2. Is the user role small enough: approve, reject, defer, prioritize, and decide durable forks?
3. Are child intents controlled, or can the system create infinite backlog?
4. Are private project details protected from public reusable artifacts?
5. Is the file state thin enough to maintain by hand if automation fails?
6. Can this hand off cleanly to `plan-project` and `orchestrate-workplan`?

## Tracking Issue Draft

See `tracking_issue.md`.
