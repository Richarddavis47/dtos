"""One explicit browser-selection contract for local, CI and Cloud validation."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

EXECUTABLE_ENV = "DTOS_CHROMIUM_EXECUTABLE"


def chromium_executable(playwright) -> str | None:
    """Return an override/fallback, or None to use Playwright's bundled browser.

    Selection happens before launch. Never hide a broken installed browser by
    retrying with a different engine. The Linux Cloud image supplies Chromium;
    Windows and CI normally use Playwright's version-matched installation.
    """
    override = os.environ.get(EXECUTABLE_ENV)
    if override:
        path = Path(override)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError(f"{EXECUTABLE_ENV} is not an executable file: {path}")
        return str(path.resolve())
    if Path(playwright.chromium.executable_path).is_file():
        return None
    if sys.platform.startswith("linux"):
        for name in ("chromium", "chromium-browser"):
            path = shutil.which(name)
            if path:
                return path
    raise RuntimeError(
        "No Chromium available. Run python -m tools.validation.setup_cloud "
        "or python -m playwright install chromium."
    )


def launch_chromium(playwright, **options):
    executable = chromium_executable(playwright)
    print(f"Validation Chromium: {executable or playwright.chromium.executable_path}", flush=True)
    if executable is not None:
        options["executable_path"] = executable
    browser = playwright.chromium.launch(**options)
    print(f"Validation Chromium version: {browser.version}", flush=True)
    return browser


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = launch_chromium(playwright, headless=True)
        try:
            page = browser.new_page()
            page.set_content("<title>DTOS browser preflight</title>")
            if page.title() != "DTOS browser preflight":
                raise RuntimeError("Chromium preflight failed")
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
