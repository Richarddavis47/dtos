"""One-pass GM behavioral aggregation over canonical Steps 4 and 5."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from threading import RLock
from time import perf_counter
from typing import Iterable

from src.core.fois.facts import TradeFact
from src.core.front_office_evidence.models import FrontOfficeEvidenceSummary
from src.core.intelligence.league_scope import league_id_from_data

from .models import (
    GM_BEHAVIOR_METHOD_VERSION, GM_BEHAVIOR_SCHEMA_VERSION,
    BehavioralDimension, GMBehavioralProfile,
)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str,
    ).encode()).hexdigest()


def _confidence(samples: int, coverage: float = 1.0) -> str:
    supported = samples * coverage
    return "high" if supported >= 12 else "medium" if supported >= 5 else "low"


def _tendency(counts: Counter[str], minimum: int = 3) -> str:
    total = sum(counts.values())
    if total < minimum or not counts:
        return "insufficient_evidence"
    ordered = counts.most_common()
    if len(ordered) > 1 and ordered[0][1] == ordered[1][1]:
        return "mixed"
    share = ordered[0][1] / total
    return ordered[0][0] if share >= .6 else "mixed"


class GMBehavioralIntelligenceService:
    """Build bounded league-scoped profiles without history or provider access."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._cache: dict[str, GMBehavioralProfile] = {}
        self._metrics = Counter({
            "profiles_built": 0, "evaluations_consumed": 0,
            "cache_hits": 0, "cache_misses": 0, "provider_calls": 0,
            "raw_history_scans": 0, "aggregation_passes": 0,
        })
        self._last_duration_ms = 0.0

    @staticmethod
    def _dimension(
        key: str, counts: Counter[str], references: tuple[str, ...],
        *, opportunities: int | None = None, observed: int | None = None,
        minimum: int = 3,
    ) -> BehavioralDimension:
        samples = sum(counts.values()) if observed is None else observed
        denominator = opportunities if opportunities is not None else samples
        coverage = round(samples / denominator, 4) if denominator else 0.0
        tendency = _tendency(counts, minimum)
        explanation = (
            f"Observed {samples} supported decisions; dominant evidence is "
            f"{tendency.replace('_', ' ')}."
            if tendency != "insufficient_evidence"
            else f"Only {samples} supported decisions are available; no strong tendency was inferred."
        )
        return BehavioralDimension(
            key, tendency, _confidence(samples, coverage), samples,
            opportunities, coverage, dict(sorted(counts.items())), explanation,
            references[:25],
        )

    def build_profile(
        self, *, evidence: FrontOfficeEvidenceSummary, trades: Iterable[TradeFact],
    ) -> GMBehavioralProfile:
        rows = tuple(sorted(trades, key=lambda row: (row.occurred_at or "", row.transaction_id)))
        cache_key = _digest((evidence.semantic_identity, GM_BEHAVIOR_METHOD_VERSION))
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._metrics["cache_hits"] += 1
                return cached
            self._metrics["cache_misses"] += 1
        started = perf_counter()
        counters: dict[str, Counter[str]] = defaultdict(Counter)
        refs: dict[str, set[str]] = defaultdict(set)
        priced = 0
        midpoint = len(rows) // 2
        for row_index, row in enumerate(rows):
            reference = row.evidence_references[0] if row.evidence_references else f"event:{row.transaction_id}"
            counters["activity"][str(row.season)] += 1
            refs["activity"].add(reference)
            in_count, out_count = len(row.incoming_asset_ids), len(row.outgoing_asset_ids)
            if in_count or out_count:
                direction = "consolidation" if out_count > in_count else "diversification" if in_count > out_count else "balanced"
                counters["package_style"][direction] += 1
                asset_types = (*row.incoming_asset_types, *row.outgoing_asset_types)
                package = (
                    "player_plus_pick" if "player" in asset_types and "pick" in asset_types
                    else "pick_heavy" if asset_types.count("pick") > asset_types.count("player")
                    else "one_for_one" if in_count == out_count == 1
                    else "multi_asset"
                )
                counters["package_preference"][package] += 1
                counters["deal_size"]["large" if in_count + out_count >= 4 else "small"] += 1
                refs["package_style"].add(reference)
                refs["package_preference"].add(reference)
                refs["deal_size"].add(reference)
            for asset_type in row.incoming_asset_types:
                counters["asset_direction"][f"acquire_{asset_type}"] += 1
                if asset_type == "pick":
                    counters["draft_capital"]["acquire_pick"] += 1
            for asset_type in row.outgoing_asset_types:
                counters["asset_direction"][f"dispose_{asset_type}"] += 1
                if asset_type == "pick":
                    counters["draft_capital"]["dispose_pick"] += 1
            for position in row.incoming_positions:
                if position:
                    counters["positional"][f"acquire_{position.upper()}"] += 1
            for position in row.outgoing_positions:
                if position:
                    counters["positional"][f"dispose_{position.upper()}"] += 1
            if row.known_incoming_value is not None and row.known_outgoing_value is not None:
                priced += 1
                ratio = row.known_incoming_value / max(row.known_outgoing_value, 1.0)
                counters["price_behavior"]["value_positive" if ratio > 1.05 else "premium_paid" if ratio < .95 else "balanced"] += 1
                refs["price_behavior"].add(reference)
            if row.competitive_window_at_trade:
                counters["window_behavior"][row.competitive_window_at_trade.casefold()] += 1
                pick_delta = row.incoming_asset_types.count("pick") - row.outgoing_asset_types.count("pick")
                player_delta = row.incoming_asset_types.count("player") - row.outgoing_asset_types.count("player")
                behavior = "acquire_picks" if pick_delta > 0 else "acquire_players" if player_delta > 0 else "balanced"
                counters["window_actions"][f"{row.competitive_window_at_trade.casefold()}:{behavior}"] += 1
                refs["window_behavior"].add(reference)
                refs["window_actions"].add(reference)
            if row.partner_id:
                counters["bilateral_relationships"][row.partner_id] += 1
                refs["bilateral_relationships"].add(reference)
            if row.season_phase:
                counters["timing"][row.season_phase] += 1
                refs["timing"].add(reference)
            era = "recent" if row_index >= midpoint else "earlier"
            if in_count or out_count:
                counters["recency"][f"{era}:{direction}"] += 1
                refs["recency"].add(reference)
            for key in ("asset_direction", "draft_capital", "positional"):
                if counters[key]:
                    refs[key].add(reference)
        dimensions = (
            self._dimension("activity", counters["activity"], tuple(sorted(refs["activity"])), minimum=2),
            self._dimension("asset_direction", counters["asset_direction"], tuple(sorted(refs["asset_direction"]))),
            self._dimension("package_style", counters["package_style"], tuple(sorted(refs["package_style"]))),
            self._dimension("package_preference", counters["package_preference"], tuple(sorted(refs["package_preference"]))),
            self._dimension("deal_size", counters["deal_size"], tuple(sorted(refs["deal_size"]))),
            self._dimension("draft_capital", counters["draft_capital"], tuple(sorted(refs["draft_capital"]))),
            self._dimension("positional", counters["positional"], tuple(sorted(refs["positional"]))),
            self._dimension("price_behavior", counters["price_behavior"], tuple(sorted(refs["price_behavior"])), opportunities=len(rows), observed=priced),
            self._dimension("competitive_window", counters["window_behavior"], tuple(sorted(refs["window_behavior"]))),
            self._dimension("window_dependent_behavior", counters["window_actions"], tuple(sorted(refs["window_actions"]))),
            self._dimension("bilateral_relationships", counters["bilateral_relationships"], tuple(sorted(refs["bilateral_relationships"]))),
            self._dimension("timing", counters["timing"], tuple(sorted(refs["timing"]))),
            self._dimension("recency_change", counters["recency"], tuple(sorted(refs["recency"]))),
        )
        core = {
            "league_id": evidence.league_id, "franchise_id": evidence.franchise_id,
            "gm_id": evidence.gm_id, "source": evidence.semantic_identity,
            "dimensions": [dimension.__dict__ for dimension in dimensions],
            "schema": GM_BEHAVIOR_SCHEMA_VERSION, "method": GM_BEHAVIOR_METHOD_VERSION,
        }
        profile = GMBehavioralProfile(
            evidence.league_id, evidence.franchise_id, evidence.gm_id, len(rows),
            evidence.evaluated_transaction_count,
            rows[0].occurred_at if rows else None, rows[-1].occurred_at if rows else None,
            dimensions, evidence.process_distribution, evidence.outcome_distribution,
            _confidence(evidence.evaluated_transaction_count, evidence.evidence_completeness / 100),
            evidence.evidence_completeness, evidence.evidence_references[:100],
            evidence.semantic_identity, _digest(core), rows[-1].occurred_at if rows else None,
        )
        with self._lock:
            self._cache[cache_key] = profile
            self._metrics["profiles_built"] += 1
            self._metrics["evaluations_consumed"] += len(rows)
            self._metrics["aggregation_passes"] += 1
            self._last_duration_ms = round((perf_counter() - started) * 1000, 3)
        return profile

    def health(self) -> dict[str, object]:
        with self._lock:
            return {
                **dict(self._metrics), "cache_entries": len(self._cache),
                "last_duration_ms": self._last_duration_ms,
                "schema_version": GM_BEHAVIOR_SCHEMA_VERSION,
                "method_version": GM_BEHAVIOR_METHOD_VERSION,
            }


gm_behavioral_intelligence = GMBehavioralIntelligenceService()


def publish_gm_behavioral_intelligence(data: dict, scores: tuple[object, ...]) -> None:
    """Publish bounded completed profiles for authenticated league consumers."""
    league_id = league_id_from_data(data)
    profiles = {
        str(getattr(score, "franchise_id").rsplit(":", 1)[-1]):
        dict(getattr(score, "gm_behavioral_profile"))
        for score in scores
        if getattr(score, "gm_behavioral_profile", None)
        and str(getattr(score, "league_id", "")) == league_id
        and str(getattr(score, "gm_behavioral_profile").get("league_id") or "") == league_id
    }
    data["gm_behavioral_intelligence"] = profiles
