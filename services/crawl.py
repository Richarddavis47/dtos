"""Fast, public, read-only serialization of the synchronized DTOS league state."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from fastapi.encoders import jsonable_encoder

from app_metadata import VERSION
from services.front_office_intelligence import build_front_office_center
from services.trade_intelligence import build_trade_center
from services.transactions import normalize_transactions
from src.core.intelligence.cache import intelligence_cache
from src.core.valuation import NORMALIZATION_VERSION, VALUATION_SCHEMA_VERSION, build_canonical_consensus, normalize_value

SCHEMA_VERSION = "1.0"
PUBLIC_PAGES = ("/", "/teams", "/front-offices", "/trades", "/transactions", "/matchups", "/picks", "/settings")
CRAWL_ENDPOINTS = {
    "snapshot": "/api/crawl/snapshot",
    "teams": "/api/crawl/teams",
    "front_offices": "/api/crawl/front-offices",
    "trades": "/api/crawl/trades",
    "transactions": "/api/crawl/transactions",
    "matchups": "/api/crawl/matchups",
    "picks": "/api/crawl/picks",
    "standings": "/api/crawl/standings",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def supported_leagues(data: dict[str, Any], default_league_id: str) -> tuple[str, ...]:
    league = data.get("league") or {}
    candidates = [default_league_id, str(league.get("league_id") or "")]
    candidates.extend(str(item.get("league_id") or "") for item in data.get("leagues") or [] if isinstance(item, dict))
    return tuple(dict.fromkeys(value for value in candidates if value))


def validate_league(data: dict[str, Any], requested: str | None, default_league_id: str) -> str:
    league_id = requested or default_league_id
    if league_id not in supported_leagues(data, default_league_id):
        raise KeyError(f"League {league_id!r} is not available in this DTOS deployment.")
    return league_id


def _safe(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(item) for item in value]
    return value


def _valuation(player_id: str, data: dict[str, Any]) -> dict[str, Any]:
    market = data.get("market_data") or {}
    normalized = []
    for provider, rows in (market.get("providers") or {}).items():
        row = (rows or {}).get(player_id)
        if not isinstance(row, dict) or row.get("value") is None:
            continue
        distribution = tuple(float(item.get("value")) for item in rows.values() if isinstance(item, dict) and item.get("value") is not None)
        normalized.append(normalize_value(provider, float(row["value"]), distribution=distribution, updated_at=row.get("updated_at"), source_season=row.get("season"), provider_confidence=int(row.get("confidence") or 70)))
    consensus = build_canonical_consensus(tuple(normalized))
    return {
        "market_value": consensus.market_consensus,
        "confidence_score": consensus.confidence_score,
        "calibration_status": consensus.calibration_status.value,
        "provider_count": len(consensus.providers_used),
        "provider_spread": consensus.provider_spread,
    }


def _player(row: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    player_id = str(row.get("id") or row.get("player_id") or "")
    return {
        "id": player_id,
        "name": row.get("name") or row.get("full_name"),
        "position": row.get("position"),
        "nfl_team": row.get("team") or row.get("nfl_team"),
        "age": row.get("age"),
        "starter": bool(row.get("starter")),
        "roster_slot": row.get("roster_slot"),
        "starter_slot": row.get("starter_slot"),
        "valuation": _valuation(player_id, data),
    }


def public_teams(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "roster_id": team.get("roster_id"),
            "owner": team.get("owner"),
            "team_name": team.get("team_name"),
            "avatar": team.get("avatar"),
            "record": {"wins": team.get("wins", 0), "losses": team.get("losses", 0), "ties": team.get("ties", 0)},
            "points_for": team.get("points_for"),
            "points_against": team.get("points_against"),
            "max_points": team.get("max_points"),
            "roster": [_player(player, data) for player in team.get("players") or []],
            "draft_picks": _safe(team.get("picks_owned") or []),
            "draft_picks_traded_away": _safe(team.get("picks_traded_away") or []),
        }
        for team in data.get("teams") or []
    ]


def standings(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "roster_id": team.get("roster_id"),
            "team_name": team.get("team_name"),
            "owner": team.get("owner"),
            "wins": team.get("wins", 0),
            "losses": team.get("losses", 0),
            "ties": team.get("ties", 0),
            "points_for": team.get("points_for"),
            "points_against": team.get("points_against"),
            "max_points": team.get("max_points"),
        }
        for rank, team in enumerate(data.get("teams") or [], 1)
    ]


def public_league(data: dict[str, Any]) -> dict[str, Any]:
    league = data.get("league") or {}
    return {
        "league_id": league.get("league_id"),
        "name": league.get("name"),
        "season": league.get("season"),
        "status": league.get("status"),
        "total_rosters": league.get("total_rosters"),
        "avatar": league.get("avatar"),
        "scoring_settings": _safe(data.get("scoring_settings") or {}),
        "roster_settings": _safe(data.get("league_settings") or {}),
        "roster_positions": _safe(data.get("roster_positions") or []),
    }


def public_front_offices(data: dict[str, Any]) -> dict[str, Any]:
    if not data.get("teams"):
        return {"valuation_schema_version": VALUATION_SCHEMA_VERSION, "active_front_office": None, "organizations": [], "compatibilities": [], "relationships": []}
    view = build_front_office_center(data)
    return {
        "valuation_schema_version": VALUATION_SCHEMA_VERSION,
        "active_front_office": view["active"].roster_id,
        "organizations": _safe(view["reports"]),
        "compatibilities": _safe(view["compatibilities"]),
        "relationships": _safe(view["relationships"]),
        "recommendation": _safe(view["unified_recommendation"]),
    }


def public_trades(data: dict[str, Any]) -> dict[str, Any]:
    if not data.get("teams"):
        return {"valuation_schema_version": VALUATION_SCHEMA_VERSION, "active_front_office": None, "opportunities": [], "value_impacts": {}}
    view = build_trade_center(data)
    return {
        "valuation_schema_version": VALUATION_SCHEMA_VERSION,
        "active_front_office": view["active_team"].get("roster_id"),
        "opportunities": _safe(view["dossiers"]),
        "value_impacts": _safe(view["value_impacts"]),
        "recommendation": _safe(view["unified_recommendation"]),
    }


def public_transactions(data: dict[str, Any]) -> list[dict[str, Any]]:
    return _safe(normalize_transactions(data))


def public_matchups(data: dict[str, Any]) -> dict[str, Any]:
    return {"week": data.get("week"), "matchups": _safe(data.get("matchups") or {})}


def public_picks(data: dict[str, Any]) -> dict[str, Any]:
    return {"pick_ledger": _safe(data.get("pick_ledger") or []), "traded_picks": _safe(data.get("traded_picks") or [])}


def build_snapshot(data: dict[str, Any], state: dict[str, Any], league_id: str) -> dict[str, Any]:
    front_offices = public_front_offices(data)
    trades = public_trades(data)
    team_rows = public_teams(data)
    return {
        "valuation_schema_version": VALUATION_SCHEMA_VERSION,
        "league_id": league_id,
        "league": public_league(data),
        "owners": [{"owner": team["owner"], "roster_id": team["roster_id"], "team_name": team["team_name"]} for team in team_rows],
        "teams": team_rows,
        "standings": standings(data),
        "draft_picks": public_picks(data),
        "matchups": public_matchups(data),
        "transactions": public_transactions(data),
        "trades": trades,
        "front_offices": front_offices,
        "rankings": {"contender_and_dynasty": [organization.get("competitive_window") for organization in front_offices["organizations"]], "power": standings(data)},
        "recommendations": [item for item in (front_offices.get("recommendation"), trades.get("recommendation")) if item],
        "alerts": ([{"type": "sync", "message": "The latest synchronization attempt failed; cached data is being served."}] if state.get("last_error") else []),
        "historical_records": {"available": False, "reason": "No public historical-record dataset is currently stored by DTOS.", "records": []},
        "sync": sync_metadata(state),
    }


def sync_metadata(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "syncing": bool(state.get("syncing")),
        "last_sync": state.get("last_sync"),
        "last_successful_sync": state.get("last_sync") if not state.get("last_error") else None,
        "status": "failed" if state.get("last_error") else "healthy" if state.get("data") else "waiting",
        "last_error": "Synchronization failed; cached data may be stale." if state.get("last_error") else None,
    }


def cached_response(key: str, factory: Callable[[], Any], *, sync_marker: str | None, ttl: float = 300) -> dict[str, Any]:
    cache_key = f"crawl:{NORMALIZATION_VERSION}:{sync_marker or 'empty'}:{key}"
    artifact, hit = intelligence_cache.get_or_create_with_status(
        cache_key,
        lambda: {"generated_at": utcnow(), "data": jsonable_encoder(_safe(factory()))},
        ttl=ttl,
    )
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "valuation_schema_version": VALUATION_SCHEMA_VERSION,
        "app_version": VERSION,
        "generated_at": utcnow(),
        "data": artifact["data"],
        "cache": {"cached": hit, "generated_at": artifact["generated_at"]},
    }
