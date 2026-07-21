"""Start, smoke-test, and deterministically stop a tracked DTOS server."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.platform.validation.lifecycle import TrackedServer  # noqa: E402


def main() -> int:
    server = None
    failure = None
    with tempfile.TemporaryFile() as log:
        try:
            server = TrackedServer.start(REPOSITORY_ROOT, log)
            server.wait_until_ready()
            print(f"Tracked validation server PID {server.process.pid} owns port {server.port}.")
            subprocess.run(
                [sys.executable, "tools/validation/smoke_http.py", "--base-url", f"http://127.0.0.1:{server.port}"],
                cwd=REPOSITORY_ROOT,
                check=True,
            )
        except Exception as exc:
            failure = exc
        finally:
            if server is not None:
                try:
                    result = server.cleanup()
                    print(f"Validation server PID {result.pid} stopped via {result.outcome} shutdown; port {result.port} released.")
                except Exception as cleanup_exc:
                    if failure is None:
                        failure = cleanup_exc
                    else:
                        failure = RuntimeError(f"Validation failed: {failure}; cleanup also failed: {cleanup_exc}")
            if failure is not None:
                log.seek(0)
                output = log.read().decode(errors="replace")
                raise RuntimeError(f"HTTP validation failed: {failure}\nServer log:\n{output[-8000:]}") from failure
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
