---
name: quota-status
description: Use when the user asks how much usage quota, rate limit, or plan allowance remains (Codex or Claude), when it resets, or whether there is room for a long autonomous run. Also use before starting long unattended work. Reports used/remaining percent per window and reset times from the quota-watch scripts.
---

# quota-status

Report the agent's remaining plan quota from live data. Never guess or estimate it.

The scripts live in this plugin's `hooks/` directory, two levels above this file
(`<plugin-root>/hooks/`).

## Codex (ChatGPT plan)

```
python3 <plugin-root>/hooks/codex-quota-check.py --json
```

Key fields: `verdict` (ok | warn | halt | unknown), `used_percent` and `remaining_percent` (the
most-used Codex window), and `windows[]`, each with `window_minutes`, `used_percent`,
`remaining_percent`, `reset_at_iso` (UTC), and `mins_to_reset`. `is_stale: true` means
the live fetch failed and cached data (at most 30 minutes old) was served. `unknown`
means no current Codex window was reported; say so rather than assuming headroom.

## Claude Code (Claude subscription)

```
<plugin-root>/hooks/quota-check.sh --json
```

Key fields: `verdict`, `util_5h`, `util_7d`, `resets_at`, `mins_to_reset`, `headroom_min`.

## Reporting

- Answer with the remaining percent for each window, its length (e.g. 5h, 7d), and
  when it resets. Convert reset times to the user's timezone when you know it.
- If the script exits non-zero, report its stderr line. Typical causes are no login or
  an expired token, which running the harness normally refreshes. Do not read or print
  the credential files yourself.
- Add `--force` only when the user asks for a fresh reading. The endpoints are cheap,
  but the cache exists for a reason.
- On `warn` or `halt`, suggest parking work at a clean boundary.
