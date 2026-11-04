"""Provider pipeline and timing instrumentation."""
from __future__ import annotations

from time import perf_counter
from typing import Any, Callable


class IntelligencePipeline:
    def __init__(self) -> None:
        self.timings_ms: dict[str, float] = {}

    def run(self, name: str, provider: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        started = perf_counter()
        result = provider(*args, **kwargs)
        self.timings_ms[name] = round((perf_counter() - started) * 1000, 3)
        return result
