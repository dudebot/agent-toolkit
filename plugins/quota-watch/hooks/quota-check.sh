#!/usr/bin/env bash
# quota-check.sh — read Claude Max 5h usage, cache adaptively, emit verdict.
#
# Usage:
#   quota-check.sh                 # silent when ok; one line when warn/halt
#   quota-check.sh --json          # full state as JSON (for scripts / hooks)
#   quota-check.sh --verdict       # prints just: ok | warn | halt
#   quota-check.sh --force         # bypass cache TTL
#   quota-check.sh --always-print  # print even when ok (for humans)
#
# Env overrides:
#   CLAUDE_HOME        default: $HOME/.claude
#   QUOTA_CACHE        default: ${TMPDIR:-/tmp}/claude-usage.json
#   QUOTA_HISTORY      default: $CLAUDE_HOME/cache/usage-history.jsonl
#   QUOTA_WARN_PCT     default: 85
#   QUOTA_HALT_PCT     default: 97
#   QUOTA_HALT_HEADROOM_MIN  default: 5   (trigger halt if projected <N min before hit)

set -euo pipefail

: "${CLAUDE_HOME:=$HOME/.claude}"
: "${QUOTA_CACHE:=${TMPDIR:-/tmp}/claude-usage.json}"
: "${QUOTA_HISTORY:=$CLAUDE_HOME/cache/usage-history.jsonl}"
: "${QUOTA_WARN_PCT:=85}"
: "${QUOTA_HALT_PCT:=97}"
: "${QUOTA_HALT_HEADROOM_MIN:=5}"

CREDS="$CLAUDE_HOME/.credentials.json"
ENDPOINT="https://api.anthropic.com/api/oauth/usage"

MODE="text"; FORCE=0; ALWAYS_PRINT=0; HOOK_MODE=0
for arg in "$@"; do
  case "$arg" in
    --json)         MODE="json" ;;
    --verdict)      MODE="verdict" ;;
    --force)        FORCE=1 ;;
    --always-print) ALWAYS_PRINT=1 ;;
    --hook)         HOOK_MODE=1 ;;
    -h|--help)      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  esac
done

# In hook mode, any failure is silent exit 0 — never block the user's turn.
if [[ "$HOOK_MODE" -eq 1 ]]; then
  trap 'exit 0' ERR
  set +e
  exec 2>/dev/null
fi

command -v jq   >/dev/null || { echo "quota-check: jq required" >&2; exit 2; }
command -v curl >/dev/null || { echo "quota-check: curl required" >&2; exit 2; }

now() { date +%s; }
iso_to_epoch() { date -d "$1" +%s 2>/dev/null || echo 0; }

# Adaptive cache TTL — higher utilization shortens TTL.
cache_ttl_sec() {
  local util="$1"
  awk -v u="$util" 'BEGIN{
    if (u < 30)       print 900
    else if (u < 70)  print 300
    else if (u < 90)  print 120
    else              print 60
  }'
}

cache_fresh() {
  [[ "$FORCE" -eq 1 ]] && return 1
  [[ -f "$QUOTA_CACHE" ]] || return 1
  local fetched util resets reset_epoch age ttl
  fetched=$(jq -r '.fetched_at // 0' "$QUOTA_CACHE")
  util=$(jq -r '.api.five_hour.utilization // 0' "$QUOTA_CACHE")
  resets=$(jq -r '.api.five_hour.resets_at // ""' "$QUOTA_CACHE")
  [[ -z "$resets" ]] && return 1
  reset_epoch=$(iso_to_epoch "$resets")
  age=$(( $(now) - fetched ))
  ttl=$(cache_ttl_sec "$util")
  # if reset already passed in cached view, force refresh
  (( reset_epoch <= $(now) )) && return 1
  (( age < ttl ))
}

fetch_live() {
  [[ -f "$CREDS" ]] || { echo "quota-check: no credentials at $CREDS" >&2; exit 3; }
  local token
  token=$(jq -r '.claudeAiOauth.accessToken // empty' "$CREDS")
  [[ -z "$token" ]] && { echo "quota-check: empty accessToken" >&2; exit 3; }

  local tmp http
  tmp=$(mktemp)
  http=$(curl -sS --max-time 10 -o "$tmp" -w '%{http_code}' \
    -H "Authorization: Bearer $token" \
    -H "anthropic-beta: oauth-2025-04-20" \
    "$ENDPOINT" || echo 000)

  if [[ "$http" != "200" ]]; then
    echo "quota-check: fetch failed http=$http" >&2
    rm -f "$tmp"
    # if we have a stale cache, fall back to it rather than hard-fail
    [[ -f "$QUOTA_CACHE" ]] && return 0
    exit 4
  fi

  mkdir -p "$(dirname "$QUOTA_CACHE")" "$(dirname "$QUOTA_HISTORY")"
  local t; t=$(now)
  jq -n --slurpfile api "$tmp" --arg t "$t" \
    '{fetched_at: ($t|tonumber), api: $api[0]}' > "$QUOTA_CACHE"

  jq -n --slurpfile api "$tmp" --arg t "$t" -c \
    '{t: ($t|tonumber),
      util_5h: $api[0].five_hour.utilization,
      resets_at_5h: $api[0].five_hour.resets_at,
      util_7d: $api[0].seven_day.utilization,
      util_opus_7d: ($api[0].seven_day_opus.utilization // null),
      util_sonnet_7d: ($api[0].seven_day_sonnet.utilization // null)}' \
    >> "$QUOTA_HISTORY"

  rm -f "$tmp"
}

# Compute slope over recent samples within the current window.
# Prints: "<slope_pct_per_min> <samples_used>"   (slope can be 0 or negative)
compute_slope() {
  [[ -f "$QUOTA_HISTORY" ]] || { echo "0 0"; return; }
  local resets_at; resets_at=$(jq -r '.api.five_hour.resets_at' "$QUOTA_CACHE")
  local reset_epoch; reset_epoch=$(iso_to_epoch "$resets_at")
  # window start = reset - 5h
  local window_start=$(( reset_epoch - 5*3600 ))
  # take last ~20 samples that fall in current window
  tail -n 200 "$QUOTA_HISTORY" | \
    jq -s --argjson ws "$window_start" \
      'map(select(.t >= $ws)) | .[-20:] |
       if length < 2 then "0 0"
       else
         (.[-1].t - .[0].t) as $dt |
         (.[-1].util_5h - .[0].util_5h) as $du |
         if $dt <= 0 then "0 \(length)"
         else "\($du / ($dt/60)) \(length)" end
       end' -r
}

# Ensure we have a cache entry (fresh or just-fetched)
if ! cache_fresh; then
  fetch_live
fi

UTIL=$(jq -r '.api.five_hour.utilization // 0' "$QUOTA_CACHE")
RESETS=$(jq -r '.api.five_hour.resets_at // ""' "$QUOTA_CACHE")
UTIL7=$(jq -r '.api.seven_day.utilization // 0' "$QUOTA_CACHE")
RESET_EPOCH=$(iso_to_epoch "$RESETS")
NOW=$(now)
MINS_TO_RESET=$(( (RESET_EPOCH - NOW) / 60 ))
(( MINS_TO_RESET < 0 )) && MINS_TO_RESET=0

read -r SLOPE SAMPLES < <(compute_slope)

# Project time-to-100% at current slope (minutes). Infinite if slope <= 0.
PROJ_MIN=$(awk -v u="$UTIL" -v s="$SLOPE" 'BEGIN{
  if (s <= 0) print 99999
  else {
    m = (100 - u) / s
    if (m < 0) m = 0
    print int(m)
  }
}')
HEADROOM_MIN=$(( MINS_TO_RESET < PROJ_MIN ? MINS_TO_RESET : PROJ_MIN ))

# Verdict
VERDICT="ok"
if awk -v u="$UTIL" -v h="$HEADROOM_MIN" -v hp="$QUOTA_HALT_PCT" -v hh="$QUOTA_HALT_HEADROOM_MIN" \
     'BEGIN{exit !(u >= hp || h < hh)}'; then
  VERDICT="halt"
elif awk -v u="$UTIL" -v wp="$QUOTA_WARN_PCT" 'BEGIN{exit !(u >= wp)}'; then
  VERDICT="warn"
fi

WAKE_AT_ISO=""
WAKE_DELAY_SEC=0
if [[ "$VERDICT" == "halt" ]]; then
  # wake 60s after reset for safety
  WAKE_DELAY_SEC=$(( (RESET_EPOCH + 60) - NOW ))
  (( WAKE_DELAY_SEC < 60 )) && WAKE_DELAY_SEC=60
  WAKE_AT_ISO=$(date -u -d "@$(( NOW + WAKE_DELAY_SEC ))" +"%Y-%m-%dT%H:%M:%SZ")
fi

case "$MODE" in
  verdict)
    echo "$VERDICT"
    ;;
  json)
    jq -n \
      --arg verdict "$VERDICT" \
      --argjson util "$UTIL" \
      --argjson util7 "$UTIL7" \
      --arg resets_at "$RESETS" \
      --argjson mins_to_reset "$MINS_TO_RESET" \
      --argjson slope_pct_per_min "$SLOPE" \
      --argjson samples "$SAMPLES" \
      --argjson proj_min_to_100 "$PROJ_MIN" \
      --argjson headroom_min "$HEADROOM_MIN" \
      --arg wake_at "$WAKE_AT_ISO" \
      --argjson wake_delay_sec "$WAKE_DELAY_SEC" \
      '{verdict:$verdict, util_5h:$util, util_7d:$util7, resets_at:$resets_at,
        mins_to_reset:$mins_to_reset, slope_pct_per_min:$slope_pct_per_min,
        slope_samples:$samples, proj_min_to_100:$proj_min_to_100,
        headroom_min:$headroom_min, wake_at:$wake_at, wake_delay_sec:$wake_delay_sec}'
    ;;
  text|*)
    if [[ "$VERDICT" == "ok" && "$ALWAYS_PRINT" -eq 0 ]]; then
      exit 0
    fi
    if [[ "$VERDICT" == "halt" ]]; then
      printf 'QUOTA HALT (advisory): 5h=%.1f%%, reset in %dm. This is a hint, not a stop order. You can re-check at any time with `quota-check.sh --json` — quota moves fast and the snapshot can be stale. If the user has prompted you mid-halt, they are likely overriding the wind-down; continue the work. If running autonomously with no user present, call ScheduleWakeup(delaySeconds=%d) to resume after reset.\n' \
        "$UTIL" "$MINS_TO_RESET" "$WAKE_DELAY_SEC"
    elif [[ "$VERDICT" == "warn" ]]; then
      printf 'QUOTA WARN (advisory): 5h=%.1f%%, reset in %dm (slope %.2f%%/min, headroom %dm). Wind down if the current work can be parked cleanly. Re-check with `quota-check.sh --json` if the slope feels stale. If the user has prompted mid-warn, they are accepting the risk; continue.\n' \
        "$UTIL" "$MINS_TO_RESET" "$SLOPE" "$HEADROOM_MIN"
    else
      printf 'quota ok: 5h=%.1f%%, 7d=%.1f%%, reset in %dm.\n' "$UTIL" "$UTIL7" "$MINS_TO_RESET"
    fi
    ;;
esac
