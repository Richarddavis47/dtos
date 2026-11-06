"""Bounded, per-read sharing of equal immutable strings in league caches.

The JSON format, values and mutable containers are unchanged. In particular,
derived evidence remains in the file and in the full restoration-admission
basis. No reconstruction or provider work is hidden behind a smaller file.
"""
from __future__ import annotations

import json
from typing import Any, TextIO


class _Strings:
    # Pool references are temporary and local to one decode, never sys.intern or
    # an account-crossing cache. Longer strings are usually unique source text.
    MAX_LENGTH = 128
    MAX_ENTRIES = 65_536
    MAX_CHARACTER_BYTES = 16 * 1024 * 1024

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.character_bytes = 0

    def share(self, value: str) -> str:
        if not 1 < len(value) <= self.MAX_LENGTH:
            return value
        existing = self.values.get(value)
        if existing is not None:
            return existing
        cost = 4 * len(value)
        if (len(self.values) < self.MAX_ENTRIES
                and self.character_bytes + cost <= self.MAX_CHARACTER_BYTES):
            self.values[value] = value
            self.character_bytes += cost
        return value

    def value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.share(value)
        if isinstance(value, list):
            for index, child in enumerate(value):
                # Nested objects were already visited by JSON's object_hook.
                if isinstance(child, (str, list)):
                    value[index] = self.value(child)
        return value

    def object(self, value: dict) -> dict:
        for key, child in value.items():
            value[key] = self.value(child)
        return value


def load_cache_json(handle: TextIO) -> Any:
    """Decode once, sharing strings only; discard the pool before publication.

    JSON's normal number, duplicate-key, invalid-input and Unicode behavior is
    retained. Lists and dictionaries always remain independent mutable objects.
    Existing callers own retention, pinned-file admission, scope validation,
    cancellation, actual-results binding and atomic publication.
    """
    strings = _Strings()
    value = json.load(handle, object_hook=strings.object)
    return strings.value(value)
