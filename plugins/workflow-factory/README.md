# workflow-factory

A skill package for turning messy intent into durable workflow prompts before execution starts.

This is the intake and workflow-design layer that sits before `plan-project` and `orchestrate-workplan`:

```text
messy intent -> workflow-factory -> plan-project -> orchestrate-workplan
  (why/what)      (briefs/prompts)    (task graph)       (execution)
```

## What it does

The skill guides an agent through a repeatable workflow-production line:

1. Capture the original messy intent.
2. Optionally turn a project/repo list into a registry and intent inbox.
3. Convert intent into a structured problem brief.
4. Draft one or more candidate workflows.
5. Run adversarial and implementability reviews.
6. Finalize runnable workflow prompts and handoff artifacts.
7. Capture follow-up work as child intents instead of losing it in prose.
8. Maintain a trace ledger and artifact index so rejected or bad artifacts can be audited later.
9. Capture defects in the factory itself as reviewable feedback artifacts instead of noisy automatic issues.

## What it does not do

- It does not execute implementation work by default.
- It does not replace GitHub issues as visibility or collaboration surfaces.
- It does not require polished requirements from the user.
- It does not store project state in chat history.

## Suggested control-repo shape

```text
projects/
  registry.yaml
  _runs/
    <run_id>/
      trace/
      factory_feedback/
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

Use `projects/_runs/` for portfolio/bootstrap runs that touch many projects. Use
`projects/<project>/runs/` for one project-specific workflow. Avoid ambiguous `projects/runs/`.

The canonical state should be files in the control repo. GitHub issues can mirror approved work later.

## Install

Use the GitHub-backed marketplace for normal installs. Local path installs are only for active
development of this repository.

Claude Code:

```text
/plugin marketplace add dudebot/agent-toolkit
/plugin install workflow-factory@agent-toolkit
```

Codex:

```text
codex plugin marketplace add dudebot/agent-toolkit --ref main
codex plugin add workflow-factory@agent-toolkit
```

Refresh after upstream changes:

```text
codex plugin marketplace upgrade agent-toolkit
codex plugin remove workflow-factory@agent-toolkit
codex plugin add workflow-factory@agent-toolkit
```

For non-interactive runs, pass Codex global options before `exec`:

```text
codex -a on-request exec -C /path/to/control-repo -s workspace-write -
```

## Status

v0.1.0 - bootstrap skill and artifact templates. The first real use should manually review the generated workflows before execution.
