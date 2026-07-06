# dead-code-detector

Find code that can be safely deleted — unused files, exports, functions, types,
and abandoned experiments — and report it with stated confidence and shown
evidence. Detection only: it deletes nothing unless explicitly asked to.

## Method

1. **Ecosystem tools first** (knip / ts-prune / vulture / cargo machete /
   deadcode / cppcheck, per language), treated as candidates to verify.
2. **Reference analysis** — zero production imports/uses is the core signal;
   test-only usage is its own category.
3. **Git-history abandonment patterns** — the distinctive tell: created in a
   `feat:` commit, never referenced since, while a sibling commit adopted the
   approach that actually shipped.
4. **Entry-point reachability** for whole-directory sweeps.

Findings are tiered (95%+ / 80–94 / 60–79 / needs-review) with the edge cases
that demote confidence handled explicitly: barrel re-exports, dynamic references,
external consumers, generated/vendored code. Prime directive: better to miss dead
code than to report live code as dead.

## Install

```
/plugin install dead-code-detector@agent-toolkit
```
