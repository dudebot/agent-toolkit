# seam-machine

A skill for evidence-based architecture passes on codebases whose module boundaries
got **greedy** — components that absorbed responsibilities belonging elsewhere, usually
because the code landed before its natural home existed.

## What it detects

God functions and lambda-webs; callback-per-feature accretion; platform/IO/domain code
resident in the wrong layer; the same invariant hand-enforced at 3+ call sites;
duplicated name tables; mutable file-scope globals; TU-local types other components
can only reach through closures; one-class-many-jobs; cyclic imports and
change-coupled modules.

## How it works — two gates

1. **Diagnose**: inventory → full reads of the suspects → falsifiable claims with
   file:line evidence → **adversarial verification** by an independent reviewer with
   forced verdicts (`REAL-AND-WORTH-FIXING / REAL-BUT-LEAVE-IT / OVERBLOWN`) plus a
   "name the seams I missed" prompt, verdicts grounded in an independent read of the
   cited source → scoreboard ranked by future tax, signed off by the user before
   extraction starts.
2. **Extract**: cheapest-and-most-independent first, one seam per behavior-preserving
   commit, tests green at every rung, and every commit must reduce a coupling count
   you can name — net, not shuffled into accessors. Uncovered behavior gets pinned
   with characterization tests before it moves. Bug fixes ride in their own commits,
   never inside a move. The ladder stops where a product decision or a genuine
   redesign begins.

Move code, don't invent abstractions. Respect documented non-goals. Verify recon
against source before it drives an edit.

## Install

```
/plugin install seam-machine@agent-toolkit
```
