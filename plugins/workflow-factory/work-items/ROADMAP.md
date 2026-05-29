# Workflow Factory Roadmap

Tracking issue: https://github.com/dudebot/agent-toolkit/issues/2

## Current State

`workflow-factory` v0 exists as an installable skill package. It can capture messy intent, clarify the problem, draft workflows, run reviews, finalize prompts, and preserve child intents as durable files.

v0 is intentionally prompt-driven. It reduces cognitive load, but it does not yet enforce prerequisites, trace completeness, resource budgets, or stage order with code.

## Architectural Direction

The factory should evolve from:

```text
skill-guided workflow drafting
```

to:

```text
file-backed workflow state machine + trace driver + runner adapters
```

The orchestrator should not merely run prompts. It should decide whether a workflow is ready to run, verify prerequisites, capture telemetry, enforce traceability, and produce remediation work when blocked.

## Core Concepts

### Workflow Item

A workflow item is a durable unit of planned work. It should include:

- intent reference
- desired outcome
- required inputs
- capability prerequisites
- permission profile
- runner profile
- token/time budgets
- allowed outputs
- forbidden outputs
- stop conditions
- remediation policy
- validation criteria

### Capability Prerequisite

A prerequisite is a concrete capability required before a workflow can run.

Examples:

- GitHub auth account is correct.
- Target repo exists locally and is up to date.
- Target repo is writable or explicitly read-only.
- Playwright is installed.
- Browser profile or login session exists.
- Network access is allowed.
- API keys or credentials exist.
- Sandbox mode is sufficient.
- Required source artifacts exist.

Prerequisites must be machine-checkable whenever possible.

### Permission Profile

Each workflow should declare the narrowest acceptable permission profile:

- `read_only`
- `workspace_write`
- `multi_repo_write`
- `browser_automation`
- `network_required`
- `full_access_required`
- `external_side_effects`

The orchestrator should verify that the actual runner environment satisfies the declared profile. If it does not, the workflow should not start.

### Telemetry

Telemetry is operational measurement, not model reasoning. It should include:

- start time
- end time
- elapsed wall time
- runner
- model/provider
- input token estimate if available
- output token estimate if available
- total token usage if provider reports it
- retry count
- approval/escalation count
- tool/preflight failures
- final status
- artifacts created

Telemetry should be appended to run metadata and summarized in project state. It should help answer whether workflows are reducing cognitive load or just moving it around.

### Traceability

Traceability should capture artifact boundaries:

- original intent
- problem brief
- draft workflow
- adversarial review
- implementability review
- final workflow
- approval decision
- execution result
- remediation item

It cannot recover hidden model reasoning. It can identify where a bad assumption first appeared in the durable artifact chain and which gate should have caught it.

### Remediation Work

If a workflow cannot run because prerequisites are missing, the result should be a blocked run plus one or more remediation intents.

Examples:

- Install Playwright and verify browser automation.
- Switch GitHub auth to the expected account.
- Clone the target repo.
- Convert a workflow from implementation to feasibility-only.
- Revise the workflow because its permission profile is too broad.

Remediation intents must not auto-run. They enter the inbox and require user approval or an explicit orchestrator policy.

## V1: Trace Driver And Readiness Gate

V1 should make workflow-factory reliable enough for repeated self-service use.

### Goals

- Enforce run directory shape.
- Validate workflow/item schemas.
- Verify prerequisites before runner launch.
- Capture telemetry and trace events.
- Fail closed when required capabilities are missing.
- Create remediation intents for blocked runs.
- Preserve prompt/output hashes and artifact indexes.

### Proposed Commands

```text
workflow-factory init-project --project <project>
workflow-factory init-run --project <project> --intent <intent-id>
workflow-factory preflight --run <run-dir>
workflow-factory run-stage --run <run-dir> --stage <stage-name> --runner <runner-name>
workflow-factory trace --run <run-dir> --event-type <type> --input <path> --output <path>
workflow-factory telemetry --run <run-dir> --status <status>
workflow-factory index --run <run-dir> --artifact <path> --created-by <role> --prompt <path>
workflow-factory reject --run <run-dir> --artifact <path> --reason <text>
workflow-factory remediate --run <run-dir> --reason <text>
workflow-factory validate-run <run-dir>
```

### V1 Acceptance Criteria

- A workflow cannot start until required prerequisites pass or are explicitly waived.
- A workflow cannot finalize without required trace events.
- A blocked run writes a blocker artifact and at least one remediation recommendation when appropriate.
- Time and token usage are captured when reported by the runner.
- Project state can show active, blocked, completed, and remediation-needed work.
- A fresh agent can resume from files without chat memory.

## V2: Orchestrator

V2 should coordinate workflow execution across agents and providers.

### Goals

- Provider adapters for Codex, Claude Code, Claude `-p`, and future runners.
- Harness detection and explicit runner config.
- Single-run locking or task claiming.
- Stage state machine with approval gates.
- Budget-aware scheduling using token/time telemetry.
- GitHub issue mirroring for approved workflows.
- Factory-feedback issue candidates for `agent-toolkit`.
- Optional execution of approved implementation workflows.

### V2 Acceptance Criteria

- The orchestrator can move an approved intent through clarification, workflow drafting, review, finalization, and child-intent extraction.
- The orchestrator can refuse to run implementation until feasibility passes.
- Token/time budgets can stop or defer work before runaway usage.
- Missing prerequisites create remediation intents rather than failed one-off chats.
- GitHub issues mirror important approved work without becoming canonical state.

## Deferred

- Dashboard UI.
- Automatic priority ranking across all projects.
- Automatic GitHub issue creation without user review.
- Automatic execution of remediation work.
- Full PM app behavior.

## Open Design Questions

- Should token/time budgets be hard caps, soft warnings, or both?
- Should prerequisite waivers require a user decision artifact?
- Should permissions be declared by workflow, runner, or both?
- How should provider-reported token usage be normalized across Codex and Claude?
- Should remediation intents be generated from a fixed template or inferred by the model and reviewed?
