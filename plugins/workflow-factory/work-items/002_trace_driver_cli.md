# Work Item: Workflow Factory Trace Driver / V1 Orchestrator

## Status

Future V1/V2 work item.

See `ROADMAP.md` for the consolidated roadmap. This file captures the first implementation slice.

## Problem

The workflow factory currently asks the model to create `trace_ledger.jsonl`, `artifact_index.md`, and rejection records. That is useful but not reliable enough for strong traceability. A model can forget a trace event, misformat JSONL, or finalize a workflow despite missing trace records.

## Goal

Build a small CLI or script that enforces the workflow-factory trace contract. This should start as a trace driver, then grow into the V1 workflow-factory orchestrator that can move an intent through intake, review, finalization, and child-intent capture without requiring manual copy/paste between stages.

The first implementation slice should focus on:

- run creation
- prerequisite validation
- trace event validation
- telemetry capture
- blocked-run artifacts
- remediation intent creation

## V1 Wishlist

The V1 orchestrator should include:

- Project/control-repo initialization for the `projects/<project>/` layout.
- Provider/harness adapters for Codex CLI, Claude Code, and future compatible runners.
- Harness detection and explicit runner configuration.
- Stage execution for intake clarification, workflow architecture, adversarial review, implementability review, finalization, child-intent extraction, and trace audit.
- A small state machine so stages cannot run out of order.
- Human approval gates for accept, reject, reject-with-changes, defer, or merge-with-existing.
- Capability prerequisite declarations and preflight checks before runner launch.
- Permission profile checks for read/write, multi-repo, browser, network, and full-access workflows.
- Schema validation for intents, workflows, reviews, child intents, trace events, and factory feedback.
- Run directory creation with prompt, stdout/stderr, final response, artifact index, and trace ledger capture.
- Telemetry capture for elapsed time, token usage when available, retries, approval/escalation count, and final status.
- Prompt/output hashing so a rejected or bad artifact can be traced back to the exact prompt and inputs that produced it.
- Single-run locking or task claiming so two orchestrators do not race the same intent.
- Remediation-intent creation when prerequisites are missing or a workflow needs revision before it can run.
- GitHub issue mirroring for approved workflows, while keeping file artifacts as canonical state.
- Factory-feedback capture when an installed skill appears underspecified, contradictory, or misleading.
- No automatic issue spam: factory-feedback artifacts should be reviewable before issue creation.
- Provider logs redacted or explicitly marked sensitive.
- A validation command that fails if required artifacts or trace events are missing.

## Deferred Beyond V1

- Dashboard UI.
- Automatic priority ranking across all projects.
- Automatic GitHub issue creation without review.
- Full execution of implementation workflows in target repos.
- Cross-provider model selection heuristics beyond explicit runner configuration.

## Proposed Commands

```text
workflow-factory init-run --project <project> --intent <intent-id>
workflow-factory preflight --run <run-dir>
workflow-factory run-stage --run <run-dir> --stage <stage-name> --runner <runner-name>
workflow-factory trace --event-type <type> --input <path> --output <path>
workflow-factory telemetry --run <run-dir> --status <status>
workflow-factory index --artifact <path> --created-by <role> --prompt <path>
workflow-factory reject --artifact <path> --reason <text>
workflow-factory remediate --run <run-dir> --reason <text>
workflow-factory feedback --run <run-dir> --reason <text>
workflow-factory validate-run <run-dir>
```

## Responsibilities

- Create run directory shape.
- Append valid trace events.
- Validate `trace_ledger.jsonl` against `trace_event.schema.yaml`.
- Validate declared prerequisites before runner launch.
- Validate permission profile against runner/sandbox configuration before runner launch.
- Ensure required event types exist before finalization.
- Capture token/time telemetry where the runner exposes it.
- Update `artifact_index.md`.
- Create rejection records.
- Create blocked-run and remediation artifacts.
- Emit a failure report when trace is incomplete.
- Maintain run state and prevent invalid stage transitions.
- Record approval decisions as durable artifacts.
- Optionally mirror approved workflows to GitHub issues after review.

## Non-Goals

- Do not run LLM prompts.
- Do not replace the workflow-factory skill.
- Do not open GitHub issues automatically.
- Do not become a full PM app.

## Acceptance Criteria

- A run cannot be finalized without required trace events.
- A run cannot start when required prerequisites are missing unless a user-approved waiver exists.
- Trace events are valid JSONL.
- Token/time telemetry is captured when available and recorded as unknown when unavailable.
- Artifact index includes every final prompt, workflow draft, review, and child intent.
- Missing prerequisites produce remediation recommendations rather than silent failure.
- Rejections and supersessions are preserved.
- A traceability auditor can reconstruct the artifact chain without chat history.
