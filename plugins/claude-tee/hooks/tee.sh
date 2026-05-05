#!/usr/bin/env bash
# tee.sh — UserPromptSubmit hook: capture prompt, append to JSONL, optionally
# fan out to SSE / HTTP, optionally block the model from responding.
#
# Reads Claude Code's UserPromptSubmit hook payload on stdin (JSON with at
# least a `prompt` field). Returns either silent success (model proceeds) or
# a JSON block decision when CLAUDE_TEE_BLOCK=1.
#
# Env overrides:
#   CLAUDE_TEE_DIR          default: $HOME/.claude/tee   (JSONL archive dir)
#   CLAUDE_TEE_PORT         default: unset               (SSE server port; only binds if set)
#   CLAUDE_TEE_FANOUT_URLS  default: unset               (comma-separated POST targets)
#   CLAUDE_TEE_BLOCK        default: 0                   (1 = return block decision after capture)
#
# Failures during capture are silent unless CLAUDE_TEE_BLOCK=1 — never break a
# user's turn over a plugin issue.

set -euo pipefail

HOOK_MODE=0
for arg in "$@"; do
  case "$arg" in
    --hook) HOOK_MODE=1 ;;
    -h|--help)
      sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
  esac
done

emit_block() {
  local reason="${1:-blocked by claude-tee plugin (debug mode)}"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg reason "$reason" '{decision: "block", reason: $reason}' 2>/dev/null \
      || printf '%s\n' '{"decision":"block","reason":"blocked by claude-tee plugin (debug mode)"}'
  else
    printf '%s\n' '{"decision":"block","reason":"blocked by claude-tee plugin (debug mode)"}'
  fi
  exit 0
}

# In hook mode, never break the user's turn — install the failure handler
# BEFORE touching any env vars, since those expansions can fail under set -u
# if HOME is unset, etc.
if [[ "$HOOK_MODE" -eq 1 ]]; then
  on_err() {
    if [[ "${CLAUDE_TEE_BLOCK:-0}" == "1" ]]; then
      emit_block "blocked by claude-tee plugin (debug mode)"
    fi
    exit 0
  }
  trap 'on_err' ERR
  # Hide stderr from the user; we never want hook errors to bubble.
  exec 2>/dev/null
fi

# Prompt archives can contain sensitive content. Make sure new files/dirs are
# user-private regardless of the inherited umask.
umask 077

: "${CLAUDE_TEE_DIR:=${HOME:-${TMPDIR:-/tmp}}/.claude/tee}"
: "${CLAUDE_TEE_BLOCK:=0}"

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
SERVER_PY="$PLUGIN_ROOT/bridge/server.py"
# Per-port pidfile so multiple bridge instances on different ports don't fight.
PORT_TAG="${CLAUDE_TEE_PORT:-noport}"
PIDFILE="${TMPDIR:-/tmp}/claude-tee-${PORT_TAG}.pid"
LOGFILE="${TMPDIR:-/tmp}/claude-tee-${PORT_TAG}.log"

if ! command -v jq >/dev/null 2>&1; then
  if [[ "$HOOK_MODE" -eq 1 ]]; then
    [[ "$CLAUDE_TEE_BLOCK" == "1" ]] && emit_block "blocked by claude-tee plugin (debug mode)"
    exit 0
  fi
  echo "claude-tee: jq required" >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  # python3 is only required when the SSE bridge is enabled.
  if [[ -n "${CLAUDE_TEE_PORT:-}" && "$HOOK_MODE" -ne 1 ]]; then
    echo "claude-tee: python3 required for the SSE bridge" >&2
    exit 2
  fi
fi

# Read hook payload
PAYLOAD="$(cat || true)"
if [[ -z "$PAYLOAD" ]]; then
  [[ "$HOOK_MODE" -eq 1 ]] && exit 0
  echo "claude-tee: empty stdin" >&2
  exit 1
fi

PROMPT="$(echo "$PAYLOAD" | jq -r '.prompt // empty')"
SESSION_ID="$(echo "$PAYLOAD" | jq -r '.session_id // empty')"
CWD="$(echo "$PAYLOAD" | jq -r '.cwd // empty')"

# Empty prompt = nothing to capture; return success
if [[ -z "$PROMPT" ]]; then
  [[ "$CLAUDE_TEE_BLOCK" == "1" ]] && emit_block "claude-tee: empty prompt"
  exit 0
fi

# Append to today's JSONL. umask 077 above ensures new files are 0600 / dirs 0700.
mkdir -p "$CLAUDE_TEE_DIR" 2>/dev/null || true
chmod 700 "$CLAUDE_TEE_DIR" 2>/dev/null || true
TODAY="$(date -u +%Y-%m-%d)"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ARCHIVE="$CLAUDE_TEE_DIR/$TODAY.jsonl"

jq -nc \
  --arg ts "$TS" \
  --arg session "$SESSION_ID" \
  --arg cwd "$CWD" \
  --arg prompt "$PROMPT" \
  '{ts: $ts, session_id: $session, cwd: $cwd, prompt: $prompt}' \
  >> "$ARCHIVE" 2>/dev/null || true
# Tighten existing file perms in case the archive was created with a looser umask.
chmod 600 "$ARCHIVE" 2>/dev/null || true

# Optional fan-out: POST to each URL in CLAUDE_TEE_FANOUT_URLS (comma-separated)
if [[ -n "${CLAUDE_TEE_FANOUT_URLS:-}" ]]; then
  IFS=',' read -ra FANOUT_URLS <<< "$CLAUDE_TEE_FANOUT_URLS"
  PAYLOAD_JSON="$(jq -nc \
    --arg ts "$TS" \
    --arg session "$SESSION_ID" \
    --arg cwd "$CWD" \
    --arg prompt "$PROMPT" \
    '{ts: $ts, session_id: $session, cwd: $cwd, prompt: $prompt}')"
  for url in "${FANOUT_URLS[@]}"; do
    url="$(echo "$url" | xargs)"  # trim whitespace
    [[ -z "$url" ]] && continue
    curl -s -m 2 -X POST -H 'Content-Type: application/json' \
      -d "$PAYLOAD_JSON" "$url" >/dev/null 2>&1 || true
  done
fi

# Optional SSE bridge: ensure server is running on $CLAUDE_TEE_PORT, then push.
if [[ -n "${CLAUDE_TEE_PORT:-}" ]]; then
  ensure_server_running() {
    local port="$1"
    # Check pidfile + process liveness
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
      return 0
    fi
    # Not running — start it. Forward all relevant env to the daemon.
    rm -f "$PIDFILE"
    CLAUDE_TEE_PORT="$port" \
      CLAUDE_TEE_DIR="$CLAUDE_TEE_DIR" \
      CLAUDE_TEE_TOKEN="${CLAUDE_TEE_TOKEN:-}" \
      CLAUDE_TEE_BUFFER="${CLAUDE_TEE_BUFFER:-200}" \
      CLAUDE_TEE_MAX_SUBSCRIBERS="${CLAUDE_TEE_MAX_SUBSCRIBERS:-16}" \
      setsid python3 "$SERVER_PY" >>"$LOGFILE" 2>&1 < /dev/null &
    echo $! > "$PIDFILE"
    # Give it a moment to bind
    for _ in 1 2 3 4 5; do
      sleep 0.1
      if curl -s -m 1 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
        return 0
      fi
    done
    return 1
  }

  if ensure_server_running "$CLAUDE_TEE_PORT"; then
    PAYLOAD_JSON="$(jq -nc \
      --arg ts "$TS" \
      --arg session "$SESSION_ID" \
      --arg cwd "$CWD" \
      --arg prompt "$PROMPT" \
      '{ts: $ts, session_id: $session, cwd: $cwd, prompt: $prompt}')"
    auth_args=()
    if [[ -n "${CLAUDE_TEE_TOKEN:-}" ]]; then
      auth_args=(-H "Authorization: Bearer $CLAUDE_TEE_TOKEN")
    fi
    curl -s -m 2 -X POST -H 'Content-Type: application/json' \
      "${auth_args[@]}" \
      -d "$PAYLOAD_JSON" "http://127.0.0.1:$CLAUDE_TEE_PORT/append" >/dev/null 2>&1 || true
  fi
fi

# Block decision (debug option) — emit AFTER capture, so the tap still happens.
if [[ "$CLAUDE_TEE_BLOCK" == "1" ]]; then
  emit_block "blocked by claude-tee plugin (debug mode)"
fi

exit 0
