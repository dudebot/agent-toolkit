# Work Item Review: workflow-factory Self Adversarial Review

## Verdict

Ready for a manual POC with fixes. The factory is useful enough to install in a control repo and run against one real intent, but it should not be treated as a mature orchestrator yet.

## Scope Reviewed

- `workflow-factory` skill instructions
- portfolio intake prompt
- traceability auditor prompt
- schemas/templates
- Codex and Claude marketplace install surface
- intended Greasyfork/Grok TTS feasibility scenario

## Findings

### High: Traceability is prompt-enforced, not system-enforced

The trace ledger requirement is correct, but an LLM can forget or inconsistently format trace events. This weakens later audits because missing trace records look similar to real absence of evidence.

Recommendation: add a later CLI/driver that creates run folders, appends trace events, validates schemas, and blocks finalization when required trace events are missing. Keep prompt-level traceability for v0, but treat it as advisory until the driver exists.

### High: No upstream factory-feedback path existed

If the installed skill discovers that its own instructions are wrong, it needs a non-spammy way to report that back to `agent-toolkit`. Without this, a target project may silently work around factory defects or create unrelated local mess.

Recommendation: add `factory_feedback/` artifacts and a prompt that creates issue candidates without opening GitHub issues automatically. This review patched that path.

### Medium: Control repo vs target repo needs to stay explicit

The intended use is:

```text
agent-toolkit = reusable skills
dudebot/admin = control repo and intent registry
target repos = implementation work
```

The skill says this indirectly, but a runner could still create project-control state inside the implementation repo.

Recommendation: portfolio intake should default to the current repo only when the current repo is explicitly the control repo. Otherwise it should ask for or infer a control root and write target repo paths as metadata only.

### Medium: Browser/userscript workflows need a specialized feasibility split

The Greasyfork/Grok TTS scenario is not one workflow item if quality matters. It has at least two gates:

1. Feasibility: inspect live Grok page behavior, session/login constraints, DOM/media hooks, CSP/userscript limits, and whether Playwright observations can translate to a userscript.
2. Implementation: build and validate a userscript using a browser harness, without manual copy-paste into Greasyfork UI.

Recommendation: factory should split browser automation/userscript intents by default when the site is dynamic, authenticated, or media-heavy.

### Medium: Child intents can explode

Portfolio intake can create too many low-confidence child intents from stale issues. The prompt has a guardrail, but no hard limit or consolidation rule.

Recommendation: add a default max of 5 inferred intents per repo per pass unless the user asks for exhaustive intake. Extra findings should go into a triage intent.

### Medium: Remote marketplace compatibility is validated locally, not end-to-end

`claude plugin validate` and local Codex install pass. Remote install from GitHub should still be verified after commit/push because marketplace sync can differ from local path resolution.

Recommendation: add a post-merge validation work item: install `workflow-factory` from `dudebot/agent-toolkit` in both Claude and Codex.

### Low: Trace auditor can identify artifact boundaries, not hidden reasoning

The trace auditor cannot reveal the model's hidden chain of thought. It can identify which artifact boundary introduced a bad claim and which review gate missed it.

Recommendation: docs should describe this limitation so users do not expect impossible forensic detail.

## Greasyfork/Grok TTS POC Shape

Use `workflow-factory` in `dudebot/admin`, not in `greasyfork-scripts`, for the intake and workflow artifacts.

Create one explicit intent:

```text
Replicate the existing OpenAI TTS save-on-play UX for Grok as a Greasyfork userscript. First determine feasibility using live-page inspection and a Playwright-style browser harness. Do not require manual copy-paste into Greasyfork UI. Validate that the resulting script works in a userscript environment before implementation is accepted.
```

Expected split:

1. `grok-tts-userscript-feasibility`
2. `grok-tts-userscript-implementation`

The implementation intent should remain blocked until feasibility passes.

## Required Follow-Up Work

1. Add factory-feedback prompt/schema/template.
2. Add a V2 trace-driver CLI work item.
3. Tighten control-repo vs target-repo wording.
4. Add inferred-intent cap for portfolio intake.
5. After commit/push, verify remote install from both Claude and Codex.
