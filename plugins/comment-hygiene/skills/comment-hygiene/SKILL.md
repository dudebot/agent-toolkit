---
name: comment-hygiene
description: Use when a codebase's inline comments have accumulated process residue — issue numbers, review provenance, sprint narration, edit-history war stories — and the user wants them cleaned without losing real invariants. Triggers on "de-dust the comments", "clean up comments", "comment hygiene", "the comments are narrating decisions". Produces a categorized findings list first, then applies it as a behavior-neutral pass.
---

# comment-hygiene

Rewrite source-code comments so they explain durable intent, invariants, constraints,
surprising behavior, and public contracts. Remove or rewrite comments that narrate the
edit history, cite the development process, hedge, apologize, describe obvious code, or
preserve stale implementation archaeology.

The failure mode this skill exists for: iterative (especially AI-assisted) development
leaves comments addressed to the *reviewer of that day's diff* — not to the next reader
of the code. Ticket tokens, "per the audit", "this sprint", "the old version did X".
Each one was reasonable in its PR; collectively they force every future reader to
mentally strip provenance noise off every real invariant.

## Categories — triage every finding into exactly one

- **D — stale and now WRONG.** The comment describes behavior that no longer exists or
  points at the wrong module. Highest priority: a wrong comment is worse than no
  comment. Verify against the code before rewriting — the code, not the comment, is
  ground truth.
- **A — pure narration.** Process residue carrying no information a future reader
  needs: ticket/issue tokens, review provenance ("audit finding", reviewer names),
  sprint/wave/scope language ("this wave", "out of scope", "not an owned file"),
  dated batch labels, replaced-workflow stories. Delete.
- **B — narration wrapping a real constraint.** A genuine invariant or platform gotcha
  buried in process story or past-tense war story ("the original version deadlocked
  here because..."). Rewrite in present tense, keeping only the durable content, and
  write the replacement text in the findings list before touching the file.
- **C — good.** Explains *why*, states a contract, or documents a trap. Keep verbatim.

## What to preserve (never delete these)

- Why the code exists; why the simpler approach is wrong.
- Threading contracts, lock ordering, lifetime/ownership rules.
- Compatibility constraints, security assumptions, performance constraints.
- Data-shape invariants and external API / platform quirks (these are usually the most
  expensive comments to re-learn).
- Cross-references to docs **by filename** ("see docs/wire-format.md §3") — these stay;
  only bare ticket tokens ("(#42)", "JIRA-1234") go.
- TODOs — but strip the process wrapper. `TODO(handoff, sprint 3, not an owned file):`
  becomes `TODO:` plus the actual gap.
- License headers, and anything in vendored/third-party code (out of scope entirely).

## Narration tells (grep fodder)

Issue tokens `(#\d+)` / `[A-Z]+-\d+`; "audit finding", "review finding", model or
reviewer names; "this wave/sprint/phase", "out of scope", "owned file", "handoff";
"shipped blind", "war story" tense ("used to", "the old X did", "previously");
dated batch labels; "replaces the old workflow of...". A hit is a candidate, not a
verdict — some matches sit inside Category B comments whose constraint must survive.

## Process

1. **Sweep.** Grep the tells, then *read the comment-dense files in full* — the worst
   narration is prose, not tokens. Skip vendored dirs and generated code.
2. **Findings list first.** Produce the categorized list — file:line, verbatim excerpt,
   category, and for B/D the exact replacement text. This list is the reviewable
   artifact; on large codebases present it before applying.
3. **Apply.** Comments only — zero runtime-behavior change. (Help strings / user-facing
   literals only if the user agreed.) Verify each site by reading it; line numbers
   drift.
4. **Verify.** Build and tests must pass identically. A comment pass that breaks the
   build edited more than comments.
5. **Report.** Summarize the classes removed/reworded, and separately flag any comment
   that indicates *actual technical debt* (a documented workaround whose root cause is
   now fixable, an "untested on platform X" that could now be tested). Those are
   follow-up work items, not comment problems — never silently delete them.

## Rules

- Prefer short comments adjacent to the non-obvious code over banner essays.
- Rewrite "we added/changed this because..." into present-tense design rationale when
  the rationale still holds; delete it when its only value is git history.
- When a comment says the code is wrong and the code says the comment is wrong, run or
  trace the code before picking a side.
- Do not remove a hedge that encodes real uncertainty ("untested on X") — that is a
  constraint, not an apology. Strip only the story around it.
