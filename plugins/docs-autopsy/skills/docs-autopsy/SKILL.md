---
name: docs-autopsy
description: Use when a repo's documentation has accumulated across sprints and nobody trusts it — stale references, superseded plans, missing coverage. Triggers on "audit the docs", "are the docs still accurate", "clean up docs/", "docs overhaul". Produces a per-file verdict table verified against the code, an archive plan with provenance, and a coverage-gap list; then executes it.
---

# docs-autopsy

An evidence-based audit of a repo's documentation: every doc gets a verdict, every
verdict gets verified against the code (the body), and the outcome is a smaller doc
set a newcomer can actually trust. Completes the hygiene trilogy with
`comment-hygiene` (comments) and `seam-machine` (architecture) — compose freely.

The failure mode this exists for: docs are written during the sprint that needed
them and never revisited. The reference doc drifts, the design docs for the road
not taken stay filed as if current, and the newest shipped feature has no doc at
all. The set as a whole becomes sediment — and the reader can't tell which layer
they're standing on.

## Verdicts — every file gets exactly one

- **CURRENT** — accurate now; spot-checked against code, not assumed.
- **STALE** — right shape, wrong facts (drifted references, renamed files, dead
  line numbers). Fix in place.
- **SUPERSEDED** — describes a plan or design the project since leapfrogged.
  Stamp and archive.
- **HISTORICAL-keep** — honest design history, already labeled as such. Archive
  (or leave if already in an archive).
- **DELETE-candidate** — one-off artifacts with no provenance value: raw prompt/
  response dumps, temporary analyses consumed by implementation, delivery/status
  reports for long-merged features, coordination docs from finished parallel work.
  Git history is the backup; still prefer archive over delete when unsure.

## The heuristics that find the bodies

1. **Authority-claiming docs get audited first and hardest.** The most dangerous
   doc is the one whose title or framing claims to be the reference ("as-built",
   "architecture", "current state", the README). A stale roadmap misleads nobody;
   a stale reference is trusted precisely because of its title. Verify every
   checkable claim in these: named files exist, named functions/classes exist,
   counted things (tests, modules, endpoints) count correctly, linked docs exist.
2. **The unclosed time capsule.** Look for an entire design conversation for a
   direction that was later leapfrogged — proposals, validations, roadmaps, Q&A
   dumps that all cite since-deleted code. They travel as a set; archive them as
   a set. Telltale: a cleanup plan that was itself never executed.
3. **Drift check by timestamp.** For each doc: when was it last meaningfully
   modified (`git log --follow`), and has the code it describes changed since
   (`git log --since=<that date> -- <covered paths>`)? Filter noise: doc-only,
   formatter, and merge commits don't count as drift; `feat:`/`fix:`/`refactor:`
   commits touching covered code do.
4. **Coverage gaps run in the opposite direction.** List shipped user-facing
   features and controls (CLI flags, keybindings, daemons, config surfaces) and
   ask which have no doc at all. Safety- and recovery-relevant features get
   priority — the escape hatch nobody documented is the worst gap.
5. **Merged-feature residue.** For delivery/plan docs, check whether the feature
   shipped (`git log --all --grep=<name>`, does the code exist?). Shipped and
   merged ⇒ the coordination paperwork is residue.

## Process

1. **Inventory.** List every doc (don't forget the README and any agent-context
   files like CLAUDE.md/AGENTS.md — they're docs too and they're authority-class).
   Note sizes and last-modified dates.
2. **Verdict table.** Read each file; verify claims against code *before* writing
   any verdict — grep for the named symbols, count the counted things. Output:
   file, one-line purpose, verdict, why (with the contradicting code location for
   STALE calls).
3. **Plan, then execute:**
   - **Fix** STALE docs in place. Prefer function/symbol-name references over
     bare line numbers in the rewrite — names don't rot, line numbers do.
   - **Archive** SUPERSEDED/HISTORICAL sets to `docs/archive/` with (a) a short
     archive README stating what this material is, why it's frozen, and that it
     cites since-deleted code — provenance, not reference; (b) a one-line
     SUPERSEDED stamp atop any file not already honestly labeled. Use `git mv`.
   - **Repoint** every cross-reference to moved files (grep each filename).
   - **Write** the missing docs found by the coverage-gap sweep — short and
     user-facing; a controls/how-to page beats a wiki tome.
4. **Report.** The verdict table, what moved/changed/was written, and any claims
   you could not verify (label them as unverified rather than guessing).

## Advanced rung: coverage contracts

If the repo (or the owner) wants recurring audits instead of one-off autopsies,
add frontmatter contracts to living docs — `covers:` (globs of the code this doc
describes) and `last_verified:` (date) — and script the drift check: a doc is a
drift candidate when N+ non-noise commits touched its covered files since
`last_verified`; code no doc covers is an orphan; two docs covering one file is
an overlap to adjudicate. Only bump `last_verified` after actually re-verifying.
Don't build this rung unless asked — a one-off autopsy doesn't need it.

## Rules

- Verify before you flag: every STALE/factual-error claim needs the code location
  that contradicts it. An audit that guesses is itself a stale doc.
- Archive over delete when unsure; git keeps deletions, but an archive with a
  provenance README keeps the *context*.
- Never update the archived files' contents beyond the stamp — they're frozen.
- Normative specs the project still builds against are CURRENT even when old;
  age is not staleness.
- If the repo has a documented non-goal or invariant, docs restating it are
  signal, not redundancy.
