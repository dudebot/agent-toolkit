# seam-machine

A skill for evidence-based architecture passes on codebases whose module boundaries
got **greedy** — components that absorbed responsibilities belonging elsewhere, usually
because the code landed before its natural home existed.

## What it detects

God functions and lambda-webs; callback-per-feature accretion; platform/IO/domain code
resident in the wrong layer; the same invariant hand-enforced at 3+ call sites;
duplicated name tables; mutable file-scope globals; TU-local types other components
can only reach through closures; one-class-many-jobs.

## How it works — three gates

0. **Integration pressure check** (write-time): before wiring a new feature into an
   existing module, prove the attachment point is natural ownership — not just the
   cheapest place the current code can reach. An integration that deepens a greed
   signal stops and proposes the smallest ownership move first; a deliberate bolt-on
   is acceptable only with the increased coupling count named on the record.
1. **Diagnose**: inventory → full reads of the suspects → falsifiable claims with
   file:line evidence → **adversarial verification** by an independent reviewer with
   forced verdicts (`REAL-AND-WORTH-FIXING / REAL-BUT-LEAVE-IT / OVERBLOWN`) plus a
   "name the seams I missed" prompt → scoreboard ranked by future tax.
2. **Extract**: cheapest-and-most-independent first, one seam per behavior-preserving
   commit, tests green at every rung, and every commit must reduce a coupling count
   you can name. Bug fixes ride in their own commits, never inside a move. The ladder
   stops where a product decision or a genuine redesign begins.

Move code, don't invent abstractions. Respect documented non-goals. Verify recon
against source before it drives an edit.

## Install

```
/plugin install seam-machine@agent-toolkit
```
