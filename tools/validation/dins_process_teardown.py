"""Cheap Linux PID1 adoption proof: browser lifecycle only, not DINS acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil


def main() -> int:
    if sys.platform != "linux" or os.environ.get("RENDER"):
        raise RuntimeError("Isolated Linux process proof only")
    if "--worker" in sys.argv:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content("<html><body>Lifecycle only</body></html>")
                page.close()
            finally:
                browser.close()
        if psutil.Process().children(recursive=True):
            raise AssertionError("Browser worker retained descendants")
        return 0
    for _ in range(3):
        subprocess.run([sys.executable, "-m", "tools.validation.dins_process_teardown", "--worker"],
                       check=True, start_new_session=True, timeout=30)
    deadline = time.monotonic() + 2
    while psutil.Process().children(recursive=True) and time.monotonic() < deadline:
        time.sleep(.05)
    rows = []
    for process in psutil.Process().children(recursive=True):
        rows.append({"pid": process.pid, "name": process.name(), "status": process.status(),
                     "rss_bytes": process.memory_info().rss, "parent_pid": process.ppid()})
    expected = "--diagnose-pid1" in sys.argv
    passed = (os.getpid() == 1 and bool(rows) and all(
        row["status"] == psutil.STATUS_ZOMBIE and row["rss_bytes"] == 0 for row in rows
    )) if expected else not rows
    result = {"diagnostic_only": True, "pid": os.getpid(), "parent_pid": os.getppid(),
              "mode": "diagnose_pid1" if expected else "require_clean_teardown",
              "children": rows, "passed": passed}
    destination = Path("/output") / ("pid1-diagnosis.json" if expected else "init-teardown.json")
    destination.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
