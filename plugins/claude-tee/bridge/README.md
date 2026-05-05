# claude-tee bridge server

Stdlib-only HTTP server that receives prompt captures from `tee.sh` and fans them out over Server-Sent Events. Started lazily by the hook the first time `CLAUDE_TEE_PORT` is set; persists across hook invocations via a per-port pidfile.

## Endpoints

| Method | Path                                  | Auth                        | Purpose |
|--------|---------------------------------------|-----------------------------|---------|
| `POST` | `/append`                             | Bearer (if token set)       | Body: JSON with `{ts, session_id, cwd, prompt}`. Stores in ring buffer, broadcasts to SSE clients. Body capped at 1 MB. |
| `GET`  | `/events?cwd_prefix=<prefix>`         | Bearer (if token set)       | SSE stream. One `data: <json>\n\n` event per capture. Optional `cwd_prefix` filters server-side so per-project consumers don't drink the firehose. 15-second keepalive comments. Subscribers capped (see below). |
| `GET`  | `/history?n=N&cwd_prefix=<prefix>`    | Bearer (if token set)       | Last N entries from the ring buffer (default 50, max 500), optionally filtered by `cwd_prefix`. |
| `GET`  | `/projects`                           | Bearer (if token set)       | Distinct `cwd` values in the ring buffer, each with `count` and `last_seen` ts. Lets consumers discover active projects without out-of-band knowledge. |
| `GET`  | `/health`                             | Always open                 | 200 OK + buffer size. Useful for liveness probes; never leaks captures. |

## Authentication

If `CLAUDE_TEE_TOKEN` is set in the server's environment, all endpoints except `/health` require `Authorization: Bearer <token>`. The hook automatically forwards the same token when posting to its own bridge, so end-users only need to set the env var once (in `settings.json`'s `env` block, shell rc, etc.).

If `CLAUDE_TEE_TOKEN` is unset, all local requests are accepted. This is a low-friction default for single-user setups; on shared machines you almost certainly want a token.

## Binding

The server binds `127.0.0.1` only. There is no IPv6 listener. If you want remote access, put it behind a reverse proxy that adds TLS — and even then, set `CLAUDE_TEE_TOKEN`.

## Env vars (read at start)

| Variable                    | Default | Purpose |
|-----------------------------|---------|---------|
| `CLAUDE_TEE_PORT`           | (required) | Port to bind on `127.0.0.1`. |
| `CLAUDE_TEE_TOKEN`          | unset   | If set, gate `/append`, `/events`, `/history` behind `Authorization: Bearer`. |
| `CLAUDE_TEE_BUFFER`         | `200`   | Ring buffer size for `/history`. |
| `CLAUDE_TEE_MAX_SUBSCRIBERS`| `16`    | Maximum concurrent SSE subscribers. Excess connections receive `503`. |

`CLAUDE_TEE_DIR` is not used by the server — the JSONL archive is owned by the hook.

## Running standalone

```bash
CLAUDE_TEE_PORT=8765 python3 server.py
# Or with auth:
CLAUDE_TEE_PORT=8765 CLAUDE_TEE_TOKEN=my-secret python3 server.py
```

Then in another terminal:

```bash
curl -N -H "Authorization: Bearer my-secret" http://127.0.0.1:8765/events
curl -H "Authorization: Bearer my-secret" "http://127.0.0.1:8765/history?n=10"
```

## Lifecycle

- The hook `tee.sh` daemonizes the server via `setsid` and stores its PID at `${TMPDIR:-/tmp}/claude-tee-<PORT>.pid`. The per-port suffix means multiple bridge instances on different ports do not collide.
- Subsequent hook invocations check the pidfile + process liveness; only respawn if the process is gone.
- The server has no persistent state — restart loses the ring buffer, but the JSONL archive (owned by the hook) is durable.
- Logs go to `${TMPDIR:-/tmp}/claude-tee-<PORT>.log`.
