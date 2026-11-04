"""Approved normalized NFL production into global facts; league scoring on read."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from src.core.historical_memory.scoring import calculate_fantasy_points

from .global_evidence import GlobalEvidenceStore, GlobalFact
from .normalization.identity import PlayerIdentityResolver


class GlobalProduction:
    def __init__(self, store: GlobalEvidenceStore):
        self.store = store

    @staticmethod
    def scoring_components(values: dict[str, Any]) -> dict[str, Any]:
        """Explicit source-to-Sleeper scoring aliases, without zero-filling gaps."""
        result = dict(values)
        result['fum'] = values.get('fumbles')
        result['fum_lost'] = values.get('fumbles_lost')
        position = values.get('position')
        result['bonus_rec_te'] = (values.get('rec') if position == 'TE' else 0) if position else None
        # The published passing_40/receiving_40 columns count big plays, NOT
        # long touchdowns. They cannot fill the *_td_40p scoring evidence gap.
        return result

    @classmethod
    def score_game(cls, values: dict[str, Any], scoring_settings: dict[str, Any]) -> dict[str, Any]:
        result = calculate_fantasy_points(cls.scoring_components(values), scoring_settings)
        if result['availability'] != 'calculated':
            result['known_component_points'] = result['fantasy_points']
            result['fantasy_points'] = None
        return result

    def publish_batch(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        identities: PlayerIdentityResolver,
        game_dates: Mapping[str, str],
        retrieved_at: str,
    ) -> dict[str, int]:
        """Consume at most 1000 already-normalized provider rows, never raw HTML.

        Unknown game dates/IDs are unresolved, not invented from season/week.
        A modern backfill does not prove historical publication time.
        """
        skipped = {"identity_unresolved": 0, "game_time_unavailable": 0}

        def bounded():
            for count, row in enumerate(rows, 1):
                if count > 1000:
                    raise ValueError("Production source batch exceeds 1000 rows.")
                yield row

        return (
            self.store.publish(
                self.facts(
                    bounded(),
                    identities=identities,
                    game_dates=game_dates,
                    skipped=skipped,
                ),
                retrieved_at=retrieved_at,
            )
            | skipped
        )

    @staticmethod
    def facts(
        rows: Iterable[Mapping[str, Any]],
        *,
        identities: PlayerIdentityResolver,
        game_dates: Mapping[str, str],
        skipped: dict[str, int],
    ) -> Iterable[GlobalFact]:
        """Stream normalized rows; orchestration owns batch and resume boundaries."""
        for row in rows:
            player = identities.resolve(
                str(row.get("provider_player_id") or ""), "GSIS"
            )
            if player is None:
                skipped["identity_unresolved"] += 1
                continue
            game_id = str(row.get("game_id") or "")
            when = game_dates.get(game_id)
            if not when:
                skipped["game_time_unavailable"] += 1
                continue
            if row.get("provider") != "nflverse":
                raise ValueError("Unexpected production source.")
            yield GlobalFact(
                family="production",
                subject_id=f"sleeper:{player.dtos_id}",
                provider="nflverse",
                source_record_id=f"{game_id}:{row['provider_player_id']}",
                effective_at=when,
                known_at=None,
                season=row.get("season"),
                week=row.get("week"),
                values={
                    **dict(row.get("raw_stats") or {}),
                    "game_id": game_id,
                    "team": row.get("nfl_team"),
                    "opponent": row.get("opponent"),
                    "position": row.get("position"),
                    "season_type": row.get("season_type"),
                },
            )

    def league_scored(
        self,
        player_id: str,
        *,
        league_id: str,
        scoring_settings: dict[str, Any],
        as_of: str,
        season: int | None = None,
    ) -> dict[str, Any]:
        """No provider work or durable league copy; caller supplies authorized context."""
        if not league_id:
            raise ValueError(
                "League scoring requires explicit authorized league context."
            )
        if not scoring_settings:
            raise ValueError('Canonical league scoring settings are unavailable.')
        facts = self.store.read("production", f"sleeper:{player_id}", as_of=as_of, season=season)
        games = [
            {
                "game_id": fact["values"].get("game_id"),
                "season": fact["season"],
                "week": fact["week"],
                "evidence_fingerprint": fact["fingerprint"],
                "knowledge_boundary": fact["knowledge_boundary"],
                "raw_stats": dict(fact["values"]),
                **self.score_game(fact["values"], scoring_settings),
            }
            for fact in facts
        ]
        complete = [row for row in games if row["availability"] == "calculated"]
        return {
            "league_id": league_id,
            "player_id": player_id,
            "as_of": as_of,
            "games": games,
            "games_with_complete_scoring": len(complete),
            "ppg": round(
                sum(row["fantasy_points"] for row in complete) / len(complete), 2
            )
            if complete
            else None,
            "denominator": "NFL games with complete supplied scoring components",
            "availability": "cached" if games else "unavailable",
            "scoring_availability": ('complete' if games and len(complete) == len(games)
                                     else 'incomplete' if games else 'unavailable'),
        }
