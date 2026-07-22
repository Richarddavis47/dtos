"""Central application and release metadata for DTOS."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

APPLICATION_NAME = "DTOS"
VERSION = "1.4.0"
BUILD_NUMBER = 1400
RELEASE_CODENAME = "Live Data Platform & Market Integration"

_REPOSITORY_ROOT = Path(__file__).resolve().parent


def _git_output(*arguments: str) -> str | None:
    """Return a Git value when repository metadata is available."""
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=_REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _git_directory() -> Path | None:
    dot_git = _REPOSITORY_ROOT / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        try:
            marker, location = dot_git.read_text(encoding="utf-8").strip().split(":", 1)
        except (OSError, ValueError):
            return None
        if marker.lower() == "gitdir":
            return (_REPOSITORY_ROOT / location.strip()).resolve()
    return None


def _repository_file_metadata() -> tuple[str | None, str | None]:
    """Read branch and commit refs when Git is present but not executable."""
    git_directory = _git_directory()
    if git_directory is None:
        return None, None
    try:
        head = (git_directory / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None, None
    if not head.startswith("ref:"):
        return None, head[:7] or None

    reference = head.removeprefix("ref:").strip()
    branch = reference.rsplit("/", 1)[-1]
    try:
        commit = (git_directory / reference).read_text(encoding="utf-8").strip()
    except OSError:
        commit = None
        try:
            packed_refs = (git_directory / "packed-refs").read_text(encoding="utf-8")
        except OSError:
            packed_refs = ""
        for line in packed_refs.splitlines():
            if line and not line.startswith(("#", "^")):
                candidate, packed_reference = line.split(" ", 1)
                if packed_reference == reference:
                    commit = candidate
                    break
    return branch, commit[:7] if commit else None


def repository_metadata() -> tuple[str, str]:
    """Return the current branch and latest commit, with deployment fallbacks."""
    file_branch, file_commit = _repository_file_metadata()
    branch = (
        os.getenv("DTOS_GIT_BRANCH")
        or os.getenv("RENDER_GIT_BRANCH")
        or _git_output("branch", "--show-current")
        or file_branch
    )
    commit = (
        os.getenv("DTOS_GIT_COMMIT")
        or os.getenv("RENDER_GIT_COMMIT")
        or _git_output("log", "-1", "--pretty=%h %s")
        or file_commit
    )
    return branch or "Unavailable", commit or "Unavailable"
