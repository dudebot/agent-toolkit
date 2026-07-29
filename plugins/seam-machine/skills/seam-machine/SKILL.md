---
name: seam-machine
description: Use when a codebase's module boundaries feel wrong — god functions, callback bags, layers absorbing work that belongs elsewhere — and the user wants an evidence-based architecture pass. Triggers on "the seams feel greedy", "architecture review", "god function", "this module does too much", "extract this cleanly". Finds greedy seams, adversarially verifies each claim, then executes extractions cheapest-first as behavior-preserving commits.
---

# seam-machine

A **seam** is a module boundary. A **greedy seam** is one that absorbed responsibilities
that belong elsewhere — almost always because code landed before its natural home
existed, and each later feature found it cheaper to bolt on than to move out. Greedy
seams are how a codebase gets a 400-line function nobody can test and a constructor
with six callbacks.

This skill runs in two gates: **diagnose** (claims → adversarial verification →
scoreboard) and **extract** (cheapest-first, one seam per commit). Never skip the
verification gate — plausible-but-wrong seam claims produce refactors that shuffle
code without reducing coupling.

## Greed signals (the detector list)

1. **God function.** One function owning several unrelated concerns, typically a main
   loop or bootstrap that accreted every feature's wiring. Tell: lambdas closing over
   a web of function-locals — untestable by construction, and every new feature adds
   another closure.
2. **Callback accretion.** A constructor or API growing one callback/std::function per
   feature. Root cause is usually signal 7: the state those callbacks reach lives in a
   type with no public home.
3. **Wrong-layer residency.** Platform, IO, or domain code living in a module named for
   a different concern (window management in the renderer, disk IO in the UI). Often
   predates the directory where it belongs — check whether that home exists *now*.
4. **Scattered invariant.** The same rule enforced by hand at 3+ call sites. Each new
   caller is a chance to forget the copy; the fix is one named policy function, not a
   hidden auto-reconcile that obscures per-site intent.
5. **Duplicated catalog.** The same name table / enum mapping / feature list maintained
   in multiple files. Every rename is multi-file drift risk.
6. **Mutable file-scope globals** serving a single feature — state that wants to be a
   member of something.
7. **Local type others need.** A type private to one translation unit that other
   components can only reach through closures or accessors. Promote the type; the
   indirection dissolves.
8. **One class, many jobs.** Selection + caching + IO + policy in one class. Rank by
   what it *blocks* (live reload, testing) rather than aesthetics.
9. **Cyclic or bidirectional dependency.** Two modules importing each other, or a
   lower layer reaching up for a higher-layer type to finish one feature. Tell:
   mutual imports, friend/backchannel access.

The examples use C++ vocabulary; the signals are language-agnostic — read
`std::function` as closure-per-feature, translation unit as module-private,
#include count as import count.

## Gate 1 — diagnose

1. **Inventory.** File sizes, include/import graph, longest functions, grep for
   file-scope mutable state, and git log for change coupling — supposedly separate
   modules that keep landing in the same commits. The biggest recently-grown files
   are the prime suspects.
2. **Read the suspects in full.** Skimming finds style; only full reads find seams.
3. **Write claims as falsifiable statements**: the seam, the evidence (file:line), the
   specific extraction, and its blast radius (call sites touched). One claim per seam.
4. **Adversarial verification.** Hand the claims to an independent reviewer — a second
   model, a fresh agent, or a cold session — with *forced verdicts*:
   `REAL-AND-WORTH-FIXING / REAL-BUT-LEAVE-IT / OVERBLOWN`, per sub-item, plus "name
   up to 3 greedy seams NOT in this list, with file:line evidence." The missed-seams
   question routinely earns its cost. The reviewer must read each claim's cited
   source before issuing a verdict and state the strongest counterevidence they
   found — forced labels without an independent read are rubber-stamping.
5. **Scoreboard.** Verdicts, one line each, ranked by future tax. Items needing a
   product decision (delete vs. fix a dying subsystem) go to a separate owner list —
   they are not extraction work. Present the scoreboard and get the user's sign-off
   on the rung order before extracting, unless they already authorized the full pass.

## Gate 2 — extract

Order by **(cost × independence)**: cheapest, least-entangled first. For each rung:

- One seam per commit, behavior-preserving. Never bundle a behavior change or bug fix
  into a move commit — if the move exposes a bug, fix it in its own commit.
- Build and full test suite green before and after every rung. Green only protects
  covered behavior — check the code being moved is actually exercised; if it isn't,
  first pin current behavior with characterization tests in their own commit.
- The commit must *reduce a coupling count* you can name (callbacks removed, call sites
  deduplicated, globals eliminated, #includes dropped). The reduction must be net:
  removing three callbacks by adding four accessors is an increase wearing a
  decrease's clothes. A move that relocates code without shrinking any count is
  churn — skip it.
- Stop the ladder when the next rung needs a product decision or a redesign
  (an "extraction" touching dozens of call sites is a redesign wearing a refactor's
  clothes — park it on the owner list).

## Rules

- **Move code, don't invent abstractions.** No new interface/base class unless two real
  implementations exist today. Extraction ≠ abstraction.
- **Respect decided non-goals.** A seam that looks greedy may be load-bearing by
  design — check the project's stated invariants before flagging (a two-slot cache is
  not a missing N-slot cache if N>2 is a documented non-goal).
- **Recon is not ground truth.** Verify any claim (yours or the reviewer's) against
  source before it drives an edit.
- Preserve existing names and schemas across the move; renaming during extraction
  doubles the diff and hides the structure change.
