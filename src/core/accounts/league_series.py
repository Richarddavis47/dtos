"""Authoritative grouping of Sleeper season leagues into dynasty series."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class LeagueSeries:
    series_id: str
    current_league: dict[str, Any]
    seasons: tuple[dict[str, Any], ...]

    @property
    def current_league_id(self) -> str:
        return str(self.current_league["league_id"])

    def public(self) -> dict[str, Any]:
        return {
            "series_id": self.series_id,
            "league_id": self.current_league_id,
            "name": self.current_league.get("name"),
            "season": self.current_league.get("season"),
            "total_rosters": self.current_league.get("total_rosters"),
            "historical_seasons": [
                {"league_id": str(row["league_id"]), "season": row.get("season")}
                for row in self.seasons if str(row["league_id"]) != self.current_league_id
            ],
        }


def _season(row: dict[str, Any]) -> int:
    value = str(row.get("season") or "")
    return int(value) if value.isdigit() else -1


def group_league_series(leagues: Iterable[dict[str, Any]]) -> tuple[LeagueSeries, ...]:
    """Group only through explicit ``previous_league_id`` relationships.

    Names never participate in identity. Missing links remain separate rather than
    being guessed, and there is no calendar cutoff or terminal season.
    """
    rows = {
        str(row["league_id"]): dict(row)
        for row in leagues if str(row.get("league_id") or "").isdigit()
    }
    referenced = {
        str(row.get("previous_league_id")) for row in rows.values()
        if str(row.get("previous_league_id") or "") in rows
    }
    leaves = sorted(set(rows) - referenced) or sorted(rows)
    result: list[LeagueSeries] = []
    claimed: set[str] = set()
    for current_id in leaves:
        members: list[dict[str, Any]] = []
        cursor = current_id
        seen: set[str] = set()
        while cursor in rows and cursor not in seen and cursor not in claimed:
            seen.add(cursor)
            claimed.add(cursor)
            row = rows[cursor]
            members.append(row)
            cursor = str(row.get("previous_league_id") or "")
        ordered = sorted(members, key=lambda row: (_season(row), str(row["league_id"])))
        if ordered:
            result.append(LeagueSeries(str(ordered[0]["league_id"]), ordered[-1], tuple(reversed(ordered))))
    for league_id in sorted(set(rows) - claimed):
        row = rows[league_id]
        result.append(LeagueSeries(league_id, row, (row,)))
    return tuple(sorted(result, key=lambda item: (-_season(item.current_league), str(item.current_league.get("name") or ""), item.series_id)))
