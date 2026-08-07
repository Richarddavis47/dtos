"""Canonical, read-only valuation universe assembled from current cached state."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Iterator

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from src.core.valuation.calibration import cached_market_consensus
from src.core.valuation.config import NORMALIZATION_VERSION, VALUATION_SCHEMA_VERSION
from src.core.valuation.models import CalibrationStatus
from src.core.valuation.normalization import normalize_internal, normalize_value, prepare_distribution

UNIVERSE_SCHEMA_VERSION = "1.0"
PROVIDER_NAMES = ("DTOS", "KTC", "FantasyCalc", "DynastyProcess")
LAYER_NAMES = (
    "market_value", "intrinsic_dtos_value", "league_adjusted_value",
    "contender_value", "rebuilder_value", "liquidity_score", "confidence_score",
    "risk_score", "age_curve_score", "provider_consensus", "future_value",
    "current_production_value",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _layer(value: int | float | None, source: str, generated_at: str, confidence: int = 0) -> dict[str, Any]:
    return {
        "value": value,
        "source": source,
        "version": VALUATION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "confidence": max(0, min(100, confidence)),
        "availability": "available" if value is not None else "unavailable",
    }


def _freshness(data: dict[str, Any], state: dict[str, Any], generated_at: str) -> dict[str, Any]:
    statuses = ((data.get("market_data") or {}).get("provider_status") or {})
    refreshes = [str(row.get("last_refresh")) for row in statuses.values() if isinstance(row, dict) and row.get("last_refresh")]
    failures = [name for name, row in statuses.items() if isinstance(row, dict) and row.get("enabled") and row.get("status") not in {"healthy", "waiting"}]
    sleeper_sync = state.get("last_sync") or data.get("players_fetched_at")
    age_hours = None
    if sleeper_sync:
        try:
            observed = datetime.fromisoformat(str(sleeper_sync).replace("Z", "+00:00"))
            observed = observed if observed.tzinfo else observed.replace(tzinfo=timezone.utc)
            age_hours = round(max(0.0, (datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds() / 3600), 2)
        except ValueError:
            age_hours = None
    delayed = age_hours is None or age_hours > 2
    status = "Partial" if failures else "Provider Delayed" if sleeper_sync and delayed else "Current" if sleeper_sync else "Unavailable"
    return {
        "dtos_version": VERSION,
        "build": BUILD_NUMBER,
        "commit": deployment_metadata()["commit"],
        "sleeper_sync_timestamp": sleeper_sync,
        "valuation_timestamp": generated_at,
        "provider_refresh_timestamp": max(refreshes) if refreshes else None,
        "generation_timestamp": generated_at,
        "current_status": status,
        "sleeper_data_age_hours": age_hours,
        "reasons": [f"Provider delayed or failed: {name}" for name in failures] or ([f"Sleeper data is {age_hours} hours old."] if sleeper_sync and delayed else [] if sleeper_sync else ["No successful Sleeper synchronization is available."]),
    }


def _owners(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for team in data.get("teams") or []:
        for player in team.get("players") or []:
            player_id = str(player.get("id") or "")
            if player_id:
                result[player_id] = {
                    "roster_id": int(team.get("roster_id") or 0),
                    "team_name": team.get("team_name"),
                    "owner": team.get("owner"),
                    "roster_slot": player.get("roster_slot"),
                }
    return result


def _provider_context(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, tuple[float, ...]]]:
    providers = ((data.get("market_data") or {}).get("providers") or {})
    distributions = {
        name: prepare_distribution(name, (
            row.get("value") for row in (providers.get(name) or {}).values()
            if isinstance(row, dict) and row.get("value") is not None
        ))
        for name in ("FantasyCalc", "DynastyProcess")
    }
    return providers, distributions


def _provider_rows(
    asset_id: str,
    providers: dict[str, Any],
    distributions: dict[str, tuple[float, ...]],
    provider_status: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for name in PROVIDER_NAMES:
        source_name = "KeepTradeCut" if name == "KTC" else name
        raw = (providers.get(source_name) or {}).get(asset_id)
        raw = raw if isinstance(raw, dict) else {}
        raw_value = _number(raw.get("value"))
        normalized = None
        confidence = int(raw.get("confidence") or 0)
        if raw_value is not None and name in distributions:
            item = normalize_value(name, raw_value, prepared_distribution=distributions[name], updated_at=raw.get("updated_at"), provider_confidence=confidence or 70)
            normalized = item.normalized_value
            confidence = item.confidence_score
        status = provider_status.get(name) or provider_status.get(source_name) or {}
        rows.append({
            "provider": name,
            "raw_value": raw_value,
            "normalized_value": normalized,
            "provider_rank": raw.get("rank"),
            "last_updated": raw.get("updated_at") or status.get("last_refresh"),
            "confidence": confidence,
            "availability": "available" if raw_value is not None else str(status.get("status") or "unavailable"),
            "reason": None if raw_value is not None else status.get("reason") or "No current value is available for this asset.",
            "source_version": NORMALIZATION_VERSION,
        })
    return rows


def _comparison(intrinsic: int | None, market: int | None) -> dict[str, Any]:
    if intrinsic is None or market is None:
        return {"difference_percent": None, "difference_rank": None, "difference_tier": None, "comparison_status": "Unavailable"}
    difference = round((intrinsic - market) * 100 / max(abs(market), 1), 2)
    magnitude = abs(difference)
    status = "No Difference" if magnitude < 2 else "Minor" if magnitude < 10 else "Moderate" if magnitude < 25 else "Major" if magnitude < 50 else "Extreme"
    return {"difference_percent": difference, "difference_rank": None, "difference_tier": status, "comparison_status": status}


class ValuationUniverse:
    """One deterministic identity and valuation record per cached player or pick."""

    def __init__(self, data: dict[str, Any], state: dict[str, Any]) -> None:
        self.data = data
        self.state = state
        self.generated_at = _now()
        self.freshness = _freshness(data, state, self.generated_at)
        self.assets = self._build()
        self.by_id = {row["asset_id"]: row for row in self.assets}
        for row in self.assets:
            if row["asset_type"] == "player":
                self.by_id[str(row["identity"]["sleeper_id"])] = row

    def _build(self) -> list[dict[str, Any]]:
        return list(self.iter_assets())

    def iter_assets(self) -> Iterator[dict[str, Any]]:
        """Yield canonical assets without retaining another complete universe."""
        players = self.data.get("normalized_players") or self.data.get("players") or {}
        owners = _owners(self.data)
        providers, distributions = _provider_context(self.data)
        provider_status = ((self.data.get("market_data") or {}).get("provider_status") or {})
        consensus = cached_market_consensus(self.data.get("market_data") or {}, (str(key) for key in players))
        for player_id, row in sorted(players.items(), key=lambda item: str(item[0])):
            if isinstance(row, dict):
                yield self._player(
                    str(player_id), row, owners.get(str(player_id)),
                    consensus.get(str(player_id)), providers, distributions,
                    provider_status,
                )
        for row in sorted(
            self.data.get("pick_ledger") or [],
            key=lambda item: (
                int(item.get("season") or 0), int(item.get("round") or 0),
                int(item.get("original_roster_id") or 0),
            ),
        ):
            yield self._pick(row)

    @classmethod
    def streaming(cls, data: dict[str, Any], state: dict[str, Any]) -> ValuationUniverse:
        """Create only the lightweight context required for bounded iteration."""
        universe = object.__new__(cls)
        universe.data = data
        universe.state = state
        universe.generated_at = _now()
        universe.freshness = _freshness(data, state, universe.generated_at)
        return universe

    def _player(self, player_id: str, player: dict[str, Any], owner: dict[str, Any] | None, consensus: tuple[int | None, int, CalibrationStatus] | None, providers: dict[str, Any], distributions: dict[str, tuple[float, ...]], provider_status: dict[str, Any]) -> dict[str, Any]:
        market, market_confidence, calibration = consensus or (None, 0, CalibrationStatus.INSUFFICIENT_DATA)
        raw_intrinsic = next((_number(player.get(key)) for key in ("dtos_value", "dynasty_value") if _number(player.get(key)) is not None), None)
        intrinsic = normalize_internal(raw_intrinsic) if raw_intrinsic is not None and raw_intrinsic <= 100 else int(raw_intrinsic) if raw_intrinsic is not None else None
        adjustment_category = {"QB": "Quarterbacks", "RB": "Running Backs", "WR": "Wide Receivers", "TE": "Tight Ends"}.get(str(player.get("position") or "").upper())
        adjustments = ((self.data.get("calibration_state") or {}).get("adjustments") or {})
        multiplier = float(adjustments.get(adjustment_category, adjustments.get("All Assets", 1.0)))
        league_adjusted = round(intrinsic * multiplier) if intrinsic is not None else None
        provider_rows = _provider_rows(player_id, providers, distributions, provider_status)
        if intrinsic is not None:
            provider_rows[0].update({"raw_value": raw_intrinsic, "normalized_value": intrinsic, "confidence": 70, "availability": "available", "reason": None})
        available = [row for row in provider_rows if row["raw_value"] is not None]
        layers = {name: _layer(None, "Unavailable", self.generated_at) for name in LAYER_NAMES}
        layers.update({
            "market_value": _layer(market, "Provider consensus", self.generated_at, market_confidence),
            "intrinsic_dtos_value": _layer(intrinsic, "DTOS existing valuation", self.generated_at, 70 if intrinsic is not None else 0),
            "league_adjusted_value": _layer(league_adjusted, f"DTOS intrinsic value with {adjustment_category or 'All Assets'} model calibration", self.generated_at, 65 if league_adjusted is not None else 0),
            "confidence_score": _layer(market_confidence, "Provider coverage and freshness", self.generated_at, market_confidence),
            "provider_consensus": _layer(market, "Canonical provider consensus", self.generated_at, market_confidence),
            "current_production_value": _layer(_number(player.get("fantasy_points")), "Sleeper cached player metadata", self.generated_at, 50 if player.get("fantasy_points") is not None else 0),
        })
        name = player.get("name") or player.get("full_name") or " ".join(filter(None, (player.get("first_name"), player.get("last_name")))) or player_id
        status = str(player.get("status") or "Unknown")
        return {
            "asset_id": f"player:{player_id}", "asset_type": "player",
            "identity": {"player_name": name, "position": player.get("position"), "nfl_team": player.get("nfl_team") or player.get("team"), "sleeper_id": player_id, "current_owner": owner, "free_agent": owner is None, "draft_pick_description": None, "year": None, "round": None, "projected_slot": None, "rookie_class": player.get("years_exp") == 0, "age": player.get("age"), "status": status},
            "layers": layers, "providers": provider_rows,
            "audit": {"provider_count": len(available), "provider_agreement": None if len(available) < 2 else "measured", "missing_providers": [row["provider"] for row in provider_rows if row["raw_value"] is None], "data_age": self.freshness["provider_refresh_timestamp"], "confidence": market_confidence, "last_changed": max((row["last_updated"] for row in available if row["last_updated"]), default=None), "source_version": UNIVERSE_SCHEMA_VERSION, "inspection_ready": True, "calibration_status": calibration.value},
            "comparison": _comparison(intrinsic, market), "freshness": self.freshness,
        }

    def _pick(self, pick: dict[str, Any]) -> dict[str, Any]:
        from src.core.asset_intelligence.picks.pick_value import dynasty_pick_value

        season, round_number, original = int(pick.get("season") or 0), int(pick.get("round") or 0), int(pick.get("original_roster_id") or 0)
        asset_id = f"pick:{season}:{round_number}:{original}"
        intrinsic = normalize_internal(dynasty_pick_value(pick).score)
        adjustments = ((self.data.get("calibration_state") or {}).get("adjustments") or {})
        pick_category = "Early Picks" if round_number <= 2 else "Late Picks"
        multiplier = float(adjustments.get(pick_category, adjustments.get("Future Picks", adjustments.get("All Assets", 1.0))))
        league_adjusted = round(intrinsic * multiplier)
        layers = {name: _layer(None, "Unavailable", self.generated_at) for name in LAYER_NAMES}
        layers.update({
            "intrinsic_dtos_value": _layer(intrinsic, "DTOS deterministic pick value", self.generated_at, 70),
            "league_adjusted_value": _layer(league_adjusted, f"DTOS deterministic pick value with {pick_category} model calibration", self.generated_at, 65),
            "future_value": _layer(intrinsic, "DTOS deterministic pick value", self.generated_at, 70),
            "confidence_score": _layer(70, "Deterministic pick identity", self.generated_at, 70),
        })
        provider_rows = _provider_rows(asset_id, {}, {}, {})
        provider_rows[0].update({"raw_value": dynasty_pick_value(pick).score, "normalized_value": intrinsic, "confidence": 70, "availability": "available", "reason": None})
        return {
            "asset_id": asset_id, "asset_type": "pick",
            "identity": {"player_name": None, "position": "PICK", "nfl_team": None, "sleeper_id": None, "current_owner": {"roster_id": int(pick.get("current_owner_id") or 0), "team_name": pick.get("current_owner")}, "free_agent": False, "draft_pick_description": f"{season} Round {round_number} ({pick.get('original_team') or f'Roster {original}'})", "year": season, "round": round_number, "projected_slot": pick.get("projected_slot"), "rookie_class": season, "status": "Owned"},
            "layers": layers, "providers": provider_rows,
            "audit": {"provider_count": 1, "provider_agreement": None, "missing_providers": ["KTC", "FantasyCalc", "DynastyProcess"], "data_age": self.freshness["sleeper_sync_timestamp"], "confidence": 70, "last_changed": self.freshness["sleeper_sync_timestamp"], "source_version": UNIVERSE_SCHEMA_VERSION, "inspection_ready": True, "calibration_status": "uncalibrated"},
            "comparison": _comparison(intrinsic, None), "freshness": self.freshness,
        }

    def status(self) -> dict[str, Any]:
        counts = {"players": sum(row["asset_type"] == "player" for row in self.assets), "picks": sum(row["asset_type"] == "pick" for row in self.assets), "total": len(self.assets)}
        return {"schema_version": UNIVERSE_SCHEMA_VERSION, "freshness": self.freshness, "counts": counts, "duplicate_identities": len(self.assets) - len({row["asset_id"] for row in self.assets}), "inspection_ready": all(row["audit"]["inspection_ready"] for row in self.assets)}

    def providers(self) -> dict[str, Any]:
        statuses = ((self.data.get("market_data") or {}).get("provider_status") or {})
        return {"freshness": self.freshness, "providers": [{"provider": name, **(statuses.get("KeepTradeCut" if name == "KTC" else name) or {}), "abstraction_version": UNIVERSE_SCHEMA_VERSION} for name in PROVIDER_NAMES]}

    def csv_bytes(self) -> bytes:
        stream = io.StringIO(newline="")
        fields = ["asset_id", "asset_type", "name", "position", "nfl_team", "sleeper_id", "owner", "status", *LAYER_NAMES, "current_status", "generated_at"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for asset in self.assets:
            identity = asset["identity"]
            writer.writerow({"asset_id": asset["asset_id"], "asset_type": asset["asset_type"], "name": identity["player_name"] or identity["draft_pick_description"], "position": identity["position"], "nfl_team": identity["nfl_team"], "sleeper_id": identity["sleeper_id"], "owner": (identity["current_owner"] or {}).get("team_name") if isinstance(identity["current_owner"], dict) else identity["current_owner"], "status": identity["status"], **{name: asset["layers"][name]["value"] for name in LAYER_NAMES}, "current_status": self.freshness["current_status"], "generated_at": self.generated_at})
        return stream.getvalue().encode("utf-8")
