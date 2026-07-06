# docs-autopsy

An evidence-based audit of a repo's documentation — every doc gets a verdict
(CURRENT / STALE / SUPERSEDED / HISTORICAL-keep / DELETE-candidate), every verdict
gets verified against the code before it's written, and the outcome is a doc set a
newcomer can trust. Completes the hygiene trilogy with `comment-hygiene` (comments)
and `seam-machine` (architecture).

## The heuristics

- **Authority-claiming docs get audited hardest** — a stale roadmap misleads
  nobody; a stale "as-built reference" is trusted *because of its title*.
- **The unclosed time capsule** — a whole design conversation for a direction the
  project later leapfrogged, still filed as current. Archived as a set with a
  provenance README, not deleted.
- **Drift by timestamp** — doc last touched vs. code-it-covers changed since,
  with doc-only/formatter/merge commits filtered out as noise.
- **Coverage gaps run the other way** — shipped features with no doc at all;
  safety/recovery features first.

An advanced rung covers recurring audits via frontmatter coverage contracts
(`covers:` globs + `last_verified:` dates) for repos that want drift detection on
a schedule instead of one-off autopsies.

## Install

```
/plugin install docs-autopsy@agent-toolkit
```
