"""Observable provider reliability used by normalized consensus weighting."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReliabilityState:
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    schema_failures: int = 0
    latency_total_ms: float = 0.0

    @property
    def score(self) -> int:
        if not self.attempts:
            return 60
        success_rate = self.successes / self.attempts
        schema_penalty = min(25, self.schema_failures * 5)
        latency_penalty = min(15, round(self.latency_total_ms / self.attempts / 1000 * 5))
        return max(0, min(100, round(success_rate * 80 + 20 - schema_penalty - latency_penalty)))


class ReliabilityTracker:
    def __init__(self) -> None:
        self._states: dict[str, ReliabilityState] = {}

    def record(self, provider: str, *, success: bool, latency_ms: float, schema_failure: bool = False) -> int:
        state = self._states.setdefault(provider, ReliabilityState())
        state.attempts += 1
        state.successes += int(success)
        state.failures += int(not success)
        state.schema_failures += int(schema_failure)
        state.latency_total_ms += latency_ms
        return state.score

    def score(self, provider: str) -> int:
        return self._states.get(provider, ReliabilityState()).score

    def health(self) -> dict[str, dict[str, int | float]]:
        return {name: {"score": row.score, "attempts": row.attempts, "successes": row.successes, "failures": row.failures, "schema_failures": row.schema_failures, "average_latency_ms": round(row.latency_total_ms / max(row.attempts, 1), 3)} for name, row in self._states.items()}
