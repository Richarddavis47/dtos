"""Approved public-provider ingestion and explicit availability contracts."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any


FANTASYCALC_URL = "https://api.fantasycalc.com/values/current?isDynasty=true&numQbs=2&numTeams=12&ppr=1"
DYNASTYPROCESS_VALUES_URL = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/values.csv"
DYNASTYPROCESS_IDS_URL = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def market_identity_map(rows) -> dict[str, str]:
    """Exact source IDs only; conflicting crosswalk identities remain unresolved."""
    candidates: dict[str, set[str]] = {}
    for row in rows:
        provider_id, sleeper_id = row.get('fantasypros_id'), row.get('sleeper_id')
        if provider_id not in {None, '', 'NA'} and sleeper_id not in {None, '', 'NA'}:
            candidates.setdefault(str(provider_id), set()).add(str(sleeper_id))
    return {key: next(iter(values)) for key, values in candidates.items() if len(values) == 1}


def _status(
    *,
    enabled: bool,
    state: str,
    result: str,
    records: int = 0,
    refreshed_at: str | None = None,
    reason: str | None = None,
    refresh_hours: int = 24,
) -> dict[str, Any]:
    refreshed = refreshed_at or _now().isoformat()
    next_refresh = (_now() + timedelta(hours=refresh_hours)).isoformat() if enabled else None
    return {
        "enabled": enabled,
        "status": state,
        "last_refresh": refreshed,
        "next_refresh": next_refresh,
        "refresh_result": result,
        "records_retrieved": records,
        "reason": reason,
    }


def provider_catalog(existing: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Return complete provider state, including sources DTOS cannot activate."""
    catalog = dict(existing or {})
    catalog.setdefault("FantasyCalc", _status(enabled=True, state="waiting", result="Not refreshed yet"))
    catalog.setdefault("DynastyProcess", _status(enabled=True, state="waiting", result="Not refreshed yet"))
    catalog.update(
        {
            "Sleeper Players": _status(enabled=True, state="waiting", result="Refreshed with league synchronization"),
            "Sleeper Trending": _status(enabled=True, state="waiting", result="Refreshed with league synchronization"),
            "Sleeper Transactions": _status(enabled=True, state="waiting", result="Refreshed with league synchronization"),
            "Sleeper ADP": _status(enabled=False, state="unsupported", result="Disabled", reason="Sleeper's supported public API does not expose an ADP endpoint."),
            "Underdog ADP": _status(enabled=False, state="unsupported", result="Disabled", reason="No approved public Underdog ADP API is available to this deployment."),
            "KeepTradeCut": _status(enabled=False, state="unsupported", result="Disabled", reason="No approved public API or licensed integration is configured."),
            "Projections": _status(enabled=False, state="unsupported", result="Disabled", reason="No live projection provider has been configured."),
            "Production": _status(enabled=True, state="waiting", result="Canonical global background ingestion", reason="Availability depends on the requested source season and retained canonical evidence."),
            "Usage": _status(enabled=True, state="waiting", result="Derived targets/carries from canonical production", reason="Snap-share and route detail are not connected."),
        }
    )
    return catalog


def refresh_due(status: dict[str, Any] | None, *, hours: int = 24) -> bool:
    if not status or not status.get("last_refresh") or status.get("status") != "healthy":
        return True
    try:
        refreshed = datetime.fromisoformat(str(status["last_refresh"]).replace("Z", "+00:00"))
    except ValueError:
        return True
    return _now() - refreshed.astimezone(timezone.utc) >= timedelta(hours=hours)


async def refresh_public_market(client: Any, cached: dict[str, Any] | None = None) -> dict[str, Any]:
    """Refresh approved public market sources while retaining disclosed fallback data."""
    previous = dict(cached or {})
    providers = dict(previous.get("providers") or {})
    statuses = provider_catalog(previous.get("provider_status") or {})
    attribution = dict(previous.get("attribution") or {})

    if refresh_due(statuses.get("FantasyCalc")):
        try:
            response = await client.get(FANTASYCALC_URL)
            response.raise_for_status()
            rows = response.json()
            stamp = _now().isoformat()
            normalized: dict[str, dict[str, Any]] = {}
            for row in rows if isinstance(rows, list) else ():
                player = row.get("player") or {}
                sleeper_id = player.get("sleeperId")
                value = row.get("value")
                if sleeper_id is None or value is None:
                    continue
                normalized[str(sleeper_id)] = {
                    "value": value,
                    "confidence": 85,
                    "updated_at": stamp,
                    "retrieved_at": stamp,
                    "source_updated_at": None,
                    "timestamp_basis": "retrieved_at_source_timestamp_unavailable",
                    "format": "dynasty_2qb",
                    "format_details": {"num_teams": 12, "ppr": 1},
                    "independence_family": "fantasycalc_observed_trades",
                    "rank": row.get("overallRank"),
                    "position_rank": row.get("positionRank"),
                    "tier": row.get("maybeTier"),
                    "trend_30_day": row.get("trend30Day"),
                    "trade_frequency": row.get("maybeTradeFrequency"),
                    "roster_percent": row.get("maybeRosterPercent"),
                    "redraft_value": row.get("redraftValue"),
                    "fantasycalc_id": player.get("id"),
                    "detail": "FantasyCalc public dynasty market value",
                }
            providers["FantasyCalc"] = normalized
            statuses["FantasyCalc"] = _status(enabled=True, state="healthy", result="success", records=len(normalized), refreshed_at=stamp)
            attribution["FantasyCalc"] = {"label": "FantasyCalc", "url": "https://fantasycalc.com/", "retrieval_mode": "public API"}
        except Exception as exc:  # provider isolation is intentional
            statuses["FantasyCalc"] = _status(enabled=True, state="failed", result="cached_fallback" if providers.get("FantasyCalc") else "failed", records=len(providers.get("FantasyCalc") or {}), reason=f"FantasyCalc temporarily unavailable: {type(exc).__name__}.")

    if refresh_due(statuses.get("DynastyProcess")):
        try:
            value_response = await client.get(DYNASTYPROCESS_VALUES_URL)
            ids_response = await client.get(DYNASTYPROCESS_IDS_URL)
            value_response.raise_for_status()
            ids_response.raise_for_status()
            identities = market_identity_map(csv.DictReader(io.StringIO(ids_response.text)))
            stamp = _now().isoformat()
            normalized = {}
            for row in csv.DictReader(io.StringIO(value_response.text)):
                sleeper_id = identities.get(row.get("fp_id"))
                value = row.get("value_2qb")
                if not sleeper_id or value in {None, "", "NA"}:
                    continue
                normalized[str(sleeper_id)] = {
                    "value": value,
                    "confidence": 75,
                    "updated_at": stamp,
                    "source_updated_at": row.get('scrape_date') or None,
                    "retrieved_at": stamp,
                    "source_timestamp_precision": "day",
                    "format": "dynasty_2qb",
                    "independence_family": "fantasypros_derived",
                    "rank": row.get("ecr_2qb"),
                    "position_rank": row.get("ecr_pos"),
                    "detail": "DynastyProcess public 2QB dynasty value",
                }
            providers["DynastyProcess"] = normalized
            statuses["DynastyProcess"] = _status(enabled=True, state="healthy", result="success", records=len(normalized), refreshed_at=stamp)
            attribution["DynastyProcess"] = {"label": "DynastyProcess", "url": "https://github.com/dynastyprocess/data", "retrieval_mode": "public dataset"}
        except Exception as exc:  # provider isolation is intentional
            statuses["DynastyProcess"] = _status(enabled=True, state="failed", result="cached_fallback" if providers.get("DynastyProcess") else "failed", records=len(providers.get("DynastyProcess") or {}), reason=f"DynastyProcess temporarily unavailable: {type(exc).__name__}.")

    return {"providers": providers, "provider_status": statuses, "attribution": attribution, "context_mode": "online" if providers else "offline", "allow_cached_fallback": bool(providers)}


def player_context(player_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build transparent Sleeper-derived player context without invented metrics."""
    player = (data.get("players") or {}).get(player_id) or {}
    trending = data.get("trending_players") or {}
    adds = next((row.get("count", 0) for row in trending.get("adds") or [] if str(row.get("player_id")) == player_id), 0)
    drops = next((row.get("count", 0) for row in trending.get("drops") or [] if str(row.get("player_id")) == player_id), 0)
    owners = [team for team in data.get("teams") or [] if any(str(row.get("id")) == player_id for row in team.get("players") or [])]
    transactions = [row for row in data.get("transactions") or [] if player_id in {str(key) for key in (row.get("adds") or {})} or player_id in {str(key) for key in (row.get("drops") or {})}]
    role = player.get("depth_chart_position") or player.get("depth_chart_order")
    snapshot = data.get("projection_intelligence") or {}
    league_id = str((data.get("league") or {}).get("league_id") or "")
    projection = ((snapshot.get("players") or {}).get(player_id) or {}) if league_id and str(snapshot.get("league_id") or "") == league_id else {}
    projected = projection.get("weekly_projected_points")
    return {
        "metadata": {
            "team": player.get("team"),
            "position": player.get("position"),
            "age": player.get("age"),
            "status": player.get("status"),
            "bye_week": player.get("bye_week"),
            "depth_chart_role": role,
            "depth_chart_order": player.get("depth_chart_order"),
        },
        "league": {"trending_adds": adds, "trending_drops": drops, "owned_by": owners[0].get("team_name") if owners else None, "transaction_count": len(transactions), "source": "Sleeper"},
        "projection_evidence": {
            "value": projected, "source": "Sleeper",
            "availability": "cached" if projected is not None else "unavailable",
            "league_id": league_id,
            "snapshot_id": snapshot.get("projection_snapshot_id") if projection else None,
            "season": snapshot.get("season") if projection else None,
            "week": snapshot.get("week") if projection else None,
            "freshness": projection.get("source_freshness") if projection else None,
        },
        "availability": {
            "adp": "Sleeper and Underdog do not expose an approved public ADP feed to this deployment.",
            "production": "Consult canonical_evidence for season-scoped production; this legacy context does not attach a production window.",
            "projection": None if projected is not None else "Canonical Sleeper projection evidence is unavailable for this player in the active league snapshot; missing evidence is not zero.",
            "usage": "No supported snap-share or route-usage provider is configured.",
            "depth_chart_role": None if role is not None else "Sleeper player metadata does not currently provide a depth-chart role for this player.",
            "bye_week": None if player.get("bye_week") is not None else "Consult canonical_evidence.schedule for source-backed schedule/bye evidence; Sleeper metadata alone does not supply this field.",
        },
    }
