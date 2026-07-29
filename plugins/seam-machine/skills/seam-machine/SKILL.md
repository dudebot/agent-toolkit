---
name: seam-machine
description: Use when a codebase's module boundaries feel wrong — god functions, callback bags, layers absorbing work that belongs elsewhere — and the user wants an evidence-based architecture pass. Also use before wiring a new feature into an existing module, to check the attachment point is natural ownership rather than the cheapest reachable place. Triggers on "the seams feel greedy", "architecture review", "god function", "this module does too much", "extract this cleanly", "where should this feature live", "add/integrate/wire this into <existing module>", "bolt this on". Finds greedy seams, adversarially verifies each claim, then executes extractions cheapest-first as behavior-preserving commits.
---

# seam-machine

A **seam** is a module boundary. A **greedy seam** is one that absorbed responsibilities
that belong elsewhere — almost always because code landed before its natural home
existed, and each later feature found it cheaper to bolt on than to move out. Greedy
seams are how a codebase gets a 400-line function nobody can test and a constructor
with six callbacks.

This skill has one write-time gate and two cleanup gates: **integration pressure
check** (before new code lands in an existing module), then **diagnose** (claims →
adversarial verification → scoreboard) and **extract** (cheapest-first, one seam per
commit). Never skip the verification gate — plausible-but-wrong seam claims produce
refactors that shuffle code without reducing coupling.

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

The examples use C++ vocabulary; the signals are language-agnostic — read
`std::function` as closure-per-feature, translation unit as module-private,
#include count as import count.

## Gate 0 — integration pressure check

Fires at write-time, not cleanup-time: before wiring a new feature into an existing
module. Greedy seams are *made* at integration, one cheap attachment at a time —
this gate is where the accretion stops. Answer in writing, before the first edit:

1. What responsibility is being added?
2. Which existing type/module already owns that responsibility?
3. Does the change add another callback, flag, mutable global, catalog entry, or
   cross-layer import — i.e., deepen a greed signal from the list above?
4. Is the chosen attachment point natural ownership, or just the cheapest place the
   current code can reach?
5. If bolting on anyway is the right call today, name the coupling count it increases
   and where the code should move later.

If the integration deepens any greed signal from the list, the default is to stop
and propose the smallest ownership move first — then wire the feature through the
corrected boundary. A deliberate bolt-on is a user decision, not an agent shortcut:
surface the tradeoff, and record question 5's answer on the owner list so the debt
has a home. The tell in practice: another lambda closing into the main loop is the
cheap attachment; a method on the type that owns that state is the natural one —
the gate exists to pick the second.

## Gate 1 — diagnose

1. **Inventory.** File sizes, include/import graph, longest functions, grep for
   file-scope mutable state. The biggest recently-grown files are the prime suspects.
2. **Read the suspects in full.** Skimming finds style; only full reads find seams.
3. **Write claims as falsifiable statements**: the seam, the evidence (file:line), the
   specific extraction, and its blast radius (call sites touched). One claim per seam.
4. **Adversarial verification.** Hand the claims to an independent reviewer — a second
   model, a fresh agent, or a cold session — with *forced verdicts*:
   `REAL-AND-WORTH-FIXING / REAL-BUT-LEAVE-IT / OVERBLOWN`, per sub-item, plus "name
   up to 3 greedy seams NOT in this list, with file:line evidence." The missed-seams
   question routinely earns its cost.
5. **Scoreboard.** Verdicts, one line each, ranked by future tax. Items needing a
   product decision (delete vs. fix a dying subsystem) go to a separate owner list —
   they are not extraction work.

## Gate 2 — extract

Order by **(cost × independence)**: cheapest, least-entangled first. For each rung:

- One seam per commit, behavior-preserving. Never bundle a behavior change or bug fix
  into a move commit — if the move exposes a bug, fix it in its own commit.
- Build and full test suite green before and after every rung.
- The commit must *reduce a coupling count* you can name (callbacks removed, call sites
  deduplicated, globals eliminated, #includes dropped). A move that relocates code
  without shrinking any count is churn — skip it.
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
