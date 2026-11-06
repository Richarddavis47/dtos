"""Pure adapters from pinned Batch 2 evidence; no SQL, provider or clock reads.

The caller owns publication and league/as-of selection. Previous-season evidence
is displayed separately and never fills a missing current-season measurement.
"""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from .models import DataStatus, ProductionContext, ProductionWindow


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Canonical production requires finite numeric evidence.")
    return float(value)


def _games(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    games = (evidence.get("production") or {}).get("games") or []
    # Source query order is revision/knowledge order, not chronological game order.
    return sorted(games, key=lambda row: (
        int(row.get("season") or evidence.get("season") or 0),
        int(row.get("week") or 0), str(row.get("game_id") or ""),
    ))


def _average(rows: list[dict[str, Any]], field: str, *, raw: bool = False) -> float | None:
    values = [_number((row.get("raw_stats") or {}).get(field) if raw else row.get(field)) for row in rows]
    # Do not silently turn a partial sample into a complete-window average.
    return round(mean(values), 2) if values and all(value is not None for value in values) else None


def _window(label: str, rows: list[dict[str, Any]], season: int | None = None) -> ProductionWindow:
    points = _average(rows, "fantasy_points") if all(
        row.get("availability") == "calculated" for row in rows
    ) else None
    targets, carries = _average(rows, "rec_tgt", raw=True), _average(rows, "rush_att", raw=True)
    touchdowns = []
    for row in rows:
        stats = row.get("raw_stats") or {}
        parts = [_number(stats.get(key)) for key in ("pass_td", "rush_td", "rec_td")]
        touchdowns.append(sum(parts) if all(value is not None for value in parts) else None)
    return ProductionWindow(
        label, points, round(targets + carries, 2) if targets is not None and carries is not None else None,
        targets, carries, _average(rows, "rec", raw=True),
        round(mean(touchdowns), 2) if touchdowns and all(value is not None for value in touchdowns) else None,
        season=season, observation_count=len(rows),
        scored_count=sum(row.get('availability') == 'calculated' and row.get('fantasy_points') is not None for row in rows),
        weeks=tuple(sorted({int(row['week']) for row in rows if row.get('week') is not None})),
        missing_components=tuple(sorted({key for row in rows for key in row.get('missing_components') or ()})),
    )


def canonical_production_context(
    current: dict[str, Any], previous: dict[str, Any] | None = None,
) -> ProductionContext:
    """Keep league, player, scoring and knowledge boundaries inseparable."""
    previous = previous or {}
    if previous:
        for key in ("league_id", "player_id", "scoring_fingerprint"):
            if not current.get(key) or current.get(key) != previous.get(key):
                raise ValueError(f"Canonical production boundary mismatch: {key}.")
        if int(previous["season"]) != int(current["season"]) - 1:
            raise ValueError("Previous production must be the immediately preceding season.")
        if (current.get("production") or {}).get("as_of") != (previous.get("production") or {}).get("as_of"):
            raise ValueError("Canonical production knowledge boundaries differ.")
    games, old_games = _games(current), _games(previous)
    windows = [
        _window(label, games[-size:], current.get("season")) for label, size in
        (("Last Game", 1), ("Last 3 Games", 3), ("Last 5 Games", 5))
    ]
    windows.extend((_window("Season Average", games, current.get("season")), _window("Previous Season Average", old_games, previous.get("season"))))
    complete = bool(games) and all(
        row.get("availability") == "calculated" and _number(row.get("fantasy_points")) is not None
        for row in games
    )
    values = [_number(row["fantasy_points"]) for row in games] if complete else []
    volatility = round(pstdev(values), 2) if len(values) >= 2 else None
    consistency = round(max(0, 100 - volatility * 5)) if volatility is not None else None
    trend = "Unavailable"
    # Two non-overlapping three-game samples, retaining the established 1-point
    # movement criterion. One or two observations do not establish a trend.
    if len(values) >= 6:
        delta = mean(values[-3:]) - mean(values[-6:-3])
        trend = "Rising" if delta > 1 else "Falling" if delta < -1 else "Stable"
    limitations = list(current.get("limitations") or ())
    if not games:
        limitations.append("No current-season NFL sample; prior-season evidence is shown separately.")
    elif not complete:
        limitations.append("Current production scoring is incomplete; no zero or partial-window average is substituted.")
        missing = sorted({key for row in games for key in row.get('missing_components') or ()})
        if missing:
            limitations.append('Missing applicable scoring components: ' + ', '.join(missing) + '.')
    elif len(games) < 6:
        limitations.append("Insufficient current-season sample for production trend.")
    source = "Canonical nflverse production · league scoring · explicit season windows"
    available = any(window.fantasy_points is not None for window in windows)
    return ProductionContext(
        tuple(windows), volatility, consistency, trend, source,
        DataStatus.CACHED if available else DataStatus.UNAVAILABLE,
        max((row.get("knowledge_boundary") for row in (*games, *old_games) if row.get("knowledge_boundary")), default=None),
        tuple(dict.fromkeys(limitations)),
    )


def prepared_analysis_context(snapshot: dict[str, Any], *, league_id: str,
                                player_id: str) -> ProductionContext:
    """Consume a serialized, pinned preparation without re-querying evidence."""
    if str(snapshot.get('league_id') or '') != str(league_id):
        raise ValueError('Prepared production belongs to another league.')
    row = (snapshot.get('players') or {}).get(str(player_id)) or {}
    value = row.get('non_sleeper_analysis') or row.get('production')
    if not value:
        return ProductionContext((), None, None, 'Unavailable', 'Canonical production',
                                 DataStatus.UNAVAILABLE, None, ('Canonical player production is not prepared.',))
    # Older compact caches retained a season sample count outside the windows.
    # Reuse that same-generation count; an absent scored count stays unknown.
    windows = []
    for window in value['windows']:
        window = dict(window)
        sample_key = 'previous_sample_count' if window['label'] == 'Previous Season Average' else 'current_sample_count'
        sample = row.get(sample_key)
        if window.get('observation_count') is None and type(sample) is int and sample >= 0:
            size = {'Last Game': 1, 'Last 3 Games': 3, 'Last 5 Games': 5}.get(window['label'], sample)
            window['observation_count'] = min(sample, size)
            if window.get('fantasy_points') is not None:
                window['scored_count'] = window['observation_count']
        windows.append(window)
    return ProductionContext(
        tuple(ProductionWindow(**{**window, 'weeks': tuple(window.get('weeks') or ()),
            'missing_components': tuple(window.get('missing_components') or ())}) for window in windows),
        value['volatility'], value['consistency'], value['trend'], value['source'],
        DataStatus(value['status']), value['updated_at'], tuple(value.get('limitations') or ()),
    )


def prepared_production_context(snapshot: dict[str, Any], *, league_id: str,
                                player_id: str, data: dict | None = None) -> ProductionContext:
    """Only explicitly admitted Sleeper scores are actual fantasy production.

    Legacy reconstructed values remain separate analysis; never relabel them.
    """
    from .sleeper_actuals import METHOD, player_context
    if str(snapshot.get('league_id') or '') != str(league_id):
        raise ValueError('Prepared production belongs to another league.')
    actuals = snapshot.get('sleeper_actuals') or {}
    if data is not None:
        from .sleeper_actuals import scoring_identity
        league = data.get('league') or {}
        scoring = data.get('scoring_settings') or league.get('scoring_settings') or {}
        source = data.get('season_matchups') or {}
        if (str(league.get('league_id')) != str(league_id)
                or str(league.get('season')) != str(snapshot.get('season'))
                or not scoring or scoring_identity(scoring) != actuals.get('scoring_fingerprint')
                or source.get('semantic_generation') != actuals.get('source_generation')):
            actuals = {}
    if (actuals.get('method_version') != METHOD or actuals.get('league_id') != str(league_id)
            or str(actuals.get('season')) != str(snapshot.get('season'))
            or actuals.get('scoring_fingerprint') != snapshot.get('scoring_fingerprint')):
        return ProductionContext((), None, None, 'Unavailable', 'Sleeper league matchup results',
            DataStatus.UNAVAILABLE, None, ('Compatible Sleeper actual results are not prepared. Retained non-Sleeper calculations are separate analysis, not authoritative fantasy results.',))
    from dataclasses import replace
    context = player_context(actuals, player_id)
    analysis = ((snapshot.get('players') or {}).get(str(player_id)) or {}).get('non_sleeper_analysis') or {}
    usage = tuple({key: window.get(key) for key in ('label', 'season', 'observation_count', 'weeks',
                        'opportunities', 'targets', 'carries', 'receptions', 'touchdowns')}
                  for window in analysis.get('windows') or ())
    return replace(context, usage_analysis=usage)


def bound_production_snapshot(data: dict) -> dict | None:
    """Retain reference analysis but suppress results from another source context."""
    snapshot = data.get('canonical_player_production')
    if not snapshot:
        return snapshot
    from .sleeper_actuals import scoring_identity
    actuals = snapshot.get('sleeper_actuals') or {}
    league = data.get('league') or {}
    settings = data.get('scoring_settings') or league.get('scoring_settings') or {}
    if (str(snapshot.get('league_id')) != str(league.get('league_id'))
            or str(snapshot.get('season')) != str(league.get('season'))
            or not settings or actuals.get('scoring_fingerprint') != scoring_identity(settings)
            or actuals.get('source_generation') != (data.get('season_matchups') or {}).get('semantic_generation')):
        return {**snapshot, 'sleeper_actuals': {}}
    return snapshot
