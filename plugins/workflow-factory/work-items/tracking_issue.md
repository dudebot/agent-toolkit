# Tracking Issue Draft

Title: Evolve workflow-factory from skill package to traceable readiness-gated orchestrator

Issue: https://github.com/dudebot/agent-toolkit/issues/2

Labels:

- workflow
- skills
- orchestration
- roadmap

## Body

`workflow-factory` v0 exists as an installable skill package. The next step is to evolve it into a readiness-gated workflow system with traceability, telemetry, prerequisite validation, permission profiles, and remediation loops.

### Problem

The skill can create durable workflow artifacts, but the important guarantees are still prompt-enforced:

- required prerequisites can be missing until after a workflow launches
- permission needs are described, not enforced
- trace events can be forgotten or malformed
- token/time usage is not captured consistently
- blocked runs do not yet create structured remediation work
- V1/V2 planning is split across local markdown files instead of one visible tracking surface

### Goal

Create a V1 trace driver and V2 orchestrator path that supports:

- workflow readiness checks before runner launch
- machine-checkable capability prerequisites
- permission profiles
- telemetry for token/time/resource usage
- durable trace events and artifact indexes
- blocked-run artifacts
- remediation intent generation
- provider/harness adapters
- approval gates
- optional GitHub issue mirroring for approved workflows

### Non-Goals

- No dashboard or full PM SaaS.
- No automatic execution of newly created workflows or remediation work.
- No private project details in public examples.
- No automatic GitHub issue creation without review.
- No requirement that GitHub issues become canonical state; file artifacts remain canonical.

### Deliverables Already Done

- `plugins/workflow-factory/.claude-plugin/plugin.json`
- `plugins/workflow-factory/.codex-plugin/plugin.json`
- `plugins/workflow-factory/README.md`
- `plugins/workflow-factory/skills/workflow-factory/SKILL.md`
- role prompts under `plugins/workflow-factory/prompts/`
- schemas under `plugins/workflow-factory/schemas/`
- templates under `plugins/workflow-factory/templates/`
- marketplace entry in `.claude-plugin/marketplace.json`
- GitHub-backed install verified for Codex and Claude

### V1 Deliverables

- Consolidated roadmap: `plugins/workflow-factory/work-items/ROADMAP.md`
- Trace driver CLI/script. Initial thin driver exists at `plugins/workflow-factory/scripts/workflow_factory.py`.
- Run directory initializer.
- Capability prerequisite checks for commands, paths, env vars, add-dir paths, and writable paths.
- Permission profile schema and validator.
- Telemetry metadata capture for wall time and token usage when available.
- Blocked-run artifact format.
- Remediation intent template and generator.
- `validate-run` command that fails when required trace, telemetry, or readiness records are missing.

### V2 Deliverables

- Runner adapters for Codex, Claude Code, Claude `-p`, and future compatible runners.
- Stage state machine for intake, clarify, draft, review, finalize, child-intent extraction, and trace audit.
- Single-run locking/task claiming.
- Budget-aware scheduling using token/time telemetry.
- GitHub issue mirroring for approved workflows after user review.
- Factory-feedback issue candidates for `agent-toolkit`.

### Capability Prerequisites

Workflows should declare prerequisites such as:

- correct GitHub account/auth
- repo cloned and current
- repo read/write expectations
- browser/Playwright availability
- login/session availability
- network access
- credentials/API keys
- sandbox mode
- source artifacts present

### Acceptance Criteria

- A workflow cannot launch until required prerequisites pass or are explicitly waived.
- A workflow cannot finalize without required trace events.
- Permission mismatches block execution and produce a durable blocker artifact.
- Token/time usage is captured when available and recorded as unknown when unavailable.
- Missing prerequisites create remediation recommendations instead of failed one-off chats.
- Remediation work enters an inbox and does not auto-run.
- A fresh agent/session can continue from the files alone.
