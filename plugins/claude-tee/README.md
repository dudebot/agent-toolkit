# claude-tee

A Claude Code plugin that **tees every prompt** — captures it to a local JSONL archive, optionally fans it out to subscribers over Server-Sent Events or HTTP POST, and (as an opt-in debug option) can block the model from responding after capture.

The metaphor is Unix `tee(1)`: data continues to its destination, with a copy written elsewhere. By default, the plugin is fully transparent — your turn proceeds as normal, you just have a durable archive of what you asked.

## Use cases

- **Personal prompt archive.** A timestamped JSONL of everything you asked Claude Code, ever. Like `~/.bash_history` but for prompts.
- **Live transcript display.** Run an OBS overlay, terminal viewer, or web dashboard subscribed to the SSE stream. Useful for screencasts and pair-programming.
- **Pipeline trigger.** POST every prompt into your own automation (n8n, scripts, search index) for downstream processing.
- **Capture-only debugging.** Blocking flag stops the model after capture — useful when you're testing the tee pipeline itself and don't want to burn model turns.

## Install

```
/plugin marketplace add dudebot/agent-toolkit
/plugin install claude-tee@agent-toolkit
```

## Configuration

All env vars are optional. Default behavior with no configuration: append-only JSONL at `~/.claude/tee/YYYY-MM-DD.jsonl`, no fan-out, no blocking.

| Variable                       | Default              | Purpose |
|--------------------------------|----------------------|---------|
| `CLAUDE_TEE_DIR`               | `$HOME/.claude/tee`  | JSONL archive directory. One file per UTC day. Files created `0600`, dir `0700`. |
| `CLAUDE_TEE_PORT`              | unset                | If set, the bridge server binds on `127.0.0.1:<port>` and broadcasts captures via SSE. |
| `CLAUDE_TEE_FANOUT_URLS`       | unset                | Comma-separated POST targets. Each capture is `POST`ed as JSON to every URL. 2-second timeout per target; failures are silent. |
| `CLAUDE_TEE_BLOCK`             | `0`                  | `1` = return a `block` decision after capture, preventing the model from responding. See "Blocking mode" below. |
| `CLAUDE_TEE_TOKEN`             | unset                | If set, the bridge server requires `Authorization: Bearer <token>` on `/events`, `/history`, and `/append`. The hook forwards the token automatically when posting to its own bridge. `/health` remains unauthenticated. |
| `CLAUDE_TEE_BUFFER`            | `200`                | Ring buffer size for the bridge server's `/history` endpoint. |
| `CLAUDE_TEE_MAX_SUBSCRIBERS`   | `16`                 | Cap on concurrent SSE subscribers. Excess connections get `503`. |

Set them in `settings.json`'s `env` block, your shell rc, or per-invocation.

## JSONL schema

One line per prompt:

```json
{"ts":"2026-05-04T14:23:01Z","session_id":"...","cwd":"/path","prompt":"..."}
```

UTC timestamps. Multi-line prompts are JSON-escaped (newlines preserved as `\n` in the string).

## Bridge server

If `CLAUDE_TEE_PORT` is set, the hook lazily starts a stdlib-only Python server (`bridge/server.py`). See [`bridge/README.md`](bridge/README.md) for endpoint details. Highlights:

- `GET /events?cwd_prefix=...` — SSE stream of captures (one event per prompt), optionally filtered by project
- `GET /history?n=N&cwd_prefix=...` — last N entries from the ring buffer
- `GET /projects` — distinct `cwd` values seen recently, with last-seen ts
- `GET /health` — liveness probe

The server binds `127.0.0.1` only. Lifecycle: per-port pidfile at `${TMPDIR:-/tmp}/claude-tee-<PORT>.pid` (so multiple bridges on different ports don't collide); respawned if the process is gone. Logs at `${TMPDIR:-/tmp}/claude-tee-<PORT>.log`.

## Multi-project semantics

The daemon is **user-global, not per-project**. Once any Claude Code instance starts the bridge, it stays up across other projects opening, closing, and re-opening — `setsid` detaches it from the spawning process. Subsequent hook invocations from any project find the running daemon via the per-port pidfile and reuse it.

This means:

- All projects on the same machine fan in to one daemon by default. Every captured prompt carries its own `cwd` field, so a single consumer subscribed to `/events` sees a unified stream tagged by project.
- A consumer that only cares about one project uses `?cwd_prefix=/path/to/that/project` on `/events` or `/history` — the server filters before sending.
- `GET /projects` returns the distinct `cwd` values seen recently with last-seen timestamps, so a consumer can discover active projects without external configuration.

If you genuinely need isolation between projects (different daemons, different ports), set a different `CLAUDE_TEE_PORT` per project via that project's `.claude/settings.json` `env` block. The pidfile is per-port, so two daemons on different ports coexist cleanly. This is rarely what you want — the trust boundary is already the user, and per-event `cwd` provenance covers most use cases without N daemons.

## Blocking mode

When `CLAUDE_TEE_BLOCK=1`, the hook captures the prompt as usual, then returns the documented Claude Code hook block payload:

```json
{"decision": "block", "reason": "blocked by claude-tee plugin (debug mode)"}
```

The model never sees the prompt. The user sees the reason string in their terminal. **The block reason is hardcoded and not configurable** — a configurable reason invites suspicious customization.

This is dual-use, and the README is honest about that:

- **As a debug aid** — testing the tee pipeline without burning model turns is the legitimate use the flag was added for. Useful when iterating on a downstream consumer (overlay, archive viewer) where you don't need the model in the loop.
- **As a transcript-only mode** — the same mechanism turns Claude Code into a capture-only frontend. If you set this on a shared machine, anyone using that Claude Code config will silently have every prompt intercepted and never see a model response.

If you enable this on a machine other people use, **tell them.** Silent interception of someone else's session crosses a consent line that "it's just a debug flag" doesn't excuse. Set it explicitly per-session via shell rather than baking it into `settings.json` if you're not the only user.

## Failure handling

The hook fails silent in normal operation — capture errors do not break your turn. The exception is when `CLAUDE_TEE_BLOCK=1`: even capture failure returns the block decision, since the user has explicitly asked for blocking and silently letting the model respond would surprise them.

If you suspect the hook isn't running:

```bash
# Run the hook against a synthetic payload
echo '{"prompt":"test","session_id":"s","cwd":"/"}' | \
  CLAUDE_TEE_DIR=/tmp/tee-test bash plugins/claude-tee/hooks/tee.sh
ls /tmp/tee-test/
```

## Requirements

- `bash`, `jq`, `curl` on PATH (standard on most Linux/Mac)
- `python3` for the bridge server (only required if `CLAUDE_TEE_PORT` is set)
- Disk space for the JSONL archive (small — typical prompt is < 1 KB; days of usage is < 1 MB)

## Privacy

The JSONL archive contains every prompt you submit, including any text you'd consider sensitive. Treat the archive directory the same way you'd treat your shell history. There is no built-in retention or rotation — set up logrotate or a cron job if you want one.

The bridge server binds `127.0.0.1` only. Authentication is optional via `CLAUDE_TEE_TOKEN` — if set, `/events`, `/history`, and `/append` require `Authorization: Bearer <token>`; `/health` is always open. Even with auth, don't expose the port to other hosts without a reverse proxy that adds TLS.
