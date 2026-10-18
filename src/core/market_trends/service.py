"""Bounded Step 7 trend reads over Step 2 sparse global market memory."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from statistics import mean, pstdev
from threading import RLock
from typing import Any
from math import isfinite
from hashlib import sha256
import json
import re

from .compatibility import comparison_identity, comparison_reasons

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


def _valid_temporal_observation(row: dict[str, Any]) -> bool:
    value = row.get("observed_at")
    if not isinstance(value, str) or not value.strip():
        return False
    # Season/week labels can be accepted by fromisoformat, but are not an
    # observed market instant (for example legacy "2026-W01").
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[T ])", value):
        return False
    try:
        _stamp(value)
    except (TypeError, ValueError):
        return False
    return True


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


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
        current_semantics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current_semantics = current_semantics or {}
        current_evidence_at = current_evidence_at or current_semantics.get("observed_at")
        now = datetime.now(timezone.utc)
        explicit_boundary = as_of is not None
        query_boundary = as_of or "9999-12-31T23:59:59+00:00"
        try:
            _stamp(query_boundary)
        except (AttributeError, TypeError, ValueError):
            query_boundary = _NO_EVIDENCE_BOUNDARY
        revision = (self.reader.observation_generation()
                    if explicit_boundary and evidence is None
                    and hasattr(self.reader, "observation_generation") else None)
        identity = (asset_id, current_value, league_id, generation, TREND_METHOD_VERSION,
                    current_evidence_at, repr(current_semantics), revision, now.date().isoformat())
        if explicit_boundary:
            cache_key = (*identity, query_boundary)
            with self._lock:
                cached = self._cache.get(cache_key)
                if cached is not None and evidence is None:
                    self._cache.move_to_end(cache_key)
                    return cached.public(compact=compact)
        source = evidence if evidence is not None else self.reader.market_trend_evidence(
            asset_ids=(asset_id,), league_id=league_id, as_of=query_boundary,
        ).get(asset_id, {})
        raw_observations = list(source.get("observations") or ())
        observations = sorted(
            (row for row in raw_observations if _valid_temporal_observation(row)),
            key=lambda row: (_stamp(row["observed_at"]), str(row.get("observation_id") or "")),
        )
        invalid_temporal_count = len(raw_observations) - len(observations)
        admission_boundary = min(now, _stamp(query_boundary))
        observations = [row for row in observations
                            if _stamp(row["observed_at"]) <= admission_boundary
                            and (not row.get("known_at") or (
                                _valid_temporal_observation({"observed_at": row["known_at"]})
                                and _stamp(row["known_at"]) <= admission_boundary))
                            and row.get("asset_id", asset_id) == asset_id
                            and _number(row.get("value"))]
        if explicit_boundary:
            boundary = query_boundary
        else:
            candidates = [
                str(row["observed_at"]) for row in observations if row.get("observed_at")
            ]
            if current_evidence_at:
                try:
                    _stamp(current_evidence_at)
                    if _stamp(current_evidence_at) <= now:
                        candidates.append(current_evidence_at)
                except (AttributeError, TypeError, ValueError):
                    pass
            boundary = max(candidates, key=_stamp) if candidates else _NO_EVIDENCE_BOUNDARY
        fingerprint = sha256(json.dumps(source, sort_keys=True, default=str).encode()).hexdigest()
        cache_key = ((*identity, boundary, fingerprint)
                     if not explicit_boundary or evidence is not None else (*identity, boundary))
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._cache.move_to_end(cache_key)
                return cached.public(compact=compact)
        reasons = comparison_reasons(observations)
        by_time: dict[datetime, float] = {}
        by_generation: dict[tuple[Any, ...], float] = {}
        for row in observations:
            stamp, value = _stamp(row["observed_at"]), float(row["value"])
            if not isfinite(value) or (stamp in by_time and by_time[stamp] != value):
                reasons += ("TIME_ORDER_UNAVAILABLE",)
            by_time[stamp] = value
            source_ids = row.get("source_generations") or {}
            if row.get("source_generation_conflict"):
                reasons += ("CONFLICTING_SOURCE_GENERATION",)
            if source_ids and not all(source_ids.values()):
                reasons += ("COMPARABLE_HISTORY_UNAVAILABLE",)
            if source_ids and all(source_ids.values()):
                key = tuple(sorted(source_ids.items()))
                if key in by_generation and by_generation[key] != value:
                    reasons += ("CONFLICTING_SOURCE_GENERATION",)
                by_generation[key] = value
        reasons = tuple(dict.fromkeys(reasons))
        # A bare current number has no proven comparison identity. Keep it as
        # current evidence, but never silently append it to a historical series.
        current_comparable = bool(
            observations and _number(current_value) and current_evidence_at
            and _valid_temporal_observation({"observed_at": current_evidence_at})
            and _stamp(observations[-1]["observed_at"]) < _stamp(current_evidence_at) <= min(now, _stamp(boundary))
            and current_semantics.get("asset_id", asset_id) == asset_id
            and comparison_identity(current_semantics or {}) is not None
            and comparison_identity(current_semantics or {}) == comparison_identity(observations[-1])
            and not comparison_reasons([observations[-1], current_semantics or {}])
        )
        current_sources = current_semantics.get("source_generations") or {}
        if current_sources and all(current_sources.values()):
            key = tuple(sorted(current_sources.items()))
            if key in by_generation and by_generation[key] != current_value:
                current_comparable = False
        historical_values = [] if reasons else [float(row["value"]) for row in observations]
        values = historical_values + ([float(current_value)] if current_comparable and not reasons else [])
        direction, magnitude, volatility = self._direction(values)
        if reasons:
            direction = TrendDirection.NOT_COMPARABLE
        latest_age = None
        if observations:
            latest_age = max(0, ((_stamp(boundary) if explicit_boundary else now)
                                 - _stamp(observations[-1]["observed_at"])).days)
        score, confidence, coverage = self._confidence(observations, latest_age)
        if reasons:
            score, confidence, coverage = 0, "unavailable", "not_comparable"
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
            if matching and current_comparable and not reasons:
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
            asset_id=asset_id, current_value=float(current_value) if _number(current_value) else None,
            as_of=boundary, direction=direction, magnitude=magnitude, magnitude_band=band,
            horizon=(f"{max(0, (_stamp(boundary)-_stamp(observations[0]['observed_at'])).days)}_days" if observations else None),
            confidence=confidence, confidence_score=score, evidence_coverage=coverage,
            checkpoint_count=len(observations), latest_checkpoint_age_days=latest_age,
            observed_high=max(historical_values) if historical_values else None,
            observed_low=min(historical_values) if historical_values else None,
            volatility=volatility, volatility_band=volatility_band, milestones=milestones,
            event_context=event_context, checkpoints=checkpoints,
            league_liquidity=league_liquidity,
            comparison_reasons=reasons,
            comparison_scope=("historical_to_current" if current_comparable and not reasons
                              else "history_only" if len(historical_values) >= 2 else "unavailable"),
            comparison_start_at=observations[0]["observed_at"] if values else None,
            comparison_units=((observations[0].get("comparison_semantics") or {}).get("value_scale")
                              if values else None),
            comparison_end_at=(current_evidence_at if current_comparable and not reasons
                               else observations[-1]["observed_at"] if values else None),
            current_qualification=(
                ("Current published price compared at its recorded observation time. "
                 + ("Retained/stale source evidence is not a fresh source observation."
                    if current_semantics.get("freshness") == "stale" else
                    "Source update time/freshness is not established."
                    if current_semantics.get("freshness", "unknown") in {"unknown", "unavailable", "mixed"}
                    else "Source freshness remains separately qualified."))
                if current_comparable and not reasons else
                "Current price is not a compatible later observation; any movement shown is history-only."
                if _number(current_value) else
                "Current pricing is unavailable; missing observations do not establish unchanged value."
            ),
            provenance={
                "source": "step_2_global_market_memory", "provider_calls": 0,
                "raw_history_scans": 0, "sparse_observations": True,
                "invalid_temporal_evidence_count": invalid_temporal_count,
                "undated_observations_excluded_from_chronology": invalid_temporal_count,
                "current_endpoint_comparable": current_comparable and not reasons,
                "excluded_evidence_count": len(raw_observations) - len(observations),
                "current_evidence": current_semantics,
            },
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
        current_comparisons: dict[str, dict[str, Any]] | None = None,
        compact: bool = True,
    ) -> dict[str, dict[str, Any]]:
        ids = tuple(str(row["asset_id"]) for row in assets[:250])
        query_boundary = as_of or "9999-12-31T23:59:59+00:00"
        evidence = self.reader.market_trend_evidence(
            asset_ids=ids, league_id=league_id, as_of=query_boundary,
        )
        return {asset_id: self.trend_for_asset(
            asset_id, next((row.get("values", {}).get("market_value") for row in assets if str(row["asset_id"]) == asset_id), None),
            league_id=league_id, as_of=as_of, generation=generation, compact=compact,
            evidence=evidence.get(asset_id),
            current_evidence_at=(current_boundaries or {}).get(asset_id),
            current_semantics=(current_comparisons or {}).get(asset_id),
        ) for asset_id in ids}

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
