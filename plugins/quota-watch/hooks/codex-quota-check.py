#!/usr/bin/env python3
"""codex-quota-check.py: read remaining Codex (ChatGPT plan) usage quota.

Codex counterpart of quota-check.sh. Reads the ChatGPT login that the Codex CLI
stores in $CODEX_HOME/auth.json (read-only; tokens are never refreshed, written,
or printed) and calls the endpoint the CLI's /status view uses:

    GET https://chatgpt.com/backend-api/wham/usage

That endpoint is undocumented and may change. Reading it does not consume quota.

Usage:
  codex-quota-check.py                 # silent when ok; one line when warn/halt
  codex-quota-check.py --always-print  # print even when ok (for humans)
  codex-quota-check.py --json          # normalized state as JSON
  codex-quota-check.py --verdict       # prints just: ok | warn | halt | unknown
  codex-quota-check.py --force         # bypass cache TTL
  codex-quota-check.py --hook          # hook mode: any failure is a silent exit 0

Env overrides:
  CODEX_HOME            default: $HOME/.codex
  CODEX_QUOTA_CACHE     default: ${TMPDIR:-/tmp}/codex-usage-<uid>-<hash>.json
  CODEX_QUOTA_BASE_URL  default: https://chatgpt.com/backend-api
  QUOTA_WARN_PCT        default: 85
  QUOTA_HALT_PCT        default: 97

Only normalized usage numbers are cached or printed. User, account, and email
fields are never copied out of the response. Redirects are refused so the
credential is only ever sent to the configured base URL.
"""
import hashlib
import json
import math
import os
import re
import signal
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ARGS = set(sys.argv[1:])
HOOK = "--hook" in ARGS
DEADLINE_SEC = 12        # whole-run budget; the Codex hook timeout is 15s
HTTP_TIMEOUT_SEC = 8
STALE_MAX_SEC = 1800     # never serve cached data older than this after a failed fetch


class QuotaError(Exception):
    def __init__(self, msg, code):
        super().__init__(msg)
        self.code = code


class Deadline(BaseException):
    """Raised by the run-wide alarm; a BaseException so no broad handler swallows it."""


MAX_EPOCH = 253402300799  # 9999-12-31; anything later cannot be rendered as a date


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def on_deadline(signum, frame):
    raise Deadline()


def env_float(name, default):
    try:
        v = float(os.environ.get(name, default))
        return v if math.isfinite(v) else float(default)
    except ValueError:
        return float(default)


def num(v):
    """A finite float, or None. Rejects bools and garbage."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if math.isfinite(v) else None


def read_auth(codex_home):
    path = os.path.join(codex_home, "auth.json")
    try:
        with open(path) as f:
            auth = json.load(f)
    except (OSError, ValueError) as e:
        raise QuotaError(f"cannot read {path}: {type(e).__name__}", 3)
    tokens = auth.get("tokens") if isinstance(auth, dict) else None
    if not isinstance(tokens, dict) or not isinstance(tokens.get("access_token"), str) \
            or not tokens["access_token"]:
        raise QuotaError("no ChatGPT login in auth.json (API-key logins have no plan quota)", 3)
    account = tokens.get("account_id") if isinstance(tokens.get("account_id"), str) else ""
    return tokens["access_token"], account


def login_digest(codex_home, base_url, access, account):
    """Short one-way digest of Codex home, backend, and current login.

    Stored in the cache and used in the default file name, so switching any of them
    never serves another login's numbers. A token refresh simply starts a new cache."""
    key = "\0".join([os.path.realpath(codex_home), base_url, account, access])
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def cache_path(digest):
    explicit = os.environ.get("CODEX_QUOTA_CACHE")
    if explicit:
        return explicit
    return os.path.join(os.environ.get("TMPDIR") or "/tmp",
                        f"codex-usage-{os.getuid()}-{digest}.json")


def ttl_sec(pct):
    return 900 if pct < 30 else 300 if pct < 70 else 120 if pct < 90 else 60


def normalize(data):
    """Copy only known scalar usage fields out of a raw /wham/usage response."""
    if not isinstance(data, dict) or not isinstance(data.get("rate_limit"), dict):
        return None
    windows = []

    def add(scope, rl):
        if not isinstance(rl, dict):
            return
        for name in ("primary_window", "secondary_window"):
            w = rl.get(name)
            if not isinstance(w, dict):
                continue
            used, secs, reset = (num(w.get("used_percent")), num(w.get("limit_window_seconds")),
                                 num(w.get("reset_at")))
            if used is None:
                continue
            windows.append({"scope": scope, "window": name.split("_")[0],
                            "window_minutes": int(secs // 60) if secs else None,
                            "used_percent": used,
                            "reset_at": int(reset) if reset else None})

    add("codex", data["rate_limit"])
    add("code_review", data.get("code_review_rate_limit"))
    extras = data.get("additional_rate_limits")
    for i, extra in enumerate(extras if isinstance(extras, list) else []):
        if isinstance(extra, dict):
            add(f"additional_{i}", extra.get("rate_limit"))
    rl = data["rate_limit"]
    credits = data.get("credits") if isinstance(data.get("credits"), dict) else {}
    return sanitize_usage({
        "allowed": rl.get("allowed"),
        "limit_reached": rl.get("limit_reached"),
        "credits": credits,
        "windows": windows,
    })


SCOPE_RE = re.compile(r"^(codex|code_review|additional_[0-9]{1,3})$")


def sanitize_usage(u):
    """Rebuild a usage record from validated scalars only; None if malformed.

    Used both on fresh responses and on cache reads, so a tampered or corrupted
    cache can neither crash the run nor carry arbitrary strings into output."""
    if not isinstance(u, dict) or not isinstance(u.get("windows"), list):
        return None
    windows = []
    for w in u["windows"]:
        if not isinstance(w, dict):
            return None
        scope, used = w.get("scope"), num(w.get("used_percent"))
        mins, reset = num(w.get("window_minutes")), num(w.get("reset_at"))
        if not (isinstance(scope, str) and SCOPE_RE.match(scope)) or used is None:
            return None
        if w.get("window") not in ("primary", "secondary"):
            return None
        if (w.get("window_minutes") is not None and mins is None) or \
                (w.get("reset_at") is not None and (reset is None or not 0 <= reset <= MAX_EPOCH)):
            return None
        windows.append({"scope": scope, "window": w["window"],
                        "window_minutes": int(mins) if mins and mins > 0 else None,
                        "used_percent": min(max(used, 0.0), 100.0),
                        "reset_at": int(reset) if reset and reset > 0 else None})
    credits = u.get("credits") if isinstance(u.get("credits"), dict) else {}
    flag = lambda v: v if isinstance(v, bool) else None
    return {
        "allowed": flag(u.get("allowed")),
        "limit_reached": flag(u.get("limit_reached")),
        "credits": {k: credits[k] for k in ("has_credits", "unlimited", "overage_limit_reached")
                    if isinstance(credits.get(k), bool)},
        "windows": windows,
    }


def fetch(base_url, access, account, digest):
    headers = {"Authorization": "Bearer " + access, "User-Agent": "codex-cli",
               "Accept": "application/json"}
    if account:
        headers["ChatGPT-Account-Id"] = account
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(base_url + "/wham/usage", headers=headers)
    try:
        with opener.open(req, timeout=HTTP_TIMEOUT_SEC) as resp:
            data = json.loads(resp.read(1_000_000))
    except urllib.error.HTTPError as e:
        hint = " (token expired? running any codex command refreshes it)" if e.code in (401, 403) else ""
        return None, f"http={e.code}{hint}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return None, type(e).__name__
    usage = normalize(data)
    if usage is None:
        return None, "unexpected response shape"
    return {"fetched_at": int(time.time()), "login": digest, "usage": usage}, None


def load_cache(path, digest):
    """Return a validated, rebuilt cache entry or None.

    Malformed content, or a cache written for a different login/backend, is a miss."""
    try:
        with open(path) as f:
            c = json.load(f)
        if not isinstance(c, dict) or c.get("login") != digest:
            return None
        fetched, usage = num(c.get("fetched_at")), sanitize_usage(c.get("usage"))
        if fetched is None or not 0 <= fetched <= MAX_EPOCH or usage is None:
            return None
        return {"fetched_at": int(fetched), "login": digest, "usage": usage}
    except Exception:
        return None


def write_cache(path, cache):
    tmp = None
    try:
        d = os.path.dirname(path) or "."
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".codex-usage.")
        with os.fdopen(fd, "w") as f:
            json.dump(cache, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except Exception:  # caching is best effort; live data is still used
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def fmt_duration(mins):
    if mins is None:
        return "?"
    if mins >= 1440:
        return f"{mins // 1440}d{(mins % 1440) // 60}h"
    return f"{mins // 60}h{mins % 60}m"


def fmt_window(w):
    m = w["window_minutes"]
    label = ("?" if not m else f"{m // 1440}d" if m % 1440 == 0
             else f"{m // 60}h" if m % 60 == 0 else f"{m}m")
    return (f"{label}={w['used_percent']:.0f}% used ({w['remaining_percent']:.0f}% left, "
            f"reset in {fmt_duration(w.get('mins_to_reset'))})")


def main():
    codex_home = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    base_url = (os.environ.get("CODEX_QUOTA_BASE_URL") or "https://chatgpt.com/backend-api").rstrip("/")
    warn_pct = env_float("QUOTA_WARN_PCT", 85)
    halt_pct = env_float("QUOTA_HALT_PCT", 97)
    access, account = read_auth(codex_home)
    digest = login_digest(codex_home, base_url, access, account)
    path = cache_path(digest)
    now = int(time.time())

    cache = load_cache(path, digest)
    fresh = False
    if cache and "--force" not in ARGS:
        ws = cache["usage"]["windows"]
        top = max([w["used_percent"] for w in ws] or [0])
        fresh = (0 <= now - cache["fetched_at"] < ttl_sec(top)
                 and all((w["reset_at"] or float("inf")) > now for w in ws))

    stale, err = False, None
    if not fresh:
        new, err = fetch(base_url, access, account, digest)
        if new:
            cache = new
            write_cache(path, cache)
        elif cache and 0 <= now - cache["fetched_at"] < STALE_MAX_SEC:
            stale = True
        else:
            raise QuotaError(f"fetch failed {err}", 4)

    usage = cache["usage"]
    ws, expired_codex = [], False
    for w in usage["windows"]:
        if w["reset_at"] and w["reset_at"] <= now:
            # Window already reset; its cached number is no longer evidence.
            expired_codex = expired_codex or w["scope"] == "codex"
            continue
        w = dict(w, remaining_percent=max(0.0, 100.0 - w["used_percent"]))
        if w["reset_at"]:
            w["reset_at_iso"] = datetime.fromtimestamp(w["reset_at"], timezone.utc).isoformat()
            w["mins_to_reset"] = max(0, (w["reset_at"] - now) // 60)
        ws.append(w)
    codex_ws = [w for w in ws if w["scope"] == "codex"]
    top = max([w["used_percent"] for w in codex_ws]) if codex_ws else None
    blocked = usage.get("limit_reached") is True or usage.get("allowed") is False
    if expired_codex:
        blocked = False  # the flags may describe a window that has since reset; trust survivors
    if blocked or (top is not None and top >= halt_pct):
        verdict = "halt"
    elif top is None:
        verdict = "unknown"
    elif top >= warn_pct:
        verdict = "warn"
    else:
        verdict = "ok"

    if "--json" in ARGS:
        print(json.dumps({
            "verdict": verdict,
            "used_percent": top,
            "remaining_percent": None if top is None else max(0.0, 100.0 - top),
            "limit_reached": usage.get("limit_reached"),
            "credits": usage.get("credits"),
            "windows": ws,
            "cache_age_sec": now - cache["fetched_at"],
            "is_stale": stale,
            "last_error": err,
        }, indent=2))
        return
    if "--verdict" in ARGS:
        print(verdict)
        if stale:
            print(f"codex-quota-check: stale data ({err})", file=sys.stderr)
        return
    if verdict in ("ok", "unknown") and "--always-print" not in ARGS:
        return
    body = ", ".join(fmt_window(w) for w in codex_ws) or "no current usage window reported"
    suffix = f" [stale: {err}]" if stale else ""
    if verdict == "halt":
        print(f"CODEX QUOTA HALT (advisory): {body}{suffix}. Codex plan quota is at or near its "
              "limit. Before starting new work, tell the user and finish or park the current "
              "step cleanly; continue past this only if the user explicitly confirms.")
    elif verdict == "warn":
        print(f"CODEX QUOTA WARN (advisory): {body}{suffix}. Mention this to the user and prefer "
              "parking at a clean boundary over starting large new work.")
    else:
        print(f"codex quota {verdict}: {body}{suffix}")


if __name__ == "__main__":
    if ARGS & {"-h", "--help"}:
        print(__doc__)
        sys.exit(0)
    try:
        signal.signal(signal.SIGALRM, on_deadline)
        signal.alarm(DEADLINE_SEC)
        main()
        signal.alarm(0)
    except Deadline:
        if HOOK:
            sys.exit(0)
        print("codex-quota-check: timed out", file=sys.stderr)
        sys.exit(5)
    except QuotaError as e:
        if HOOK:
            sys.exit(0)
        print(f"codex-quota-check: {e}", file=sys.stderr)
        sys.exit(e.code)
    except Exception as e:  # never block a turn in hook mode
        if HOOK:
            sys.exit(0)
        print(f"codex-quota-check: unexpected {type(e).__name__}", file=sys.stderr)
        sys.exit(1)
