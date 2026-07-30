"""Explainable competitive-cycle and historical-window analysis."""
from __future__ import annotations

from dataclasses import asdict
import json

from src.core.fois.facts import SeasonResult
from src.core.fois.models import (
    CompetitiveCycle,
    HistoricalWindow,
    ResultsAnalysis,
    SeasonTimeline,
)
from src.core.fois.scoring import clamp


class CompetitiveCycleAnalyzer:
    """Classify observed seasons and group them into competitive cycles."""

    def analyze(
        self,
        seasons: tuple[SeasonResult, ...],
        *,
        ownership_changes: int = 0,
        expected_seasons: int | None = None,
    ) -> ResultsAnalysis:
        ordered = tuple(sorted(seasons, key=lambda row: row.season))
        timeline = self._timeline(ordered)
        cycles = self._cycles(timeline)
        windows = self._windows(timeline)
        rebuilds = [cycle.duration for cycle in cycles if cycle.cycle_type == "rebuild"]
        reloads = [
            cycle.reload_time
            for cycle in cycles
            if cycle.reload_time is not None
        ]
        strengths = self._strengths(timeline, cycles)
        weaknesses = self._weaknesses(timeline, cycles)
        observed = len([row for row in ordered if row.complete])
        expected = expected_seasons or observed
        completeness = observed / expected if expected else 0
        explanation = (
            f"Analyzed {observed} completed season(s) across {len(cycles)} "
            f"competitive cycle(s); {ownership_changes} ownership transition(s) "
            "reduce confidence but never reduce the Results score."
        )
        return ResultsAnalysis(
            timeline,
            cycles,
            windows,
            {
                "total_rebuild_years": sum(rebuilds),
                "rebuild_count": len(rebuilds),
                "average_rebuild_length": (
                    round(sum(rebuilds) / len(rebuilds), 2) if rebuilds else 0
                ),
                "longest_rebuild": max(rebuilds, default=0),
                "average_reload_time": (
                    round(sum(reloads) / len(reloads), 2) if reloads else None
                ),
                "history_completeness": round(completeness * 100, 2),
            },
            strengths,
            weaknesses,
            explanation,
        )

    def _timeline(
        self,
        seasons: tuple[SeasonResult, ...],
    ) -> tuple[SeasonTimeline, ...]:
        output: list[SeasonTimeline] = []
        previous_state: str | None = None
        for row in seasons:
            wins = row.matchup_wins if row.matchup_wins is not None else row.wins
            losses = (
                row.matchup_losses
                if row.matchup_losses is not None
                else row.losses
            )
            games = (wins or 0) + (losses or 0)
            win_rate = (wins or 0) / games if games else None
            bottom_quartile = (
                row.finish is not None
                and row.league_size is not None
                and row.finish > row.league_size * .75
            )
            if row.rebuilding:
                state = "rebuild"
                reason = "Explicit cached competitive-cycle evidence identifies a rebuild."
            elif row.championship or row.championship_game or (
                row.final_four and (win_rate or 0) >= .6
            ):
                state = "elite_contender"
                reason = "Championship-level postseason result."
            elif row.playoff or (win_rate is not None and win_rate > .5):
                state = "contender"
                reason = "Playoff qualification or a winning regular season."
            elif row.rebuilding or bottom_quartile or (
                win_rate is not None and win_rate < .36
            ):
                state = "rebuild"
                reason = "Bottom-quartile finish or sub-.360 observed win rate."
            elif previous_state == "rebuild" and (win_rate or 0) >= .43:
                state = "ascending"
                reason = "Improved from a rebuild toward contention."
            elif previous_state in {"contender", "elite_contender"}:
                state = "reload" if (win_rate or 0) >= .43 else "decline"
                reason = (
                    "Temporarily outside contention with a competitive baseline."
                    if state == "reload"
                    else "Results declined materially after contention."
                )
            else:
                state = "transition"
                reason = "Neither contention nor rebuild evidence is conclusive."
            confidence = 100 if row.complete and games else 65 if row.complete else 35
            output.append(
                SeasonTimeline(
                    row.season,
                    state,
                    wins,
                    losses,
                    row.finish,
                    row.league_size,
                    row.playoff,
                    row.final_four,
                    row.championship_game,
                    row.championship,
                    reason,
                    confidence,
                )
            )
            previous_state = state
        return tuple(output)

    def _cycles(
        self,
        timeline: tuple[SeasonTimeline, ...],
    ) -> tuple[CompetitiveCycle, ...]:
        def family(state: str) -> str:
            if state in {"contender", "elite_contender"}:
                return "contention"
            if state == "rebuild":
                return "rebuild"
            return "transition"

        groups: list[list[SeasonTimeline]] = []
        for row in timeline:
            if not groups or family(groups[-1][-1].state) != family(row.state):
                groups.append([row])
            else:
                groups[-1].append(row)
        cycles: list[CompetitiveCycle] = []
        for index, rows in enumerate(groups, 1):
            kind = family(rows[0].state)
            effective = {
                row.season: (
                    1
                    if row.championship
                    else 2
                    if row.championship_game
                    else min(4, row.finish)
                    if row.final_four and row.finish is not None
                    else row.finish
                )
                for row in rows
            }
            finishes = [finish for finish in effective.values() if finish is not None]
            peak = min(finishes) if finishes else None
            peak_years = tuple(
                row.season for row in rows if effective[row.season] == peak
            )
            reload_time = None
            if kind == "contention" and index > 1:
                previous = groups[index - 2]
                if family(previous[0].state) != "contention":
                    reload_time = rows[0].season - previous[0].season
            cycles.append(
                CompetitiveCycle(
                    f"cycle-{index}-{rows[0].season}-{rows[-1].season}",
                    kind,
                    rows[0].season,
                    rows[-1].season,
                    len(rows),
                    peak,
                    peak_years,
                    sum(row.championship for row in rows),
                    sum(row.playoff for row in rows),
                    len(rows) if kind == "rebuild" else 0,
                    reload_time,
                    (
                        f"{kind.title()} cycle from {rows[0].season} through "
                        f"{rows[-1].season} ({len(rows)} season(s))."
                    ),
                )
            )
        return tuple(cycles)

    def _windows(
        self,
        timeline: tuple[SeasonTimeline, ...],
    ) -> tuple[HistoricalWindow, ...]:
        if not timeline:
            return ()
        years = tuple(row.season for row in timeline)
        definitions = (
            ("full_history", years),
            ("trailing_10", years[-10:]),
            ("trailing_5", years[-5:] if len(years) >= 5 else ()),
            ("trailing_3", years[-3:] if len(years) >= 3 else ()),
        )
        windows = [
            HistoricalWindow(
                key,
                selected[0],
                selected[-1],
                selected,
                True,
                clamp(len(selected) / 10 * 100),
            )
            for key, selected in definitions
            if selected
        ]
        current: list[int] = []
        current_family = (
            "contention"
            if timeline[-1].state in {"contender", "elite_contender"}
            else "rebuild"
            if timeline[-1].state == "rebuild"
            else "transition"
        )
        for row in reversed(timeline):
            row_family = (
                "contention"
                if row.state in {"contender", "elite_contender"}
                else "rebuild"
                if row.state == "rebuild"
                else "transition"
            )
            if row_family != current_family:
                break
            current.append(row.season)
        current.reverse()
        if current:
            windows.append(
                HistoricalWindow(
                    "current_cycle",
                    current[0],
                    current[-1],
                    tuple(current),
                    True,
                    clamp(len(current) / 5 * 100),
                )
            )
        unique: dict[tuple[str, tuple[int, ...]], HistoricalWindow] = {
            (window.key, window.seasons): window for window in windows
        }
        return tuple(unique.values())

    @staticmethod
    def _strengths(
        timeline: tuple[SeasonTimeline, ...],
        cycles: tuple[CompetitiveCycle, ...],
    ) -> tuple[str, ...]:
        strengths: list[str] = []
        titles = sum(row.championship for row in timeline)
        playoffs = sum(row.playoff for row in timeline)
        if titles:
            strengths.append(f"{titles} championship(s).")
        if playoffs:
            strengths.append(f"{playoffs} playoff appearance(s).")
        longest = max(
            (cycle.duration for cycle in cycles if cycle.cycle_type == "contention"),
            default=0,
        )
        if longest >= 3:
            strengths.append(f"{longest}-season sustained contention window.")
        return tuple(strengths)

    @staticmethod
    def _weaknesses(
        timeline: tuple[SeasonTimeline, ...],
        cycles: tuple[CompetitiveCycle, ...],
    ) -> tuple[str, ...]:
        weaknesses: list[str] = []
        longest = max(
            (cycle.duration for cycle in cycles if cycle.cycle_type == "rebuild"),
            default=0,
        )
        if longest > 2:
            weaknesses.append(f"{longest}-season rebuild exceeded the target.")
        losing = sum(
            (row.wins or 0) < (row.losses or 0)
            for row in timeline
            if row.wins is not None and row.losses is not None
        )
        if losing >= 3:
            weaknesses.append(f"{losing} losing season(s).")
        return tuple(weaknesses)


def analysis_payload(analysis: ResultsAnalysis) -> dict:
    """Return a stable JSON-ready Results analysis payload."""
    return json.loads(json.dumps(asdict(analysis), sort_keys=True))
