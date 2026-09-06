"""Temporary SSH-forwarded inspection transport; never a public application route.

The operator supplies a reviewed exact-target inventory. No discovery, mutation,
wildcard API access, redirect following, token export, or application imports.
The process is deliberately single-request-at-a-time and bounded in lifetime.
"""
from __future__ import annotations

import argparse
import base64
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import signal
import time
from urllib.parse import quote, unquote, urlsplit

MAX_BODY = 16 * 1024 * 1024
MAX_TARGETS = 10000
RESPONSE_HEADERS = frozenset({
    "content-type", "content-language", "retry-after", "server-timing",
    "x-request-id", "x-response-time-ms", "x-dtos-server-duration-ms",
    "x-dtos-request-duration", "x-dtos-warming",
    "content-security-policy", "content-security-policy-report-only",
    "x-content-type-options", "x-frame-options", "referrer-policy",
    "permissions-policy", "cross-origin-opener-policy", "cross-origin-embedder-policy",
    "cross-origin-resource-policy", "access-control-allow-origin", "vary",
})


def valid_target(target: str) -> bool:
    """Reject ambiguous encodings before exact inventory membership checking."""
    if not isinstance(target, str) or len(target) > 4096:
        return False
    if any(ord(char) < 33 or ord(char) > 126 for char in target):
        return False
    try:
        parsed = urlsplit(target)
    except ValueError:
        return False
    if parsed.scheme or parsed.netloc or parsed.fragment:
        return False
    if not target.startswith("/") or target.startswith("//"):
        return False
    if "\\" in target or "//" in parsed.path:
        return False
    # Canonical franchise/pick IDs use percent-encoded colons. Permit those,
    # not encoded separators, traversal, control characters, or double encoding.
    if "%" in parsed.path and re.search(r"%(?!3[Aa])", parsed.path):
        return False
    if any(part in {".", ".."} for part in parsed.path.split("/")):
        return False
    return not (
        parsed.path in {"/sync", "/transactions/refresh"}
        or parsed.path.startswith(("/api/account", "/api/admin"))
        or (parsed.path.startswith("/account/") and parsed.path not in {
            "/account/sign-in", "/account/register", "/account/leagues",
        })
    )


class RelayPolicy:
    def __init__(self, targets: list[str], token: str, upstream_port: int):
        if not token or len(token) < 32 or any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise ValueError("Invalid local inspection credential")
        if not 1 <= upstream_port <= 65535:
            raise ValueError("Invalid loopback port")
        if not targets or len(targets) > MAX_TARGETS or not all(valid_target(t) for t in targets):
            raise ValueError("Invalid exact inspection inventory")
        self.targets = frozenset(targets)
        self.token = token
        self.upstream_port = upstream_port
        self.secret_forms = tuple({
            token.encode(), quote(token, safe="").encode(),
            json.dumps(token)[1:-1].encode(), base64.b64encode(token.encode()),
        })
        if any(not self.clean(unquote(target).encode()) for target in targets):
            raise ValueError("Invalid exact inspection inventory")

    def permits(self, method: str, target: str) -> bool:
        return method in {"GET", "HEAD"} and valid_target(target) and target in self.targets

    def clean(self, content: bytes) -> bool:
        return not any(secret in content for secret in self.secret_forms)

    def read(self, method: str, target: str) -> tuple[int, list[tuple[str, str]], bytes]:
        if not self.permits(method, target):
            raise ValueError("Inspection target denied")
        connection = http.client.HTTPConnection("127.0.0.1", self.upstream_port, timeout=60)
        try:
            # Incoming headers are intentionally never copied. In particular:
            # Host, Cookie, Authorization, Forwarded, and inspection credentials.
            connection.request(method, target, headers={
                "X-DTOS-Inspection": "deterministic",
                "X-DTOS-Inspection-Auth": self.token,
                "Accept-Encoding": "identity",
                "Connection": "close",
            })
            response = connection.getresponse()
            headers = response.getheaders()
            location = response.getheader("Location")
            if 300 <= response.status < 400 and not (
                location and self.permits("GET", location)
            ):
                raise ValueError("Inspection redirect denied")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("Encoded upstream response denied")
            length = response.getheader("Content-Length")
            if length is not None and (not length.isdigit() or int(length) > MAX_BODY):
                raise ValueError("Inspection response exceeds bound")
            body = response.read(MAX_BODY + 1)
            if len(body) > MAX_BODY:
                raise ValueError("Inspection response exceeds bound")
            if method == "GET" and length is not None and int(length) != len(body):
                raise ValueError("Incomplete inspection response")
            # Scan *all* upstream headers before releasing any response, even
            # headers not included in the tiny outward allowlist.
            if not self.clean(body) or not self.clean(json.dumps(headers).encode()):
                raise ValueError("Inspection response rejected")
            allowed = [(key, value) for key, value in headers if key.lower() in RESPONSE_HEADERS]
            if location and 300 <= response.status < 400:
                allowed.append(("Location", location))
            if any("\r" in value or "\n" in value for _, value in allowed):
                raise ValueError("Invalid upstream headers")
            return response.status, allowed, body
        finally:
            connection.close()


class RelayServer(HTTPServer):
    def __init__(self, port: int, policy: RelayPolicy):
        self.policy = policy
        self.counts = {"completed": 0, "denied": 0, "failed": 0}
        super().__init__(("127.0.0.1", port), RelayHandler)
        self.timeout = 0.5

    def handle_error(self, request, client_address):
        # Never emit an exception/traceback containing a request or credentials.
        self.counts["failed"] += 1


class RelayHandler(BaseHTTPRequestHandler):
    server: RelayServer

    def log_message(self, *_args):
        pass

    def send_error(self, code, message=None, explain=None):
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def do_GET(self):
        if (
            not self.server.policy.permits(self.command, self.path)
            or self.headers.get("Transfer-Encoding") is not None
            or self.headers.get("Content-Length", "0") != "0"
            or self.headers.get("Upgrade") is not None
        ):
            self.server.counts["denied"] += 1
            self.send_error(403)
            return
        try:
            status, headers, body = self.server.policy.read(self.command, self.path)
        except Exception:
            self.server.counts["failed"] += 1
            self.send_error(502)
            return
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.server.counts["completed"] += 1
        self.close_connection = True

    do_HEAD = do_GET

    def setup(self):
        super().setup()
        self.connection.settimeout(65)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--lifetime", type=int, default=2400)
    args = parser.parse_args()
    try:
        if not 1 <= args.port <= 65535 or not 1 <= args.lifetime <= 3600:
            raise ValueError("Invalid relay bounds")
        if args.inventory.stat().st_size > 1024 * 1024:
            raise ValueError("Invalid inventory size")
        policy = RelayPolicy(
            json.loads(args.inventory.read_text(encoding="utf-8")),
            os.environ.pop("DTOS_INSPECTION_AUTH_TOKEN", ""), int(os.environ["PORT"]),
        )
        stopped = False

        def stop(_signal, _frame):
            nonlocal stopped
            stopped = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        with RelayServer(args.port, policy) as server:
            deadline = time.monotonic() + args.lifetime
            print(json.dumps({"relay": "ready", "loopback_only": True}), flush=True)
            while not stopped and time.monotonic() < deadline:
                server.handle_request()
            print(json.dumps({"relay": "closed", "counts": server.counts}), flush=True)
        return 0
    except Exception:
        print('{"relay":"failed_closed"}', flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
