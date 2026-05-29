# Factory Feedback Prompt

You are using workflow-factory and have found a defect, ambiguity, missing guardrail, or bad instruction in the factory itself.

Your job is to create a reviewable upstream feedback artifact for `agent-toolkit`. Do not open a GitHub issue unless the user explicitly asks.

## When To Use

Use this when:

- workflow-factory instructions conflict.
- a required artifact shape is missing or impossible.
- traceability cannot be maintained with the current templates.
- a prompt encourages premature execution, over-automation, or hidden approval.
- the factory cannot represent a real workflow edge case.
- a generated workflow fails because the factory gave bad meta-direction.

## Output

Write a file under the current run:

- `factory_feedback/<id>.md`

The file must include:

1. Summary
2. Severity
   - critical, high, medium, low
3. Affected Factory Artifact
   - prompt, schema, template, skill instruction, marketplace config, or docs
4. Reproduction Context
   - what user intent or workflow exposed the problem
5. Expected Behavior
6. Actual Behavior
7. Why The Existing Review Gates Missed It
8. Proposed Fix
9. Should This Become An `agent-toolkit` Issue?
   - yes, no, or needs user decision
10. Trace Event

## Rules

- Do not silently patch the factory from inside an unrelated project unless the user asked for that.
- Do not create noisy low-confidence issue drafts. If uncertain, write one consolidated feedback item.
- If the defect can cause data loss, privacy leakage, or premature execution, mark it high or critical.
- Feedback artifacts are inbox items until the user approves upstream work.
