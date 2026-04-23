# quota-watch

An adaptive Claude Max quota monitor that runs as a `UserPromptSubmit` hook. Every time you submit a prompt, it checks your 5-hour and 7-day utilization against the Anthropic OAuth usage endpoint, and:

- **ok**: stays silent — no context injected, no noise
- **warn** (default ≥85% 5h): prints a one-line "wind down" notice that the model will see as context for the turn
- **halt** (default ≥97% 5h, or projected to cross within 5 minutes): prints a halt directive and a `ScheduleWakeup(delaySeconds=N)` instruction so the model parks itself until after the reset

## How it stays cheap

The endpoint is polled with an **adaptive cache TTL** based on current utilization:

| 5h utilization | cache TTL | max endpoint calls/hour |
| --- | --- | --- |
| < 30% | 15 min | 4 |
| 30–70% | 5 min | 12 |
| 70–90% | 2 min | 30 |
| ≥ 90% | 1 min | 60 |

Rapid-fire prompts during low utilization will typically hit cache; the endpoint is only called when the cached view expires or the 5h window rolls over.

## Install

Via this marketplace:

```
/plugin marketplace add dudebot/agent-toolkit
/plugin install quota-watch@agent-toolkit
```

## Configuration

Environment variables (all optional):

| Variable | Default | Purpose |
| --- | --- | --- |
| `CLAUDE_HOME` | `$HOME/.claude` | Where the OAuth credentials live (`$CLAUDE_HOME/.credentials.json`) |
| `QUOTA_CACHE` | `$TMPDIR/claude-usage.json` | Cached API response |
| `QUOTA_HISTORY` | `$CLAUDE_HOME/cache/usage-history.jsonl` | Sample history for slope projection |
| `QUOTA_WARN_PCT` | `85` | Utilization % to warn at |
| `QUOTA_HALT_PCT` | `97` | Utilization % to halt at |
| `QUOTA_HALT_HEADROOM_MIN` | `5` | Project-to-100 headroom in minutes that also triggers halt |

## CLI usage

The script also works standalone for humans:

```
quota-check.sh                 # silent when ok; one line when warn/halt
quota-check.sh --always-print  # print even when ok
quota-check.sh --json          # full state as JSON
quota-check.sh --verdict       # just: ok | warn | halt
quota-check.sh --force         # bypass cache TTL
```

## Verifying installation

The hook only produces visible output when you're near quota, which is exactly when you don't want to be debugging it. To smoke-test without waiting:

1. Run `quota-check.sh --always-print` — if you see a `quota ok: ...` line, credentials and endpoint are reachable.
2. Run `quota-check.sh --json` to inspect the full state (util, slope, headroom, next reset).

If either of those works, the hook wrapper is also going to work — it's the same script with different output gating.

## Requirements

- `jq` and `curl` on PATH
- A valid Anthropic OAuth credentials file at `$CLAUDE_HOME/.credentials.json` (Claude Code writes this on `/login`)

## Notes

This plugin hits `api.anthropic.com/api/oauth/usage` with the `anthropic-beta: oauth-2025-04-20` header. That endpoint is undocumented and may change. If the plugin stops reporting numbers after an Anthropic API update, that's the first thing to check.
