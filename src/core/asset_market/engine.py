"""Bounded, deterministic Asset Market over canonical cached DTOS contracts."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from typing import Any

from app_metadata import BUILD_NUMBER, VERSION
from src.core.brain import brain_service
from src.core.historical_memory import historical_graph
from src.core.historical_memory.models import DATABASE_MIGRATION_VERSION
from src.core.historical_memory.store import HistoricalStore
from src.core.valuation.universe import LAYER_NAMES, ValuationUniverse

MARKET_SCHEMA_VERSION = "1.0"
SORT_FIELDS = {
    "market": "market_value",
    "intrinsic": "intrinsic_dtos_value",
    "league": "league_adjusted_value",
    "contender": "contender_value",
    "rebuilder": "rebuilder_value",
    "confidence": "confidence_score",
    "risk": "risk_score",
    "liquidity": "liquidity_score",
}


def _layer_value(asset: dict[str, Any], name: str) -> float | None:
    value = ((asset.get("layers") or {}).get(name) or {}).get("value")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _display_name(asset: dict[str, Any]) -> str:
    identity = asset.get("identity") or {}
    return str(
        identity.get("player_name")
        or identity.get("draft_pick_description")
        or asset.get("asset_id")
    )


def _canonical_url(asset: dict[str, Any]) -> str:
    identity = asset.get("identity") or {}
    if asset.get("asset_type") == "pick":
        raw = str(asset["asset_id"]).split(":")
        return f"/picks/PICK-{raw[1]}-R{raw[2]}-ORIG{raw[3]}"
    return f"/players/{identity.get('sleeper_id')}"


def _availability(asset: dict[str, Any]) -> str:
    identity = asset.get("identity") or {}
    if asset.get("asset_type") == "pick":
        return "owned_pick"
    owner = identity.get("current_owner")
    slot = str((owner or {}).get("roster_slot") or "").casefold()
    status = str(identity.get("status") or "").casefold()
    if slot in {"taxi", "reserve", "ir"}:
        return slot
    if owner:
        return "rostered"
    if status in {"inactive", "retired"}:
        return status
    return "day_traders_free_agent"


def _market_id_from_history(canonical_id: str) -> str:
    if canonical_id.startswith("DTOS-P-"):
        return f"player:{canonical_id.removeprefix('DTOS-P-')}"
    if canonical_id.startswith("PICK-"):
        parts = canonical_id.split("-")
        if len(parts) >= 4:
            return ":".join((
                "pick", parts[1], parts[2].removeprefix("R"),
                parts[3].removeprefix("ORIG"),
            ))
    return canonical_id


def _summary(asset: dict[str, Any], brain_asset: dict[str, Any] | None) -> dict[str, Any]:
    identity = asset.get("identity") or {}
    audit = asset.get("audit") or {}
    scores = (brain_asset or {}).get("scores") or {}
    values = {name: _layer_value(asset, name) for name in LAYER_NAMES}
    brain_layers = (brain_asset or {}).get("valuation_layers") or {}
    for name, layer in brain_layers.items():
        if name in values and values[name] is None and isinstance(layer, dict):
            value = layer.get("value")
            values[name] = float(value) if value is not None else None
    owner = identity.get("current_owner") or {}
    historical = bool(identity.get("sleeper_id"))
    return {
        "asset_id": asset["asset_id"],
        "asset_type": asset["asset_type"],
        "display_name": _display_name(asset),
        "position": identity.get("position"),
        "nfl_team": identity.get("nfl_team"),
        "age": identity.get("age"),
        "status": identity.get("status"),
        "owner": owner or None,
        "availability": _availability(asset),
        "rookie": bool(identity.get("rookie_class")),
        "year": identity.get("year"),
        "round": identity.get("round"),
        "values": values,
        "confidence": int(scores.get("confidence", audit.get("confidence") or 0)),
        "agreement": int(scores.get("agreement") or 0),
        "evidence_coverage": int(scores.get("coverage") or 0),
        "provider_coverage": int(audit.get("provider_count") or 0),
        "missing_evidence": list((brain_asset or {}).get("missing_evidence") or []),
        "historical_availability": "available" if historical else "unavailable",
        "canonical_url": _canonical_url(asset),
        "market_detail_url": f"/api/market/assets/{asset['asset_id']}",
    }


class AssetMarket:
    """Immutable compact index with detail hydration delegated to canonical systems."""

    def __init__(
        self, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
    ) -> None:
        started = time.perf_counter()
        self.data = data
        self.state = state
        self.store = store
        self.league_id = league_id
        self.dataset_version = store.dataset_version(league_id)
        universe = ValuationUniverse(data, state)
        brain = brain_service(data)
        self._brain = brain
        self.brain_generation = brain.report.get("generated_at")
        self.generated_at = datetime.now(timezone.utc).isoformat()
        self.assets = tuple(
            _summary(asset, brain.asset(asset["asset_id"]))
            for asset in universe.assets
        )
        self.by_id = {row["asset_id"]: row for row in self.assets}
        self._canonical = {row["asset_id"]: row for row in universe.assets}
        self.build_duration_ms = round((time.perf_counter() - started) * 1000, 3)

    def identity(self, brain_snapshot_id: str | None = None) -> dict[str, Any]:
        identity = {
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "market_schema_version": MARKET_SCHEMA_VERSION,
            "league_id": self.league_id,
            "historical_dataset_version": self.store.dataset_version(self.league_id),
            "market_generation": self.generated_at,
            "brain_generation": self.brain_generation,
            "valuation_generation": (
                (self.data.get("valuation_intelligence") or {}).get("generated_at")
            ),
            "generated_at": self.generated_at,
        }
        if brain_snapshot_id is not None:
            identity["brain_snapshot_id"] = brain_snapshot_id
        return identity

    def health(self) -> dict[str, Any]:
        counts: dict[str, int] = {"total": len(self.assets)}
        for row in self.assets:
            key = row["asset_type"] if row["asset_type"] == "pick" else row["availability"]
            counts[key] = counts.get(key, 0) + 1
        return {
            **self.identity(), "status": "ready", "counts": counts,
            "duplicate_asset_ids": len(self.assets) - len(self.by_id),
            "build_duration_ms": self.build_duration_ms,
            "read_contract": {
                "provider_sync": False, "pagination_before_hydration": True,
                "single_flight": True, "detail_history_hydration": "on_demand",
            },
        }

    def directory(
        self, *, offset: int = 0, limit: int = 50, sort: str = "market",
        direction: str = "desc", asset_type: str | None = None,
        position: str | None = None, availability: str | None = None,
        owner: int | None = None, minimum: float | None = None,
        maximum: float | None = None, age_min: float | None = None,
        age_max: float | None = None, year: int | None = None,
        round_number: int | None = None,
    ) -> dict[str, Any]:
        layer = SORT_FIELDS.get(sort, "market_value")
        rows = [row for row in self.assets if (
            (not asset_type or row["asset_type"] == asset_type)
            and (not position or str(row.get("position") or "").casefold() == position.casefold())
            and (not availability or row["availability"] == availability)
            and (owner is None or int((row.get("owner") or {}).get("roster_id") or 0) == owner)
            and (year is None or row.get("year") == year)
            and (round_number is None or row.get("round") == round_number)
            and (age_min is None or row.get("age") is not None and float(row["age"]) >= age_min)
            and (age_max is None or row.get("age") is not None and float(row["age"]) <= age_max)
            and (minimum is None or row["values"].get(layer) is not None and row["values"][layer] >= minimum)
            and (maximum is None or row["values"].get(layer) is not None and row["values"][layer] <= maximum)
        )]
        reverse = direction.casefold() != "asc"
        rows.sort(
            key=lambda row: (
                row["values"].get(layer) is not None,
                row["values"].get(layer) if row["values"].get(layer) is not None else float("-inf"),
                row["asset_id"],
            ),
            reverse=reverse,
        )
        page = [dict(row, rank=index + 1) for index, row in enumerate(rows)][offset:offset + limit]
        return {
            **self.identity(), "total": len(rows), "offset": offset,
            "limit": limit, "sort": sort, "direction": direction,
            "tie_breaker": "canonical_asset_id", "assets": page,
        }

    def search(self, query: str, limit: int = 50) -> dict[str, Any]:
        needle = query.strip().casefold()
        normalized = needle.replace("-", " ")
        wants_free_agent = "free agent" in normalized
        wants_taxi = "taxi" in normalized
        wants_rookie = "rookie" in normalized
        wants_pick = "pick" in normalized or "draft" in normalized
        position = next((
            value for phrase, value in (
                ("qb", "QB"), ("rb", "RB"), ("wr", "WR"), ("te", "TE"),
                ("quarterback", "QB"), ("running back", "RB"),
                ("wide receiver", "WR"), ("tight end", "TE"),
            ) if phrase in normalized
        ), None)
        ignored = {
            "free", "agent", "agents", "rookie", "rookies", "taxi",
            "pick", "picks", "draft", "quarterback", "quarterbacks",
            "running", "back", "backs", "wide", "receiver", "receivers",
            "tight", "end", "ends",
            "1st", "2nd", "3rd", "4th", "5th", "6th", "7th",
        }
        tokens = tuple(
            token for token in normalized.split() if token and token not in ignored
        )
        rows = [
            row for row in self.assets
            if (not wants_free_agent or row["availability"] == "day_traders_free_agent")
            and (not wants_taxi or row["availability"] == "taxi")
            and (not wants_rookie or row["rookie"])
            and (not wants_pick or row["asset_type"] == "pick")
            and (not position or row.get("position") == position)
            and (not tokens or all(
                token in " ".join((
                    row["asset_id"], row["display_name"],
                    str(row.get("position") or ""), str(row.get("nfl_team") or ""),
                    str((row.get("owner") or {}).get("team_name") or ""),
                    str((row.get("owner") or {}).get("owner") or ""),
                    row["availability"],
                )).casefold()
                for token in tokens
            ))
        ]
        history = (
            historical_graph(self.store, self.league_id, self.data).search(
                query, limit - len(rows),
            )
            if len(rows) < limit else []
        )
        extras = [
            {
                "asset_id": row["canonical_id"], "asset_type": row["result_type"],
                "display_name": row["display_label"], "position": None,
                "nfl_team": None, "owner": None,
                "resolution_status": row["resolution_status"],
                "market_value": None, "contender_value": None,
                "rebuilder_value": None, "confidence": 0,
                "canonical_url": row["canonical_url"],
                "historical_availability": row["historical_availability"],
            }
            for row in history
            if _market_id_from_history(str(row["canonical_id"])) not in self.by_id
        ]
        existing = {row["asset_id"] for row in extras}
        for transaction in self.store.search_transaction_ids(self.league_id, query, limit):
            transaction_id = transaction["source_record_id"]
            source_league = str(
                (transaction.get("payload") or {}).get("source_league_id")
                or self.league_id
            )
            prefix = "TRADE" if transaction["entity_type"] == "trade" else "TX"
            canonical_id = f"{prefix}-{source_league}-{transaction_id}"
            if canonical_id in existing:
                continue
            extras.append({
                "asset_id": canonical_id,
                "asset_type": transaction["entity_type"],
                "display_name": f"{transaction['entity_type'].title()} {transaction_id}",
                "position": None, "nfl_team": None, "owner": None,
                "resolution_status": "resolved", "market_value": None,
                "contender_value": None, "rebuilder_value": None,
                "confidence": 100,
                "canonical_url": (
                    f"/trades/history/{transaction_id}"
                    if transaction["entity_type"] == "trade"
                    else f"/transactions?search={transaction_id}"
                ),
                "historical_availability": "available",
            })
        for team in self.data.get("teams") or []:
            label = str(team.get("team_name") or team.get("owner") or "")
            if needle and needle not in label.casefold() and needle not in str(team.get("owner") or "").casefold():
                continue
            roster_id = int(team.get("roster_id") or 0)
            extras.append({
                "asset_id": f"{self.league_id}:franchise:{roster_id}",
                "asset_type": "team", "display_name": label,
                "position": None, "nfl_team": None,
                "owner": {"roster_id": roster_id, "owner": team.get("owner")},
                "resolution_status": "resolved", "market_value": None,
                "contender_value": None, "rebuilder_value": None,
                "confidence": 100, "canonical_url": f"/teams/{roster_id}",
                "historical_availability": "available",
            })
        compact = [{
            **row, "resolution_status": "resolved",
            "market_value": row["values"].get("market_value"),
            "contender_value": row["values"].get("contender_value"),
            "rebuilder_value": row["values"].get("rebuilder_value"),
        } for row in rows]
        combined = sorted([*compact, *extras], key=lambda row: (
            str(row.get("display_name") or "").casefold(), str(row["asset_id"]),
        ))[:limit]
        return {**self.identity(), "query": query, "count": len(combined), "results": combined}

    def detail(self, asset_id: str, front_office: int | None = None) -> dict[str, Any] | None:
        row = self.by_id.get(asset_id)
        if row is None:
            return None
        brain_asset = self._brain.asset(asset_id)
        decision = self._brain.decision("Asset Market", (asset_id,))
        historical_dataset_version = self.store.dataset_version(self.league_id)
        graph = historical_graph(self.store, self.league_id, self.data)
        if row["asset_type"] == "player":
            raw_id = asset_id.removeprefix("player:")
            history = graph.player_dossier(raw_id)
        else:
            _, season, round_number, original = asset_id.split(":", 3)
            history = graph.pick_dossier(f"PICK-{season}-R{round_number}-ORIG{original}")
        canonical_layers = dict(
            (self._canonical.get(asset_id) or {}).get("layers") or {}
        )
        canonical_layers.update({
            name: {**(canonical_layers.get(name) or {}), **layer}
            for name, layer in ((brain_asset or {}).get("valuation_layers") or {}).items()
            if isinstance(layer, dict)
        })
        return {
            **self.identity(decision.brain_snapshot_id), "asset": row,
            "valuation": brain_asset,
            "value_layers": {
                name: {
                    **layer, "scale": "DTOS 0-10000 normalized scale",
                    "dataset_version": historical_dataset_version,
                    "brain_snapshot_id": decision.brain_snapshot_id,
                    "provider_coverage": row["provider_coverage"],
                    "agreement": row["agreement"],
                    "evidence_categories": [
                        item["name"] for item in (brain_asset or {}).get("categories", [])
                        if item.get("available")
                    ],
                    "missing_evidence": row["missing_evidence"],
                    "limitations": (
                        [] if layer.get("value") is not None
                        else ["This canonical layer is unavailable; no substitute value was used."]
                    ),
                }
                for name, layer in canonical_layers.items()
            },
            "providers": list(
                (self._canonical.get(asset_id) or {}).get("providers") or []
            ),
            "front_office": front_office,
            "recommendation": {
                "action": "Monitor",
                "availability": "advisory_only",
                "primary_reason": "Canonical Brain evidence is available for review; DTOS does not execute transactions.",
                "supporting_evidence": list(decision.recommendation_explanation),
                "counterarguments": list((brain_asset or {}).get("missing_evidence") or []),
                "expected_impact": "Requires Front Office judgment.",
                "confidence": decision.confidence.value,
                "missing_evidence": list((brain_asset or {}).get("missing_evidence") or []),
                "brain_snapshot_id": decision.brain_snapshot_id,
                "decision_provenance": list(decision.decision_provenance),
            },
            "history": history,
        }

    def trending(self, limit: int = 10) -> dict[str, Any]:
        timeline = (self.data.get("valuation_intelligence") or {}).get("timeline") or {}
        comparable = []
        for asset_id, observations in timeline.items():
            if asset_id not in self.by_id or not isinstance(observations, list) or len(observations) < 2:
                continue
            first, last = observations[0], observations[-1]
            start = first.get("confidence")
            end = last.get("confidence")
            if start is None or end is None or first.get("timestamp") == last.get("timestamp"):
                continue
            comparable.append({
                "asset": self.by_id[asset_id], "starting_observation": first,
                "ending_observation": last, "direction": "rising" if end > start else "falling" if end < start else "stable",
                "magnitude": end - start, "measurement": "canonical evidence confidence",
                "reason": "Comparable timestamped Brain observations are available.",
            })
        risers = sorted(comparable, key=lambda row: (row["magnitude"], row["asset"]["asset_id"]), reverse=True)[:limit]
        fallers = sorted(comparable, key=lambda row: (row["magnitude"], row["asset"]["asset_id"]))[:limit]
        available = bool(comparable)
        unavailable = None if available else "At least two timestamped comparable canonical Brain observations are required."
        return {
            **self.identity(), "measurement_window": "oldest_to_latest_retained_brain_observation",
            "minimum_evidence": "two timestamped comparable observations",
            "biggest_risers": risers if available else [],
            "biggest_fallers": fallers if available else [],
            "most_stable": [row for row in comparable if row["magnitude"] == 0][:limit],
            "most_discussed": {"status": "unsupported", "reason": "No verified discussion-data provider is configured."},
            "availability": "available" if available else "unavailable",
            "unavailable_reason": unavailable,
        }


class AssetMarketCache:
    """Single-flight last-valid cache keyed by every canonical input identity."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._key: str | None = None
        self._store_identity: str | None = None
        self._market: AssetMarket | None = None
        self.build_count = 0
        self.hits = 0
        self.last_error: str | None = None
        self.last_miss_reason: str | None = None

    @staticmethod
    def store_identity(store: HistoricalStore) -> str:
        """Return a private instance/durable-generation cache namespace."""
        payload = {
            "instance": id(store),
            "database_uuid": store.database_uuid(),
            "database_schema": DATABASE_MIGRATION_VERSION,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @classmethod
    def key(
        cls, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
    ) -> tuple[str, str]:
        store_identity = cls.store_identity(store)
        payload = {
            "version": VERSION, "build": BUILD_NUMBER,
            "market_schema": MARKET_SCHEMA_VERSION, "league_id": league_id,
            "store_namespace": store_identity,
            "sync": state.get("last_sync"),
            "brain": (data.get("valuation_intelligence") or {}).get("generated_at"),
            "valuation": (data.get("valuation_intelligence") or {}).get("schema_version"),
        }
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return key, store_identity

    def get(
        self, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
    ) -> AssetMarket:
        try:
            key, store_identity = self.key(data, state, store, league_id)
        except Exception:
            with self._lock:
                if self._market is not None and self._market.store is store:
                    self._key = None
                    self._store_identity = None
                    self._market = None
            raise
        if key == self._key and self._market is not None:
            self.hits += 1
            return self._market
        with self._lock:
            if key == self._key and self._market is not None:
                self.hits += 1
                return self._market
            try:
                self.last_miss_reason = (
                    "cold_start" if self._market is None
                    else "canonical_market_inputs_changed"
                )
                market = AssetMarket(data, state, store, league_id)
            except Exception as exc:
                self.last_error = str(exc)
                if (
                    self._market is not None
                    and self._store_identity == store_identity
                ):
                    return self._market
                raise
            self._market, self._key = market, key
            self._store_identity = store_identity
            self.build_count += 1
            self.last_error = None
            return market

    def metrics(self) -> dict[str, Any]:
        return {
            "build_count": self.build_count, "cache_hits": self.hits,
            "cache_key": self._key, "last_error": self.last_error,
            "last_miss_reason": self.last_miss_reason,
            "last_valid_model": self._market is not None,
        }

    def clear(self) -> None:
        with self._lock:
            self._key = None
            self._store_identity = None
            self._market = None


asset_market_cache = AssetMarketCache()


def asset_market(
    data: dict[str, Any], state: dict[str, Any], store: HistoricalStore,
    league_id: str,
) -> AssetMarket:
    return asset_market_cache.get(data, state, store, league_id)
