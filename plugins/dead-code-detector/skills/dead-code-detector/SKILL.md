---
name: dead-code-detector
description: Use when the user wants to find code that can be safely deleted — unused files, exports, functions, types, abandoned experiments. Triggers on "find dead code", "is anything unused", "what can we delete", post-refactor orphan hunts, pre-release cleanup. Detects and reports with confidence tiers and evidence; deletes nothing without explicit instruction.
---

# dead-code-detector

Systematically identify dead code with stated confidence and shown evidence.
**Detection and reporting only** — never delete without the user explicitly asking
for the cleanup. The prime directive: it is better to miss dead code than to
report live code as dead. Below 80% confidence, mark NEEDS-REVIEW or don't report.

## Strategy order

### 1. Ecosystem tools first (highest confidence, cheapest)

Run the language's dead-code tool before any manual analysis; treat its output as
candidates to verify, not verdicts:

| Ecosystem | Tools |
|---|---|
| TypeScript/JS | `knip` (most comprehensive: files, exports, deps, types), `ts-prune` (unused exports), `unimported` (unused files) |
| Python | `vulture`, `dead` |
| Rust | `cargo machete` / `cargo udeps` (deps), `#[warn(dead_code)]` output |
| Go | `deadcode` (golang.org/x/tools), `staticcheck -checks U1000` |
| C/C++ | linker `--gc-sections --print-gc-sections`, `cppcheck --enable=unusedFunction`, compiler `-Wunused` family |
| JVM | ProGuard/R8 shrink report, IntelliJ inspection exports |

If no tool exists or it can't run, fall back to manual analysis (below) — and say
so in the report, since manual-only findings deserve a confidence haircut.

### 2. Reference analysis (manual fallback)

For each candidate file: search the whole codebase for imports/includes of it.
For each export/public symbol in zero-import files: search for the identifier,
excluding its own definition and (counted separately) test files. Zero production
references is the core dead signal.

### 3. Git-history abandonment patterns

The distinctive tell of an **abandoned experiment**: created in a `feat:` commit,
never referenced by any later commit, while a sibling commit (often same day)
adopted the alternative approach that actually shipped. `git log --follow` the
candidate, find its creation context, and check what the surviving call path uses
instead. A file untouched for 6+ months with zero references is a weaker version
of the same signal.

### 4. Entry-point reachability

For whole-directory sweeps: trace from the real entry points (main, server
bootstrap, route tables, CLI binaries, exported package surface) and flag files
in no chain. Cross-check with strategies 1–2 before reporting.

## Confidence tiers — every finding gets one

- **95%+ (safe to delete):** zero imports anywhere; not reachable via barrel/
  re-exports; no dynamic-reference risk; git history shows created-but-never-
  integrated.
- **80–94% (very likely dead):** export defined but never used outside its own
  file; or history shows the alternative approach won.
- **60–79% (needs review):** referenced only from tests or commented-out code;
  or long-untouched with weak reference signals.
- **<60%:** don't report, or list under NEEDS-REVIEW with the specific doubt.

## Edge cases that demote confidence

- **Barrel/re-export files** (`index.*`, `mod.rs`, `__init__.py`): dead only if
  both the barrel and the symbol-via-barrel have zero consumers.
- **Dynamic references**: `import()`/reflection/string-built paths/DI containers/
  plugin registries. Grep for string fragments of the name; if the codebase uses
  dynamic loading at all, cap file-level confidence and say why.
- **Test-only usage**: report as its own category — the code is dead in
  production, but the human decides whether the tests go with it.
- **External consumers**: anything referenced by package manifests (`bin`,
  `exports`, entry_points), published type declarations, config files, docs, CI,
  or downstream repos. Flag NEEDS-REVIEW, never safe-to-delete.
- **Generated and vendored code**: out of scope; note it, don't analyze it.

## Report format

Group by confidence tier, highest first. Per finding: path, reference count and
what was searched, export-level usage counts, git context (created when/why, last
touched), one-line reason, and the recommendation (delete / review / keep). Show
the actual search commands for high-confidence findings so the human can re-run
them. End with totals (files, lines) and anything the scan could NOT rule out
(dynamic loading, external consumers) stated plainly.

## Rules

- Verify tool output with at least one manual spot-check per tier before
  reporting — tools miss dynamic references too.
- Never count a test import as production usage; never silently ignore it either.
- If asked to also delete: highest tier only, one commit, build + tests green
  after; anything below 95% stays a recommendation.
- When the same sweep keeps finding abandoned experiments, say so — that's a
  process observation the owner may care about more than the line count.
