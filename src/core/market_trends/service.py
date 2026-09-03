"""Bounded Step 7 trend reads over Step 2 sparse global market memory."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from statistics import mean, pstdev
from threading import RLock
from typing import Any

from .models import (
    TREND_METHOD_VERSION, LeagueLiquidity, MarketTrend, TrendCheckpoint,
    TrendDirection,
)

_MILESTONES = {
    "season_start": "season_start",
    "preseason": "preseason",
    "nfl_draft": "nfl_draft",
    "midseason": "midseason",
    "last_material_event": "material_market_state",
}
_NO_EVIDENCE_BOUNDARY = "1970-01-01T00:00:00+00:00"


def _stamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class MarketTrendService:
    """Produces deterministic derived intelligence; it never owns or writes history."""

    def __init__(self, reader: Any, *, cache_limit: int = 512) -> None:
        self.reader = reader
        self.cache_limit = max(1, cache_limit)
        self._cache: OrderedDict[tuple[Any, ...], MarketTrend] = OrderedDict()
        self._lock = RLock()

    @staticmethod
    def _direction(values: list[float]) -> tuple[TrendDirection, float | None, float | None]:
        if len(values) < 2:
            return TrendDirection.INSUFFICIENT, None, None
        magnitude = round(values[-1] - values[0], 2)
        average = max(abs(mean(values)), 1.0)
        changes = [
            (current - previous) / max(abs(previous), 1.0) * 100
            for previous, current in zip(values, values[1:])
        ]
        volatility = round(pstdev(changes), 2) if len(changes) >= 2 else None
        material = max(25.0, average * 0.03)
        if volatility is not None and volatility >= 12:
            direction = TrendDirection.VOLATILE
        elif abs(magnitude) < material:
            direction = TrendDirection.STABLE if len(values) >= 3 else TrendDirection.INSUFFICIENT
        else:
            direction = TrendDirection.RISING if magnitude > 0 else TrendDirection.FALLING
        return direction, magnitude, volatility

    @staticmethod
    def _confidence(rows: list[dict[str, Any]], latest_age: int | None) -> tuple[int, str, str]:
        if len(rows) < 2:
            return 0, "unavailable", "insufficient"
        providers = len({provider for row in rows for provider in row["providers"]})
        span = (_stamp(rows[-1]["observed_at"]) - _stamp(rows[0]["observed_at"])).days
        score = min(90, 20 + min(len(rows), 8) * 7 + min(providers, 3) * 6 + min(max(span, 0), 180) // 12)
        if latest_age is not None and latest_age > 180:
            score = max(15, score - 25)
        label = "high" if score >= 75 else "medium" if score >= 50 else "low"
        coverage = "strong" if len(rows) >= 6 and providers >= 2 else "partial"
        return int(score), label, coverage

    def trend_for_asset(
        self, asset_id: str, current_value: float | int | None, *, league_id: str | None = None,
        as_of: str | None = None, generation: str = "current", compact: bool = False,
        evidence: dict[str, Any] | None = None, current_evidence_at: str | None = None,
    ) -> dict[str, Any]:
        explicit_boundary = as_of is not None
        query_boundary = as_of or "9999-12-31T23:59:59+00:00"
        try:
            _stamp(query_boundary)
        except (AttributeError, TypeError, ValueError):
            query_boundary = "9999-12-31T23:59:59+00:00"
        if explicit_boundary:
            cache_key = (
                asset_id, current_value, league_id, query_boundary, generation,
                TREND_METHOD_VERSION,
            )
            with self._lock:
                cached = self._cache.get(cache_key)
                if cached is not None:
                    self._cache.move_to_end(cache_key)
                    return cached.public(compact=compact)
        source = evidence or self.reader.market_trend_evidence(
            asset_ids=(asset_id,), league_id=league_id, as_of=query_boundary,
        ).get(asset_id, {})
        observations = list(source.get("observations") or ())
        if explicit_boundary:
            boundary = query_boundary
        else:
            candidates = [
                str(row["observed_at"]) for row in observations if row.get("observed_at")
            ]
            if current_evidence_at:
                try:
                    _stamp(current_evidence_at)
                    candidates.append(current_evidence_at)
                except (AttributeError, TypeError, ValueError):
                    pass
            boundary = max(candidates, key=_stamp) if candidates else _NO_EVIDENCE_BOUNDARY
        cache_key = (
            asset_id, current_value, league_id, boundary, generation,
            TREND_METHOD_VERSION,
        )
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._cache.move_to_end(cache_key)
                return cached.public(compact=compact)
        # Current truth is used as the endpoint, never written back or substituted for history.
        historical_values = [float(row["value"]) for row in observations]
        values = historical_values + ([float(current_value)] if current_value is not None else [])
        direction, magnitude, volatility = self._direction(values)
        latest_age = None
        if observations:
            latest_age = max(0, (_stamp(boundary) - _stamp(observations[-1]["observed_at"])).days)
        score, confidence, coverage = self._confidence(observations, latest_age)
        material = max(25.0, abs(values[0]) * 0.03) if values else 25.0
        ratio = abs(magnitude or 0) / material
        band = "unavailable" if magnitude is None else "small" if ratio < 1 else "moderate" if ratio < 3 else "large"
        volatility_band = "unavailable" if volatility is None else "stable" if volatility < 4 else "moving" if volatility < 12 else "swinging"
        checkpoints = tuple(TrendCheckpoint(
            observation_id=str(row["observation_id"]), observed_at=str(row["observed_at"]),
            value=float(row["value"]), confidence=int(row["confidence"]),
            reason_codes=tuple(row.get("reason_codes") or ()),
            provider_count=len(row.get("providers") or ()),
            related_asset_ids=tuple(row.get("related_asset_ids") or ()),
        ) for row in observations)
        milestones: dict[str, dict[str, Any]] = {}
        for label, reason in _MILESTONES.items():
            matching = [row for row in observations if reason in row.get("reason_codes", ())]
            if matching and current_value is not None:
                selected = matching[-1]
                milestones[label] = {
                    "checkpoint_id": selected["observation_id"],
                    "observed_at": selected["observed_at"], "value": selected["value"],
                    "change": round(float(current_value) - float(selected["value"]), 2),
                }
        liquidity = source.get("liquidity")
        league_liquidity = LeagueLiquidity(**liquidity) if liquidity else None
        event_context = tuple({
            "checkpoint_id": row["observation_id"], "observed_at": row["observed_at"],
            "reason_codes": tuple(row.get("reason_codes") or ()),
            "relationship": "coincided_with",
        } for row in observations if row.get("reason_codes"))
        trend = MarketTrend(
            asset_id=asset_id, current_value=float(current_value) if current_value is not None else None,
            as_of=boundary, direction=direction, magnitude=magnitude, magnitude_band=band,
            horizon=(f"{max(0, (_stamp(boundary)-_stamp(observations[0]['observed_at'])).days)}_days" if observations else None),
            confidence=confidence, confidence_score=score, evidence_coverage=coverage,
            checkpoint_count=len(observations), latest_checkpoint_age_days=latest_age,
            observed_high=max(historical_values) if historical_values else None,
            observed_low=min(historical_values) if historical_values else None,
            volatility=volatility, volatility_band=volatility_band, milestones=milestones,
            event_context=event_context, checkpoints=checkpoints,
            league_liquidity=league_liquidity,
            provenance={"source": "step_2_global_market_memory", "provider_calls": 0,
                        "raw_history_scans": 0, "sparse_observations": True},
        )
        with self._lock:
            self._cache[cache_key] = trend
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self.cache_limit:
                self._cache.popitem(last=False)
        return trend.public(compact=compact)

    def summaries(
        self, assets: list[dict[str, Any]], *, league_id: str | None,
        as_of: str | None, generation: str,
        current_boundaries: dict[str, str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        ids = tuple(str(row["asset_id"]) for row in assets[:250])
        query_boundary = as_of or "9999-12-31T23:59:59+00:00"
        evidence = self.reader.market_trend_evidence(
            asset_ids=ids, league_id=league_id, as_of=query_boundary,
        )
        return {asset_id: self.trend_for_asset(
            asset_id, next((row.get("values", {}).get("market_value") for row in assets if str(row["asset_id"]) == asset_id), None),
            league_id=league_id, as_of=as_of, generation=generation, compact=True,
            evidence=evidence.get(asset_id),
            current_evidence_at=(current_boundaries or {}).get(asset_id),
        ) for asset_id in ids}

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
