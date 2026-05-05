#!/usr/bin/env python3
"""claude-tee bridge server.

Stdlib-only HTTP server that receives prompt captures from the tee.sh hook
and fans them out to Server-Sent Events subscribers. Also persists a small
in-memory ring buffer for late joiners requesting recent history.

Endpoints:
  POST /append        body: JSON {ts, session_id, cwd, prompt}
                      stores in ring buffer, broadcasts to SSE clients.
  GET  /events        SSE stream — one `data: <json>\\n\\n` event per capture.
  GET  /history?n=N   last N entries (default 50, max 500).
  GET  /health        200 OK if server is alive.

Env:
  CLAUDE_TEE_PORT     port to bind on 127.0.0.1 (required)
  CLAUDE_TEE_DIR      JSONL archive dir (only used by hook; server doesn't read it)
  CLAUDE_TEE_BUFFER   ring buffer size (default 200)

The server binds 127.0.0.1 only — it is not intended to be exposed to other
hosts. If you want external access, put it behind a reverse proxy with auth.
"""

import json
import os
import queue
import sys
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get("CLAUDE_TEE_PORT", "0") or "0")
BUFFER_SIZE = int(os.environ.get("CLAUDE_TEE_BUFFER", "200"))
MAX_SUBSCRIBERS = int(os.environ.get("CLAUDE_TEE_MAX_SUBSCRIBERS", "16"))
TOKEN = os.environ.get("CLAUDE_TEE_TOKEN", "").strip()  # if set, require Bearer match
MAX_BODY_BYTES = 1_000_000

if PORT <= 0:
    print("claude-tee bridge: CLAUDE_TEE_PORT must be set to a positive integer", file=sys.stderr)
    sys.exit(2)

# Ring buffer of recent captures + lock
_buffer = deque(maxlen=BUFFER_SIZE)
_buffer_lock = threading.Lock()

# SSE subscriber registry: each subscriber gets a Queue
_subscribers = []
_subscribers_lock = threading.Lock()


def _broadcast(entry):
    with _buffer_lock:
        _buffer.append(entry)
    with _subscribers_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(entry)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


def _subscribe():
    """Reserve an SSE subscriber slot. Returns None if at capacity."""
    with _subscribers_lock:
        if len(_subscribers) >= MAX_SUBSCRIBERS:
            return None
        q = queue.Queue(maxsize=BUFFER_SIZE)
        _subscribers.append(q)
        return q


def _unsubscribe(q):
    with _subscribers_lock:
        if q in _subscribers:
            _subscribers.remove(q)


class Handler(BaseHTTPRequestHandler):
    # Quiet default access logging
    def log_message(self, fmt, *args):
        return

    def _json(self, code, body):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _auth_ok(self):
        """If CLAUDE_TEE_TOKEN is set, require Authorization: Bearer <token>.
        If unset, all local requests are allowed (the historical, low-friction default)."""
        if not TOKEN:
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        return header[len("Bearer "):].strip() == TOKEN

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/health":
            self._json(200, {"ok": True, "buffer_size": len(_buffer)})
            return
        if not self._auth_ok():
            self._json(401, {"error": "unauthorized"})
            return
        q = parse_qs(u.query or "")
        cwd_prefix = (q.get("cwd_prefix", [""])[0] or "").strip()

        def _match(entry):
            if not cwd_prefix:
                return True
            return isinstance(entry, dict) and (entry.get("cwd") or "").startswith(cwd_prefix)

        if u.path == "/projects":
            # Distinct cwds in the ring buffer, with last-seen timestamp + count.
            seen = {}
            with _buffer_lock:
                for e in _buffer:
                    cwd = (e.get("cwd") or "") if isinstance(e, dict) else ""
                    if not cwd:
                        continue
                    cur = seen.get(cwd, {"cwd": cwd, "count": 0, "last_seen": ""})
                    cur["count"] += 1
                    ts = e.get("ts") or ""
                    if ts > cur["last_seen"]:
                        cur["last_seen"] = ts
                    seen[cwd] = cur
            projects = sorted(seen.values(), key=lambda r: r["last_seen"], reverse=True)
            self._json(200, {"projects": projects})
            return
        if u.path == "/history":
            n = int((q.get("n", ["50"])[0]))
            n = max(1, min(n, 500))
            with _buffer_lock:
                items = [e for e in _buffer if _match(e)]
            items = items[-n:]
            self._json(200, {"items": items, "cwd_prefix": cwd_prefix or None})
            return
        if u.path == "/events":
            sub = _subscribe()
            if sub is None:
                self._json(503, {"error": "max subscribers reached", "max": MAX_SUBSCRIBERS})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                # Initial keepalive so clients see the connection immediately
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        entry = sub.get(timeout=15)
                        if not _match(entry):
                            continue
                        chunk = b"data: " + json.dumps(entry).encode("utf-8") + b"\n\n"
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except queue.Empty:
                        # Periodic keepalive comment line
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                _unsubscribe(sub)
            return
        self._json(404, {"error": "not found", "path": u.path})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/append":
            self._json(404, {"error": "not found", "path": u.path})
            return
        if not self._auth_ok():
            self._json(401, {"error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > MAX_BODY_BYTES:
            self._json(400, {"error": "missing or oversized body", "max": MAX_BODY_BYTES})
            return
        try:
            body = self.rfile.read(length)
            entry = json.loads(body.decode("utf-8"))
        except Exception as e:
            self._json(400, {"error": f"invalid json: {e}"})
            return
        if not isinstance(entry, dict) or "prompt" not in entry:
            self._json(400, {"error": "body must be a JSON object with a 'prompt' field"})
            return
        _broadcast(entry)
        self._json(200, {"ok": True})


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
