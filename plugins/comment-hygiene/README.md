# comment-hygiene

A skill that de-dusts source-code comments after iterative (especially AI-assisted)
development: it strips edit-history narration — ticket tokens, review provenance,
sprint/wave language, "the old version did X" war stories — while preserving every
durable invariant, threading contract, platform gotcha, and design rationale.

## How it works

1. **Sweep** — grep the narration tells, then read comment-dense files in full.
2. **Findings list** — every candidate categorized with file:line and a verdict:
   - **D** stale-and-wrong (fix first; verified against the code),
   - **A** pure narration (delete),
   - **B** narration wrapping a real constraint (present-tense rewrite, replacement
     text written up front),
   - **C** good (keep).
3. **Apply** — comments only, zero runtime-behavior change; build and tests must pass
   identically.
4. **Report** — classes removed/reworded, plus flags for comments that indicate real
   technical debt (those become follow-up work, never silent deletions).

## Install

```
/plugin install comment-hygiene@agent-toolkit
```
