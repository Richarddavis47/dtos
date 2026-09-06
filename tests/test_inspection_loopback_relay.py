"""Real loopback transport proof with synthetic credentials, no production access."""
import base64
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from tools.inspection.loopback_relay import RelayPolicy, RelayServer, valid_target

TOKEN = "fixture-only-inspection-credential-not-a-production-secret"


@contextmanager
def running(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
        if thread.is_alive():
            raise AssertionError("Relay thread survived teardown")


class Upstream(BaseHTTPRequestHandler):
    received = []

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.received.append((self.path, dict(self.headers)))
        content = b"<html>unchanged complete DOM</html>"
        status = 200
        if self.path == "/leak":
            content = TOKEN.encode()
        if self.path == "/encoded-leak":
            content = base64.b64encode(TOKEN.encode())
        if self.path == "/redirect":
            status = 302
        self.send_response(status)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Type", "text/html")
        self.send_header("X-Request-ID", "fixture-request")
        self.send_header("Content-Security-Policy", "default-src 'self'")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Set-Cookie", "fixture=never-forward")
        if self.path == "/header-leak":
            self.send_header("X-Secret", TOKEN)
        if self.path == "/redirect":
            self.send_header("Location", "http://untrusted.invalid/")
        if self.path == "/compressed":
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    do_HEAD = do_GET


class InspectionRelayTests(unittest.TestCase):
    def setUp(self):
        Upstream.received = []

    def test_exact_policy_denies_ambiguous_or_mutating_targets(self):
        policy = RelayPolicy(["/teams/4", "/api/inspect/site-map"], TOKEN, 10000)
        for method in ("POST", "PUT", "DELETE", "PATCH", "CONNECT", "OPTIONS"):
            self.assertFalse(policy.permits(method, "/teams/4"))
        for target in ("/teams/4?league_id=other", "//host/teams/4", "http://host/teams/4",
                       "/teams/../teams/4", "/teams/%34", "/teams\\4", "/teams/4#fragment",
                       "/teams/4\r\nHeader:value", "/sync", "/transactions/refresh"):
            self.assertFalse(policy.permits("GET", target), target)
        self.assertTrue(policy.permits("HEAD", "/teams/4"))
        for path in ("/api/account/leagues", "/account/sign-out", "/api/admin/rebuild"):
            self.assertFalse(valid_target(path))
        self.assertTrue(valid_target("/history/franchise/123%3Afranchise%3A4"))

    def test_invalid_local_configuration_fails_closed(self):
        for targets, token, port in (([], TOKEN, 10000), (["//evil"], TOKEN, 10000),
                                      (["/"], "", 10000), (["/"], TOKEN, 0)):
            with self.assertRaises(ValueError):
                RelayPolicy(targets, token, port)

    def test_required_account_form_views_are_read_only_not_submissions(self):
        targets = ["/account", "/account/create", "/account/recover", "/account/sleeper",
                   "/account/sign-in", "/account/leagues"]
        policy = RelayPolicy(targets, TOKEN, 10000)
        for target in targets:
            self.assertTrue(policy.permits("GET", target))
            self.assertFalse(policy.permits("POST", target))
        self.assertFalse(policy.permits("GET", "/account/sign-out"))

    def test_real_transport_identity_headers_and_teardown(self):
        with running(HTTPServer(("127.0.0.1", 0), Upstream)) as upstream:
            policy = RelayPolicy(["/teams/4"], TOKEN, upstream.server_port)
            with running(RelayServer(0, policy)) as relay:
                self.assertEqual(relay.server_address[0], "127.0.0.1")
                connection = http.client.HTTPConnection("127.0.0.1", relay.server_port)
                connection.request("GET", "/teams/4", headers={
                    "Authorization": "incoming-do-not-forward", "Cookie": "not-forwarded",
                    "X-DTOS-Inspection-Auth": "attacker", "Host": "untrusted.invalid",
                })
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"<html>unchanged complete DOM</html>")
                self.assertEqual(response.getheader("X-Request-ID"), "fixture-request")
                self.assertEqual(response.getheader("Content-Security-Policy"), "default-src 'self'")
                self.assertEqual(response.getheader("Cross-Origin-Resource-Policy"), "same-origin")
                self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
                self.assertIsNone(response.getheader("Set-Cookie"))
                self.assertNotIn(TOKEN, json.dumps(response.getheaders()))
                connection.close()
                sent = Upstream.received[0][1]
                self.assertEqual(sent["X-DTOS-Inspection-Auth"], TOKEN)
                self.assertEqual(sent["X-DTOS-Inspection"], "deterministic")
                self.assertNotIn("Authorization", sent)
                self.assertNotIn("Cookie", sent)
                self.assertEqual(sent["Host"], f"127.0.0.1:{upstream.server_port}")
                port = relay.server_port
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            with self.assertRaises(OSError):
                connection.request("GET", "/teams/4")
            connection.close()

    def test_no_upstream_call_on_rejected_request(self):
        with running(HTTPServer(("127.0.0.1", 0), Upstream)) as upstream:
            with running(RelayServer(0, RelayPolicy(["/teams/4"], TOKEN, upstream.server_port))) as relay:
                for method, path, headers in (
                    ("POST", "/teams/4", {}), ("GET", "/private", {}),
                    ("GET", "/teams/4", {"Content-Length": "5"}),
                    ("GET", "/teams/4", {"Upgrade": "websocket"}),
                ):
                    connection = http.client.HTTPConnection("127.0.0.1", relay.server_port)
                    connection.request(method, path, headers=headers)
                    response = connection.getresponse()
                    self.assertGreaterEqual(response.status, 400)
                    self.assertEqual(response.read(), b"")
                    connection.close()
            self.assertEqual(Upstream.received, [])

    def test_head_preserves_length_without_body(self):
        with running(HTTPServer(("127.0.0.1", 0), Upstream)) as upstream:
            with running(RelayServer(0, RelayPolicy(["/teams/4"], TOKEN, upstream.server_port))) as relay:
                connection = http.client.HTTPConnection("127.0.0.1", relay.server_port)
                connection.request("HEAD", "/teams/4")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"")
                self.assertEqual(int(response.getheader("Content-Length")), len(b"<html>unchanged complete DOM</html>"))
                connection.close()

    @unittest.skipUnless(hasattr(signal, "SIGALRM"), "Linux hard-deadline execution proof")
    def test_cli_deadline_interrupts_stalled_client_and_removes_listener(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            path.write_text('["/teams/4"]')
            with socket.socket() as available:
                available.bind(("127.0.0.1", 0))
                port = available.getsockname()[1]
            process = subprocess.Popen([
                sys.executable, "-m", "tools.inspection.loopback_relay", "--inventory", str(path),
                "--port", str(port), "--lifetime", "2",
            ], env=dict(os.environ, DTOS_INSPECTION_AUTH_TOKEN=TOKEN, PORT="9"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(json.loads(process.stdout.readline())["relay"], "ready")
                with socket.create_connection(("127.0.0.1", port)) as client:
                    client.sendall(b"GET /teams/4 HTTP/1.1\r\n")  # Deliberately unfinished headers.
                    output, error = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0)
                self.assertEqual(json.loads(output)["relay"], "closed")
                self.assertNotIn(TOKEN, output + error)
                with self.assertRaises(OSError):
                    socket.create_connection(("127.0.0.1", port), timeout=1)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_secret_leaks_redirects_and_encoding_rejected_before_headers(self):
        paths = ["/leak", "/encoded-leak", "/header-leak", "/redirect", "/compressed"]
        with running(HTTPServer(("127.0.0.1", 0), Upstream)) as upstream:
            with running(RelayServer(0, RelayPolicy(paths, TOKEN, upstream.server_port))) as relay:
                for path in paths:
                    connection = http.client.HTTPConnection("127.0.0.1", relay.server_port)
                    connection.request("GET", path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 502)
                    self.assertEqual(response.read(), b"")
                    self.assertNotIn(TOKEN, json.dumps(response.getheaders()))
                    connection.close()

    def test_response_memory_bound_is_fail_closed_not_truncated_success(self):
        with running(HTTPServer(("127.0.0.1", 0), Upstream)) as upstream:
            policy = RelayPolicy(["/teams/4"], TOKEN, upstream.server_port)
            with patch("tools.inspection.loopback_relay.MAX_BODY", 5):
                with self.assertRaises(ValueError):
                    policy.read("GET", "/teams/4")

    def test_public_artifact_identity_does_not_bypass_private_capture_transport(self):
        from tools.inspection.capture import _interaction_target

        base = "http://127.0.0.1:18769"
        public = "https://dtos.example"
        self.assertEqual(_interaction_target(base, public + "/teams/4?league=1", public), base + "/teams/4?league=1")
        external = "https://sleeper.example/player/4"
        self.assertEqual(_interaction_target(base, external, public), external)
        self.assertEqual(_interaction_target(base, "/teams/4", public), base + "/teams/4")


if __name__ == "__main__":
    unittest.main()
