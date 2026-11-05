"""Read-only source coverage, distinct from structural cache validity."""

from __future__ import annotations

from typing import Any


def object_rows(value: Any) -> list[dict]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def list_state(value: Any, *, supplied: bool = True) -> str:
    if not supplied:
        return "unacquired"
    if value is None:
        return "unavailable"
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        return "malformed"
    return "observed" if value else "observed_empty"


def periods(facts: dict, family: str) -> dict:
    """At most the existing 19 transaction / 18 scoring periods; no fetching."""
    league = facts.get("league") if isinstance(facts.get("league"), dict) else {}
    settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    last = 18 if league.get("status") == "complete" else settings.get("leg")
    last = min(18, max(0, int(last))) if str(last).isdigit() else 18
    expected = set(range(0 if family == "transactions" else 1, last + 1))
    buckets = facts.get(family)
    valid = buckets if isinstance(buckets, dict) else {}
    supplied = {int(key) for key in valid if str(key).isdigit() and 0 <= int(key) <= 18}
    states: dict[str, list[int]] = {state: [] for state in (
        "observed", "observed_empty", "unavailable", "unacquired", "malformed")}
    for week in sorted(expected | supplied):
        if week not in supplied:
            state = "unavailable" if family in facts and buckets is None else "unacquired"
            if buckets is not None and not isinstance(buckets, dict):
                state = "malformed"
        else:
            value = valid.get(str(week), valid.get(week))
            state = list_state(value)
        states[state].append(week)
    return {"family": family, **states,
            "acquired": sorted(states["observed"] + states["observed_empty"]),
            "complete_acquisition": not any(states[s] for s in ("unavailable", "unacquired", "malformed")),
            "scope": "Supported Sleeper transaction buckets 0–18" if family == "transactions" else "Supported weekly matchup buckets 1–18"}


def readable_buckets(facts: dict, family: str) -> dict[str, list[dict]]:
    buckets = facts.get(family)
    if not isinstance(buckets, dict):
        return {}
    return {str(key): object_rows(value) for key, value in buckets.items()
            if str(key).isdigit() and int(key) >= (0 if family == "transactions" else 1) and isinstance(value, list)}


def family_observed(facts: dict, family: str) -> bool:
    if family in {"transactions", "matchups"}:
        return bool(readable_buckets(facts, family))
    return isinstance(facts.get(family), list)


def season_coverage(facts: dict, season: int) -> dict:
    league = facts.get("league") if isinstance(facts.get("league"), dict) else {}
    limitations = []
    from .playoffs import admitted_bracket_row
    for family in ('winners_bracket', 'losers_bracket'):
        if any(admitted_bracket_row(row)['outcome_reason_codes'] for row in object_rows(facts.get(family))):
            limitations.append(f'{family.replace("_", " ").title()}: malformed or conflicting outcome identities withheld; independent season evidence remains available.')
    for week, rows in readable_buckets(facts, 'matchups').items():
        if any(not isinstance(row.get('starters'), list) for row in rows):
            limitations.append(f'Week {week}: missing or malformed starters leave lineup roles unknown.')
        if any(not isinstance(row.get('players_points'), dict) for row in rows):
            limitations.append(f'Week {week}: individual scoring components unavailable or malformed.')
    return {"season": season, "source_league_id": league.get("league_id"),
            "transactions": periods(facts, "transactions"),
            "matchups": periods(facts, "matchups"),
            "families": {key: list_state(facts.get(key), supplied=key in facts)
                         for key in ("users", "rosters", "drafts", "draft_picks", "traded_picks", "winners_bracket", "losers_bracket")},
            "weekly_roster_note": "Matchup membership is week-specific; season roster snapshots are not weekly rosters.",
            "optional_field_limitations": limitations,
            "structural_validity_is_acquisition_completeness": False}


def transaction_coverage_summary(coverage: dict, *, records_present=False) -> dict:
    """Season transaction acquisition, never a conclusion from calendar age."""
    periods = coverage.get('transactions') or {}
    acquired = {w for w in periods.get('acquired') or [] if type(w) is int and 0 <= w <= 18}
    gaps = {name: periods.get(name) or [] for name in ('unacquired', 'unavailable', 'malformed')}
    if coverage.get('source_identity_compatible') is False:
        return {'state': 'unknown', 'acquired': [], 'gaps': {},
                'reason': 'Retained source league-season metadata is incompatible with this season; coverage and an empty-history conclusion are withheld.',
                'scope': 'Source context incompatible; other independent seasons remain available.'}
    complete = (periods.get('complete_acquisition') is True and acquired == set(range(19))
                and not any(gaps.values()) and coverage.get('source_status') == 'complete'
                and coverage.get('source_identity_compatible') is True
                and not any(coverage.get(k) for k in ('unqualified_records', 'conflicting_identities', 'unknown_status_records', 'last_valid_periods')))
    state = 'complete' if complete else 'partial' if acquired or records_present else 'unknown'
    reason = ('All supported source transaction buckets 0–18 were retrieved for this completed source season.' if complete else
              'Some source periods or the completed-season confirmation are missing; retained events remain useful.' if state == 'partial' else
              'DTOS has not established which source weeks were retrieved; missing history is not no activity.')
    problems = [f"{coverage[k]} {label}" for k, label in (
        ('unqualified_records', 'records with unverified transaction or franchise identity'), ('conflicting_identities', 'conflicting transaction identities'),
        ('unknown_status_records', 'records with unknown transaction status')) if coverage.get(k)]
    if problems:
        reason += ' Retained gaps: ' + '; '.join(problems) + '.'
    if coverage.get('last_valid_periods'):
        reason += ' Last-valid source periods remain visible after an unavailable refresh: ' + ', '.join(map(str, coverage['last_valid_periods'])) + '.'
    return {'state': state, 'acquired': sorted(acquired), 'gaps': gaps, 'reason': reason,
            'scope': 'Retained Sleeper transaction buckets 0–18; draft selections have separate coverage.'}
