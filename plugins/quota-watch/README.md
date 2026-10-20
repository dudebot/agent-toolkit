# quota-watch

Quota monitors for Claude Code and Codex. Both run as a `UserPromptSubmit` hook, stay silent while usage is fine, and inject a wind-down notice near the limit. A bundled `quota-status` skill lets the agent report remaining quota when asked.

## Claude Code

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

## Install (Claude Code)

Via this marketplace:

```
/plugin marketplace add dudebot/agent-toolkit
/plugin install quota-watch@agent-toolkit
```

## Configuration (Claude Code)

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

## Codex

`hooks/codex-quota-check.py` reads your Codex (ChatGPT plan) usage from the same endpoint the Codex CLI's `/status` view uses, with the login Codex already stores in `$CODEX_HOME/auth.json`. It only reads that file: tokens are never refreshed, written, or printed, only normalized usage numbers are cached or printed, and redirects are refused so the credential only goes to the configured backend. Reading usage does not consume quota.

What you get:

- **Hook** (`hooks/codex-hooks.json`, `UserPromptSubmit`): silent when ok; a one-line `CODEX QUOTA WARN` / `CODEX QUOTA HALT` notice the model sees as context when the most-used Codex window crosses the warn/halt threshold or the backend reports the limit reached. Codex has no `ScheduleWakeup` equivalent, so halt is a park-and-stop advisory.
- **Skill** (`quota-status`): the agent runs the script and answers questions like "how much quota is left?" with live numbers instead of guessing.
- **CLI**: the same flags as the Claude script.

```
codex-quota-check.py                 # silent when ok; one line when warn/halt
codex-quota-check.py --always-print  # e.g. "codex quota ok: 7d=40% used (60% left, reset in 3d4h)"
codex-quota-check.py --json          # verdict, used/remaining percent, windows[], reset times
codex-quota-check.py --verdict       # just: ok | warn | halt | unknown
codex-quota-check.py --force         # bypass the adaptive cache
```

The windows depend on your plan: some plans have a 5-hour and a weekly window, others only one. The script reports whatever the backend returns, including code-review and additional limits, and bases the verdict on the most-used Codex window. If the backend reports no current Codex window, the verdict is `unknown` rather than a guessed headroom. The adaptive cache TTL is the same as above; after a failed fetch, cached data up to 30 minutes old is served and marked `is_stale`, and windows whose reset time has passed are dropped. The whole run is capped at 12 seconds by an alarm so the hook finishes inside Codex's 15-second timeout.

### Install (Codex)

```
codex plugin marketplace add dudebot/agent-toolkit --ref main
codex plugin add quota-watch@agent-toolkit
```

Codex requires you to trust plugin hooks before they run: start `codex`, open `/hooks`, and approve the quota-watch `UserPromptSubmit` hook. Re-approve after plugin updates, since trust is pinned to the hook content. The skill works without the hook being trusted.

To call the script from cron or a plain shell, point at the installed copy under `$CODEX_HOME/plugins/cache/agent-toolkit/quota-watch/<version>/hooks/`, or keep a small wrapper on your `PATH` that resolves the newest installed version.

### Configuration (Codex)

| Variable | Default | Purpose |
| --- | --- | --- |
| `CODEX_HOME` | `$HOME/.codex` | Where Codex keeps `auth.json` |
| `CODEX_QUOTA_CACHE` | `$TMPDIR/codex-usage-<uid>-<hash>.json` | Cached usage (mode 0600, normalized numbers only; tagged with a one-way digest of the Codex home, backend, and login, and ignored if that digest does not match, including at a custom path) |
| `CODEX_QUOTA_BASE_URL` | `https://chatgpt.com/backend-api` | Backend base URL |
| `QUOTA_WARN_PCT` / `QUOTA_HALT_PCT` | `85` / `97` | Shared with the Claude script |

Requirements: `python3` (standard library only) and a ChatGPT login in Codex (`codex login`). API-key logins have no plan quota to read.

## Notes

This plugin hits `api.anthropic.com/api/oauth/usage` with the `anthropic-beta: oauth-2025-04-20` header. That endpoint is undocumented and may change. If the plugin stops reporting numbers after an Anthropic API update, that's the first thing to check.

The Codex script hits `chatgpt.com/backend-api/wham/usage`, also undocumented. If it starts returning errors or empty windows after a Codex update, check which endpoint the open-source Codex CLI currently uses for rate limits.
