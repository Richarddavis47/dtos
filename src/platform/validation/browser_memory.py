"""Validation-only Node heap policy; never imported by application startup."""
from __future__ import annotations

from collections.abc import Mapping

DEFAULT_NODE_OPTIONS = '--max-old-space-size=256'


def bounded_test_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Budget driver GC within a shared 2 GiB test cgroup, preserving overrides.

    This is V8 old-space, not a total RSS limit. Chromium/Python/native buffers
    remain subject to the unchanged cgroup. No tests or assertions are removed.
    """
    result = dict(environment)
    result.setdefault('NODE_OPTIONS', DEFAULT_NODE_OPTIONS)
    return result
