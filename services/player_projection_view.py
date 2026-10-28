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
    from src.core.intelligence.team_strength import compatible_profile
    prepared = compatible_profile(data, pinned) or {}
    return {str(pid): player_projection_view(data, str(pid), reader, week,
                                            prepared_profile=prepared) for pid in player_ids}


def player_projection_view(data: dict, player_id: str, service, week: int | None = None,
                           *, prepared_profile=None) -> dict:
    league = data.get('league') or {}
    selected = week if week is not None else int(data.get('week') or 1)
    result = {'player_id': player_id, 'league_id': str(league.get('league_id') or ''), 'season': league.get('season'), 'week': selected, 'weeks': [], 'value': None,
              'display': 'Unavailable', 'availability': 'unavailable', 'generation': None,
              'confidence': None,
              'reason': 'Weekly projections have not been prepared for this league and scoring setup. Check the league refresh status, then retry.'}
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
        result['reason'] = 'No prepared Sleeper projection covers this selected week. Choose an available week or retry after the league refresh.'
        return result
    snapshot = service.week_snapshot(selected, generation_snapshot=pinned)
    if not (snapshot and snapshot.get('horizon_generation') == pinned['horizon_generation']
            and snapshot.get('week') == selected and snapshot.get('league_id') == pinned.get('league_id')
            and snapshot.get('season') == pinned.get('season')
            and snapshot.get('scoring_profile_id') == pinned.get('scoring_profile_id')
            and snapshot.get('scoring_settings', {}) == scoring):
        result['reason'] = 'The weekly projection update does not match the current league snapshot. Retry after the league refresh; no older projection was substituted.'
        return result
    row = (snapshot.get('players') or {}).get(str(player_id)) or {}
    from src.core.projection_intelligence.service import projection_row_compatible
    if not projection_row_compatible(snapshot, str(player_id), row):
        result['reason'] = 'This player’s prepared projection conflicts with the selected player, week, season or scoring publication. Retry after the league refresh; no other projection was substituted.'
        return result
    if prepared_profile is None:
        from src.core.intelligence.team_strength import compatible_profile
        prepared_profile = compatible_profile(data, pinned) or {}
    known_bye = (prepared_profile.get('projection_generation') == pinned.get('horizon_generation')
                 and prepared_profile.get('league_id') == pinned.get('league_id')
                 and prepared_profile.get('season') == pinned.get('season')
                 and any(str(player_id) in ((team.get('weekly') or {}).get(selected)
                         or (team.get('weekly') or {}).get(str(selected)) or {}).get('known_bye_player_ids', [])
                         for team in (prepared_profile.get('teams') or {}).values()))
    status = str(row.get('availability') or '').casefold()
    from src.core.projection_intelligence.service import UNAVAILABLE_PLAYER_STATUSES
    participation = (f"NFL bye in Week {selected}; this player is excluded from that week's playable-lineup comparison."
                     if known_bye else
                     f"Listed {status.upper()} at preparation; this player is excluded from current-week playable lineup cover."
                     if status in UNAVAILABLE_PLAYER_STATUSES and selected == pinned.get('week') else
                     'No current NFL team is recorded. This does not establish future signing or playing time.'
                     if row.get('nfl_team_state') == 'unassigned' else None)
    result['participation_note'] = participation
    positions = row.get('fantasy_positions')
    if isinstance(positions, list) and len(positions) > 1:
        result['eligibility_note'] = 'Sleeper fantasy eligibility: ' + ' / '.join(positions) + '. League slot rules determine lineup use.'
    value = number(row.get('canonical_projection'))
    result.update(value=value, snapshot_id=snapshot.get('projection_snapshot_id'),
                  confidence=row.get('projection_confidence'))
    if value is not None:
        # The source adapter owns numeric/display semantics. No scoring or
        # screen-specific rounding is performed here.
        display = row.get('sleeper_web_display_projection')
        result.update(display=str(display) if display is not None else str(value),
                      availability='available', reason=None,
                      display_reason=None if display is not None else row.get('display_reason') or 'Canonical league-scored Sleeper statistics; exact Sleeper display replay is unverified.')
    else:
        reasons = {
            'NO_PLAYER_RECORD': f'No supported Sleeper projection for Week {selected}: no matching player-week record was supplied.',
            'NO_SCORING_STATISTICS': f'No supported Sleeper projection for Week {selected}: a player-week record exists, but contains no usable scoring statistics.',
            'UNSUPPORTED_SCORING': f'No supported Sleeper projection for Week {selected}: the supplied statistics cannot establish points in this scoring setup.',
        }
        result['reason'] = row.get('availability_reason') or reasons.get(row.get('missing_projection_reason')) or 'No supported Sleeper projection is available for this player in the selected week. This is missing evidence, not a zero projection.'
    return result
