"""Read-only player/week presentation over one published projection horizon."""
from services.matchup_season import number
from types import SimpleNamespace


def player_projection_views(data: dict, player_ids, service, week: int | None = None) -> dict:
    """Pin/read once for an entire compact-card list, not once per card."""
    pinned = service.snapshot() if service is not None else None
    cache = {}
    def read(selected, **kwargs):
        if selected not in cache:
            cache[selected] = service.week_snapshot(selected, generation_snapshot=pinned)
        return cache[selected]
    reader = SimpleNamespace(snapshot=lambda: pinned, week_snapshot=read)
    return {str(pid): player_projection_view(data, str(pid), reader, week) for pid in player_ids}


def player_projection_view(data: dict, player_id: str, service, week: int | None = None) -> dict:
    league = data.get('league') or {}
    selected = week if week is not None else int(data.get('week') or 1)
    result = {'player_id': player_id, 'league_id': str(league.get('league_id') or ''), 'season': league.get('season'), 'week': selected, 'weeks': [], 'value': None,
              'display': 'Unavailable', 'availability': 'unavailable', 'generation': None,
              'confidence': None,
              'reason': 'Compatible prepared projection evidence is unavailable.'}
    pinned = service.snapshot() if service is not None else None
    scoring = data.get('scoring_settings') or league.get('scoring_settings') or {}
    if not (pinned and str(pinned.get('league_id')) == str(league.get('league_id'))
            and str(pinned.get('season')) == str(league.get('season'))
            and pinned.get('scoring_settings', {}) == scoring and pinned.get('horizon_generation')):
        return result
    manifest = pinned.get('horizon_snapshot_ids') or {}
    result['weeks'] = sorted(int(w) for w in manifest if str(w).isdecimal() and 1 <= int(w) <= 18)
    result['generation'] = pinned['horizon_generation']
    if str(selected) not in manifest:
        result['reason'] = 'This week is outside the currently prepared source horizon.'
        return result
    snapshot = service.week_snapshot(selected, generation_snapshot=pinned)
    if not (snapshot and snapshot.get('horizon_generation') == pinned['horizon_generation']
            and snapshot.get('week') == selected and snapshot.get('league_id') == pinned.get('league_id')
            and snapshot.get('season') == pinned.get('season')
            and snapshot.get('scoring_profile_id') == pinned.get('scoring_profile_id')
            and snapshot.get('scoring_settings', {}) == scoring):
        return result
    row = (snapshot.get('players') or {}).get(str(player_id)) or {}
    value = number(row.get('canonical_projection'))
    result.update(value=value, snapshot_id=snapshot.get('projection_snapshot_id'),
                  confidence=row.get('projection_confidence'))
    if value is not None:
        # The source adapter owns numeric/display semantics. No scoring or
        # screen-specific rounding is performed here.
        display = row.get('sleeper_web_display_projection')
        result.update(display=str(display) if display is not None else str(value),
                      availability='available', reason=None)
    else:
        result['reason'] = row.get('availability_reason') or 'No supported player projection for this week.'
    return result
