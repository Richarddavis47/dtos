"""League-relative grading of explicit, generation-bound evidence dimensions."""
from __future__ import annotations

from statistics import mean
from typing import Any

from src.core.competitive_window import build_competitive_window
from src.core.team_intelligence.models import LeagueTeamSummary, RelativeGrade, TeamIntelligenceCard
from src.core.asset_intelligence.picks.pick_value import dynasty_pick_value
from src.core.valuation import normalize_pick

POSITIONS = ("QB", "RB", "WR", "TE")


def _percentile(value: float, population: tuple[float, ...]) -> int:
    if not population or max(population) == min(population):
        return 50
    below = sum(item < value for item in population)
    equal = sum(item == value for item in population)
    return round((below + equal * .5) / len(population) * 100)


def _letter(percentile: int) -> str:
    for threshold, label in ((90, "A+"), (80, "A"), (65, "A-"), (50, "B+"), (40, "B"), (30, "C"), (20, "D")):
        if percentile >= threshold:
            return label
    return "F"


def _rank(value: float, population: tuple[float, ...]) -> int:
    return 1 + sum(item > value for item in population)


def _relative(category: str, roster_id: int, raw: dict[int, dict[str, float]], reasons: tuple[str, ...]) -> RelativeGrade:
    value = raw[roster_id][category]
    population = tuple(row[category] for row in raw.values())
    percentile = _percentile(value, population)
    return RelativeGrade(category, percentile, _letter(percentile), percentile, _rank(value, population), len(population), reasons)


def _pick_value(picks: tuple[dict[str, Any], ...]) -> float:
    return sum(
        normalize_pick(
            dynasty_pick_value(pick).score,
            int(pick.get("round") or 4),
        )
        for pick in picks
    )


def build_team_intelligence(
    decisions: dict[int, Any],
    league_rooms: dict[int, dict[str, int]],
    league_players: dict[int, dict[str, Any]],
    league_metrics: dict[int, dict[str, float]],
    *, grading=None,
) -> tuple[dict[int, TeamIntelligenceCard], LeagueTeamSummary]:
    if grading is not None:
        return _from_grading_evidence(decisions, grading)
    raise ValueError('Generation-bound roster grading evidence is required; legacy scalar fallback is retired.')


def _from_grading_evidence(decisions, grading):
    """Adapt the generation-bound dimensions; never reuse legacy card scores."""
    from src.core.intelligence.roster_grading import rank_roster_dimension
    rows = tuple(grading.values())
    if set(grading) != set(decisions):
        raise ValueError('Every franchise requires the same evidence boundary')
    ranks = {name: rank_roster_dimension(rows, name) for name in rows[0].dimensions} if rows else {}
    size = len(rows)
    def unavailable(name):
        return RelativeGrade(name, None, 'Unavailable', None, None, size,
            ('No validated aggregate for this concept; unrelated scalar evidence is not substituted.',))
    def dimension(roster_id, name):
        item = grading[roster_id].dimensions[name]
        values = tuple(row.dimensions[name].value for row in rows if row.dimensions[name].value is not None)
        if item.value is None:
            return unavailable(name)
        percentile = _percentile(item.value, values)
        return RelativeGrade(name, percentile, _letter(percentile), percentile,
            ranks[name][roster_id], size,
            (f'{item.value:g} {item.units}; coverage {item.covered}/{item.expected}.',
             'This dimension is not an overall dynasty or competitive-window grade.'))
    cards = {}
    picks = {key: {'Future Capital': _pick_value(item.profile.picks)} for key, item in decisions.items()}
    for roster_id, decision in decisions.items():
        lineup = dimension(roster_id, 'Optimal projected lineup')
        depth = dimension(roster_id, 'Useful projected depth')
        overall = unavailable('Overall team assessment')
        future = unavailable('Long-term dynasty utility')
        draft = _relative('Future Capital', roster_id, picks, ('Existing canonical pick model; separate from player value.',))
        window = build_competitive_window(current_strength=lineup.score, overall_strength=None,
            future_strength=None, depth=depth.score, youth=None, draft_capital=draft.score,
            risk=None, confidence=0)
        cards[roster_id] = TeamIntelligenceCard(roster_id, overall, lineup,
            unavailable('Intrinsic dynasty utility'), lineup, depth,
            {position: unavailable(f'{position} evidence assessment') for position in POSITIONS},
            draft, dimension(roster_id, 'Longevity context'), future,
            unavailable('Roster flexibility'), unavailable('Asset liquidity'), window,
            lineup.score, None, None, 0,
            ('Supported dimensions are published separately; no ambiguous overall grade is manufactured.',
             'Competitive Window is unavailable until all required team-level evidence is supported.'),
            decision.profile.wins + decision.profile.losses + decision.profile.ties == 0,
            None, None, None, None, dimension(roster_id, 'Market asset strength'),
            dimension(roster_id, 'Production quality'),
            grading[roster_id].league_id, grading[roster_id].generation)
    ages = [age for decision in decisions.values() for age in decision.profile.known_ages]
    summary = LeagueTeamSummary(None, mean(ages) if ages else None, None, 0, 0,
        'Unavailable', 'Unavailable', None, None, 'Unavailable', 'Unavailable',
        None, None, None, None, None, 'Evidence dimensions')
    return cards, summary
