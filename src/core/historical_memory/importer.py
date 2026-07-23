"""Resumable, idempotent Sleeper historical league importer."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

from src.core.historical_memory.models import HISTORICAL_SCHEMA_VERSION
from src.core.historical_memory.store import HistoricalStore

logger = logging.getLogger("dtos.history")
Fetch = Callable[[str], Awaitable[Any]]
REGULAR_WEEKS = 18


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HistoricalImporter:
    def __init__(self, store: HistoricalStore, fetch: Fetch) -> None:
        self.store = store
        self.fetch = fetch

    async def discover_seasons(self, league_id: str, earliest: int = 2021) -> list[tuple[str, dict[str, Any]]]:
        seasons: list[tuple[str, dict[str, Any]]] = []
        seen: set[str] = set()
        current = league_id
        while current and current not in seen:
            seen.add(current)
            league = await self.fetch(f"/league/{current}")
            if not isinstance(league, dict) or not league:
                break
            season = int(league.get("season") or 0)
            if season and season >= earliest:
                seasons.append((current, league))
            previous = str(league.get("previous_league_id") or "")
            if not previous or season <= earliest:
                break
            current = previous
        return sorted(seasons, key=lambda item: int(item[1].get("season") or 0))

    async def backfill(
        self,
        league_id: str,
        *,
        earliest: int = 2021,
        workbook: Path | None = None,
        seasons: set[int] | None = None,
    ) -> dict[str, Any]:
        run_id = uuid4().hex
        started = _now()
        workbook_status = (
            f"available:{workbook}" if workbook and workbook.exists()
            else "not_supplied; Sleeper remains authoritative"
        )
        self.store.start_run(run_id, league_id, started, workbook_status)
        written = unchanged = 0
        errors: list[str] = []
        imported: list[int] = []
        checkpoint: str | None = "discover"
        try:
            discovered, nfl_state = await asyncio.gather(
                self.discover_seasons(league_id, earliest),
                self.fetch("/state/nfl"),
            )
            if seasons:
                discovered = [item for item in discovered if int(item[1]["season"]) in seasons]
            for source_league_id, league in discovered:
                season = int(league["season"])
                max_week = _completed_week_limit(season, nfl_state)
                checkpoint = f"{season}:league"
                added, same = await self._import_season(
                    run_id, league_id, source_league_id, season, league, max_week,
                )
                written += added
                unchanged += same
                imported.append(season)
                self.store.update_run(
                    run_id, status="running", checkpoint=f"{season}:complete",
                    written=written, unchanged=unchanged, errors=errors, completed_at=None,
                )
            status = "complete"
        except Exception as exc:
            logger.exception("Historical import failed at %s", checkpoint)
            errors.append(f"{type(exc).__name__}: {exc}")
            status = "partial"
        completed = _now()
        self.store.update_run(
            run_id, status=status, checkpoint=checkpoint, written=written,
            unchanged=unchanged, errors=errors, completed_at=completed,
        )
        return {
            "run_id": run_id, "league_id": league_id, "seasons": imported,
            "status": status, "records_written": written,
            "records_unchanged": unchanged, "errors": errors,
            "started_at": started, "completed_at": completed,
            "workbook_status": workbook_status, "checkpoint": checkpoint,
            "reconciliation": {
                "sleeper_records_accepted": written + unchanged,
                "workbook_records_supplemented": 0,
                "conflicts": [],
                "chosen_source": "Sleeper",
                "unresolved": [] if workbook and workbook.exists() else ["Supplemental workbook was not supplied."],
            },
        }

    async def _import_season(
        self, run_id: str, root_league_id: str, source_league_id: str,
        season: int, league: dict[str, Any], max_week: int,
    ) -> tuple[int, int]:
        retrieved = _now()
        written = unchanged = 0

        def append(entity: str, source_id: str, payload: dict[str, Any], **dimensions: Any) -> None:
            nonlocal written, unchanged
            key_parts = [root_league_id, entity, str(season), str(dimensions.get("week") or ""), source_id]
            inserted = self.store.append(
                record_key=":".join(key_parts), entity_type=entity,
                league_id=root_league_id, season=season,
                source_record_id=source_id, observed_at=dimensions.pop("observed_at", retrieved),
                retrieved_at=retrieved, provider="Sleeper",
                availability=dimensions.pop("availability", "observed"),
                confidence=dimensions.pop("confidence", 95),
                calculation_method=dimensions.pop("calculation_method", "provider_record"),
                schema_version=HISTORICAL_SCHEMA_VERSION, payload=payload, **dimensions,
            )
            written += int(inserted)
            unchanged += int(not inserted)

        append("league_season", source_league_id, {
            "league_id": root_league_id, "source_league_id": source_league_id,
            "season": season, "league_name": league.get("name"), "platform": "Sleeper",
            "scoring_settings": league.get("scoring_settings") or {},
            "roster_positions": league.get("roster_positions") or [],
            "settings": league.get("settings") or {},
            "playoff_settings": {
                key: value for key, value in (league.get("settings") or {}).items()
                if "playoff" in key
            },
            "draft_settings": {
                key: value for key, value in (league.get("settings") or {}).items()
                if "draft" in key
            },
            "total_rosters": league.get("total_rosters"),
            "status": league.get("status"),
            "schema_version": HISTORICAL_SCHEMA_VERSION,
        })
        users, rosters, drafts, winners, losers = await asyncio.gather(
            self.fetch(f"/league/{source_league_id}/users"),
            self.fetch(f"/league/{source_league_id}/rosters"),
            self.fetch(f"/league/{source_league_id}/drafts"),
            self.fetch(f"/league/{source_league_id}/winners_bracket"),
            self.fetch(f"/league/{source_league_id}/losers_bracket"),
        )
        user_map = {str(row.get("user_id")): row for row in users or []}
        ranked_rosters = sorted(
            rosters or [],
            key=lambda row: (
                -int((row.get("settings") or {}).get("wins") or 0),
                int((row.get("settings") or {}).get("losses") or 0),
                -float(_decimal_score(row.get("settings") or {}, "fpts") or 0),
                int(row.get("roster_id") or 0),
            ),
        )
        rank_by_roster = {
            str(row.get("roster_id")): rank
            for rank, row in enumerate(ranked_rosters, 1)
        }
        for roster in rosters or []:
            roster_id = str(roster.get("roster_id"))
            owner_id = str(roster.get("owner_id") or "")
            owner = user_map.get(owner_id, {})
            metadata = owner.get("metadata") or {}
            franchise_id = f"{root_league_id}:franchise:{roster_id}"
            append("franchise_identity", roster_id, {
                "franchise_id": franchise_id, "sleeper_roster_id": roster_id,
                "owner_id": owner_id, "sleeper_username": owner.get("display_name") or owner.get("username"),
                "sleeper_team_name": metadata.get("team_name"),
                "dtos_display_name": metadata.get("team_name") or owner.get("display_name") or f"Team {roster_id}",
                "valid_from": f"{season}-01-01", "valid_to": f"{season}-12-31",
                "active": True,
            }, franchise_id=franchise_id)
            append("season_standing", roster_id, {
                "roster_id": int(roster_id), "settings": roster.get("settings") or {},
                "wins": (roster.get("settings") or {}).get("wins"),
                "losses": (roster.get("settings") or {}).get("losses"),
                "ties": (roster.get("settings") or {}).get("ties"),
                "points_for": _decimal_score(roster.get("settings") or {}, "fpts"),
                "points_against": _decimal_score(roster.get("settings") or {}, "fpts_against"),
                "max_points_for": _decimal_score(roster.get("settings") or {}, "ppts"),
                "rank": rank_by_roster[roster_id],
                "rank_method": "wins desc, losses asc, points-for desc, roster ID asc",
            }, franchise_id=franchise_id)
        append("playoff_bracket", "winners", {"bracket": winners or [], "type": "winners"})
        append("playoff_bracket", "losers", {"bracket": losers or [], "type": "consolation"})
        placements = {
            int(node["p"]): int(node["w"])
            for node in winners or []
            if node.get("p") is not None and node.get("w") is not None
        }
        append("playoff_result", "placements", {
            "placements": placements,
            "champion_roster_id": placements.get(1),
            "runner_up_roster_id": placements.get(2),
            "third_place_roster_id": placements.get(3),
            "final_four_roster_ids": [value for place, value in placements.items() if place <= 4],
            "availability": "observed" if placements else "unavailable",
        }, availability="observed" if placements else "unavailable")

        for draft in drafts or []:
            draft_id = str(draft.get("draft_id") or "")
            picks = await self.fetch(f"/draft/{draft_id}/picks") if draft_id else []
            append("draft", draft_id, {"draft": draft, "picks_count": len(picks or [])})
            for pick in picks or []:
                pick_id = str(pick.get("pick_no") or f"{pick.get('round')}-{pick.get('draft_slot')}")
                append("draft_pick", f"{draft_id}:{pick_id}", {
                    **pick, "draft_id": draft_id,
                    "original_franchise": pick.get("roster_id"),
                    "current_pick_owner": pick.get("picked_by"),
                }, player_id=str(pick.get("player_id") or "") or None)

        weekly_payloads = await asyncio.gather(*(
            request
            for week in range(1, max_week + 1)
            for request in (
                self.fetch(f"/league/{source_league_id}/matchups/{week}"),
                self.fetch(f"/league/{source_league_id}/transactions/{week}"),
            )
        ))
        for week in range(1, max_week + 1):
            matchups = weekly_payloads[(week - 1) * 2]
            transactions = weekly_payloads[(week - 1) * 2 + 1]
            if not matchups and not transactions:
                continue
            append("league_week", str(week), {
                "season": season, "week": week, "phase": "regular_or_postseason",
                "status": "complete" if matchups else "incomplete",
                "completed": bool(matchups),
                "start_date": None, "end_date": None,
            }, week=week, availability="calculated", calculation_method="Sleeper week presence")
            matchup_groups: dict[str, list[dict[str, Any]]] = {}
            for matchup in matchups or []:
                matchup_groups.setdefault(str(matchup.get("matchup_id") or "unassigned"), []).append(matchup)
            for matchup_id, sides in matchup_groups.items():
                scores = [(int(side.get("roster_id") or 0), float(side.get("points") or 0)) for side in sides]
                ordered = sorted(scores, key=lambda item: (-item[1], item[0]))
                tied = len(ordered) == 2 and ordered[0][1] == ordered[1][1]
                append("matchup", f"{week}:{matchup_id}", {
                    "matchup_id": matchup_id, "franchises": [item[0] for item in scores],
                    "team_points": {str(item[0]): item[1] for item in scores},
                    "winner": None if tied or len(ordered) < 2 else ordered[0][0],
                    "loser": None if tied or len(ordered) < 2 else ordered[-1][0],
                    "tie": tied,
                    "margin": 0.0 if tied else round(ordered[0][1] - ordered[-1][1], 2) if len(ordered) >= 2 else None,
                    "postseason_context": week > 14,
                }, week=week, availability="calculated", calculation_method="Sleeper paired matchup scores")
            for matchup in matchups or []:
                roster_id = str(matchup.get("roster_id"))
                franchise_id = f"{root_league_id}:franchise:{roster_id}"
                source_id = f"{week}:{roster_id}"
                starters = [str(item) for item in matchup.get("starters") or []]
                players = [str(item) for item in matchup.get("players") or []]
                player_points = matchup.get("players_points") or {}
                append("weekly_roster", source_id, {
                    "starters": starters, "bench": [item for item in players if item not in starters],
                    "taxi": [], "ir": [], "inactive": [],
                    "roster_state_timestamp": None,
                    "slot_limitations": "Sleeper matchup payload does not distinguish taxi/IR history.",
                }, week=week, franchise_id=franchise_id)
                append("matchup_team", source_id, {
                    **matchup, "team_points": matchup.get("points"),
                    "bench_points": round(sum(float(player_points.get(item) or 0) for item in players if item not in starters), 2),
                    "lineup_efficiency": None,
                    "optimal_points": None,
                    "outcome": "requires opponent pairing",
                }, week=week, franchise_id=franchise_id)
                for player_id in players:
                    points = player_points.get(player_id)
                    append("player_week", f"{week}:{roster_id}:{player_id}", {
                        "fantasy_points": float(points) if points is not None else None,
                        "actual_league_scored_points": float(points) if points is not None else None,
                        "starter": player_id in starters,
                        "raw_stats": None,
                        "raw_stats_availability": "unavailable from Sleeper matchup history",
                        "usage": None,
                        "usage_availability": "provider_not_supported by Sleeper league API",
                        "scoring_schema_source": source_league_id,
                    }, week=week, franchise_id=franchise_id, player_id=player_id,
                       availability="observed" if points is not None else "unavailable")
            for transaction in transactions or []:
                transaction_id = str(transaction.get("transaction_id") or "")
                transaction_type = "trade" if transaction.get("type") == "trade" else "transaction"
                append(transaction_type, transaction_id, {
                    **transaction, "trade_time_values": None,
                    "trade_time_value_availability": "unavailable unless a contemporaneous valuation snapshot exists",
                }, week=week, observed_at=_timestamp(transaction.get("created")) or retrieved)

        self._quality_checks(
            run_id, root_league_id, season, expect_weeks=max_week > 0,
            expect_champion=max_week == REGULAR_WEEKS,
        )
        return written, unchanged

    def _quality_checks(
        self, run_id: str, league_id: str, season: int, *,
        expect_weeks: bool, expect_champion: bool,
    ) -> None:
        count, weeks = self.store.records(league_id, "league_week", season=season, limit=100)
        if count == 0 and expect_weeks:
            self.store.add_quality_issue(
                f"{league_id}:{season}:missing-weeks", run_id, league_id, season,
                "warning", "missing_weeks", "Sleeper returned no historical matchup or transaction weeks.",
            )
        player_count, _ = self.store.records(league_id, "player_week", season=season, limit=1)
        if player_count:
            self.store.add_quality_issue(
                f"{league_id}:{season}:raw-stats", run_id, league_id, season,
                "informational", "provider_gap",
                "Sleeper matchup history supplies league-scored player points but not reproducible raw NFL stat components or advanced usage.",
            )
            self.store.add_quality_issue(
                f"{league_id}:{season}:identity-coverage", run_id, league_id, season,
                "informational", "identity_coverage",
                "Historical matchups retain stable Sleeper player IDs; current metadata resolves active players, while retired IDs may lack display metadata.",
            )
        _, playoff_rows = self.store.records(league_id, "playoff_result", season=season, limit=10)
        has_champion = any(row["payload"].get("champion_roster_id") is not None for row in playoff_rows)
        if expect_champion and not has_champion:
            self.store.add_quality_issue(
                f"{league_id}:{season}:missing-champion", run_id, league_id, season,
                "warning", "missing_champion",
                "No champion placement was available in the Sleeper winners bracket.",
            )


def _decimal_score(settings: dict[str, Any], key: str) -> float | None:
    whole = settings.get(key)
    decimal = settings.get(f"{key}_decimal")
    if whole is None and decimal is None:
        return None
    return round(float(whole or 0) + float(decimal or 0) / 100, 2)


def _timestamp(milliseconds: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(milliseconds) / 1000, timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _completed_week_limit(season: int, nfl_state: Any) -> int:
    if not isinstance(nfl_state, dict) or not nfl_state.get("season"):
        return REGULAR_WEEKS
    active_season = int(nfl_state["season"])
    if season < active_season:
        return REGULAR_WEEKS
    if season > active_season:
        return 0
    if nfl_state.get("season_type") not in {"regular", "post"}:
        return 0
    return max(0, min(REGULAR_WEEKS, int(nfl_state.get("week") or 1) - 1))
