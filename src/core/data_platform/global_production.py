"""Approved normalized NFL production into global facts; league scoring on read."""

from __future__ import annotations

from typing import Any, Iterable, Mapping
import math

from src.core.historical_memory.scoring import calculate_fantasy_points

from .global_evidence import GlobalEvidenceStore, GlobalFact
from .normalization.identity import PlayerIdentityResolver


class GlobalProduction:
    def __init__(self, store: GlobalEvidenceStore):
        self.store = store

    @staticmethod
    def completed_week_boundary(data: dict[str, Any], season: int) -> int | None:
        nfl = data.get('nfl_state') or {}
        week = nfl.get('week')
        return (week - 1 if str(nfl.get('season')) == str(season)
                and nfl.get('season_type') in (None, 'regular')
                and type(week) is int and 1 <= week <= 18 else None)

    @staticmethod
    def scoring_components(values: dict[str, Any]) -> dict[str, Any]:
        """Explicit source-to-Sleeper scoring aliases, without zero-filling gaps."""
        result = dict(values)
        result['fum'] = values.get('fumbles')
        result['fum_lost'] = values.get('fumbles_lost')
        position = values.get('position')
        for key, required_position, stat in (
            ('bonus_rec_te', 'TE', 'rec'), ('bonus_rec_rb', 'RB', 'rec'),
            ('bonus_rec_wr', 'WR', 'rec'), ('bonus_rush_td_qb', 'QB', 'rush_td'),
        ):
            result[key] = (values.get(stat) if position == required_position else 0
                           if position in {'QB', 'RB', 'WR', 'TE', 'K', 'P'} else None)
        # The published passing_40/receiving_40 columns count big plays, NOT
        # long touchdowns. They cannot fill the *_td_40p scoring evidence gap.
        return result

    @classmethod
    def score_game(cls, values: dict[str, Any], scoring_settings: dict[str, Any]) -> dict[str, Any]:
        # These categories score the fantasy team-defense asset, not an NFL
        # individual. Player special-teams categories (st_*) remain applicable.
        team_only = {'sack', 'int', 'ff', 'fum_rec', 'fum_rec_td', 'safe', 'blk_kick',
                     'def_td', 'def_st_td', 'def_st_ff', 'def_st_fum_rec',
                     'def_kr_yd', 'def_pr_yd', 'def_pr_td', 'pts_allow', 'yds_allow'}
        individual = values.get('position') in {'QB', 'RB', 'WR', 'TE', 'FB', 'K', 'P'}
        active, ignored, inapplicable = {}, [], []
        for key, weight in scoring_settings.items():
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight):
                raise ValueError('Canonical production scoring coefficients must be finite numbers.')
            if weight == 0:
                ignored.append(key)
            elif individual and (key in team_only or key.startswith(('pts_allow_', 'yds_allow_'))):
                inapplicable.append(key)
            else:
                active[key] = weight
        components = cls.scoring_components(values)
        # Malformed source evidence must not be silently skipped by a permissive
        # legacy scorer and then described as a complete canonical game.
        for key in active:
            value = components.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                components[key] = None
        result = calculate_fantasy_points(components, active)
        result['ignored_zero_weight_components'] = sorted(ignored)
        result['inapplicable_components'] = sorted(inapplicable)
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
        through_week: int | None = None,
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
            if through_week is None or (fact["week"] is not None and fact["week"] <= through_week)
        ]
        complete = [row for row in games if row["availability"] == "calculated"]
        return {
            "league_id": league_id,
            "player_id": player_id,
            "as_of": as_of,
            "completed_week_boundary": through_week,
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
