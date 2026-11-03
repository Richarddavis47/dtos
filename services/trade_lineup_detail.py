"""Slot-level views over completed canonical lineups; no optimizer or provider work."""
from collections import Counter
from html import escape

from services.trade_lineup_evidence import completed_lineup_admissions, number, same_number, total
from src.core.trade_intelligence.lineup import BENCH_SLOTS, _eligible, eligible_positions
from src.ui.intelligence_presentation import manager_points


def bind_lineup_details(data, result, reader, proposal):
    """Bind identities and already-read weekly publications to this completed DTO.

    Search readers retain these immutable handles locally. This does not refresh,
    solve, persist, or change the canonical impact/qualification records.
    """
    impact = result.get('multi_horizon_impact') or {}
    sides = impact.get('sides') or {}
    snapshot = reader.snapshot() or {}
    identities, owned = {}, {}
    database = data.get('players') or {}
    if not isinstance(database, dict):
        database = {str(p.get('id') or p.get('player_id')): p for p in database}
    for team in data.get('teams') or []:
        rid = str(team.get('roster_id'))
        if rid not in {str(proposal.active_roster_id), str(proposal.partner_roster_id)}:
            continue
        owned[rid] = []
        for player in team.get('players') or []:
            pid = str(player.get('id') or player.get('player_id') or '')
            owned[rid].append(pid)
            source = {**(database.get(pid) or {}), **player}
            name = source.get('full_name') or source.get('name')
            identities[pid] = name if name and str(name) != pid else None
    moves = [[a.asset_id.removeprefix('player:') for a in assets if a.kind == 'player']
             for assets in (proposal.assets_sent, proposal.assets_received)]
    rosters = {}
    for label, rid, outgoing, incoming in (
            ('active', str(proposal.active_roster_id), moves[0], moves[1]),
            ('partner', str(proposal.partner_roster_id), moves[1], moves[0])):
        pre = owned.get(rid, [])
        rosters[label] = {'roster_id': rid, 'pre': pre,
                         'post': [p for p in pre if p not in outgoing] + incoming}
    weeks = sorted({int(w) for side in sides.values() for w in side.get('weekly') or {}})
    publications = {}
    for week in weeks:
        published = reader.week_snapshot(week, generation_snapshot=reader.snapshot()) or {}
        from src.core.projection_intelligence.service import projection_row_compatible
        rows = published.get('players') or {}
        publications[str(week)] = {
            **{k: published.get(k) for k in ('league_id', 'season', 'week', 'scoring_profile_id',
                                            'horizon_generation', 'projection_snapshot_id')},
            'players': {pid: {**{k: rows[pid].get(k) for k in (
                'position', 'fantasy_positions', 'canonical_projection', 'availability', 'source_timestamp')},
                'compatible': projection_row_compatible(published, pid, rows[pid])}
                for pid in identities if pid in rows},
        }
    result['lineup_detail_context'] = {
        'league_id': snapshot.get('league_id'), 'season': snapshot.get('season'),
        'projection_generation': snapshot.get('projection_snapshot_id'),
        'scoring_profile_id': snapshot.get('scoring_profile_id'),
        'required_slots': [str(s).upper() for s in (data.get('league') or {}).get('roster_positions') or []
                           if str(s).upper() not in BENCH_SLOTS],
        'identities': identities, 'rosters': rosters, 'weeks': publications,
        'meaning': 'Analytical optimal lineups; submitted Sleeper starters remain separate and unchanged.',
    }


def lineup_detail_view(result, *, admissions=None):
    """Admit each phase's slot detail independently; never manufacture missing rows."""
    admissions = admissions or completed_lineup_admissions(result)
    context = result.get('lineup_detail_context') or {}
    inputs = (result.get('provenance') or {}).get('inputs') or {}
    projection = inputs.get('projection_evidence') or {}
    expected_context = {'league_id': inputs.get('league_id'), 'season': projection.get('season'),
                        'projection_generation': inputs.get('projection_generation'),
                        'scoring_profile_id': projection.get('scoring_profile_id')}
    compatible = all(v is not None and str(context.get(k)) == str(v) for k, v in expected_context.items())
    required = context.get('required_slots') or []
    compatible &= bool(required)
    sides = {}
    impact = result.get('multi_horizon_impact') or {}
    for side in ('active', 'partner'):
        admitted = admissions[side]
        roster = (context.get('rosters') or {}).get(side) or {}
        observed_side = (impact.get('sides') or {}).get(side) or {}
        side_compatible = compatible and str(roster.get('roster_id')) == str(observed_side.get('roster_id'))
        weeks = {}
        for key, comparison in (observed_side.get('weekly') or {}).items():
            if not (type(key) is int and 1 <= key <= 18 or isinstance(key, str) and key in {str(w) for w in range(1, 19)}):
                continue
            week = int(key)
            source = (context.get('weeks') or {}).get(str(week)) or {}
            expected = projection.get('projection_snapshot_id') if week == projection.get('week') else (
                projection.get('horizon_snapshot_ids') or {}).get(str(week))
            week_compatible = bool(side_compatible and expected and source.get('projection_snapshot_id') == expected
                and source.get('week') == week and source.get('season') == projection.get('season')
                and str(source.get('league_id')) == str(inputs.get('league_id'))
                and source.get('scoring_profile_id') == projection.get('scoring_profile_id')
                and source.get('horizon_generation') == projection.get('horizon_generation')
                and admitted['identity_state'] == 'compatible')
            phases = {}
            for phase in ('pre', 'post'):
                row = comparison.get(phase) or {}
                optimal = row.get('optimal') or {}
                entries = optimal.get('entries') or []
                coverage = row.get('coverage') or {}
                unsupported = optimal.get('unsupported_slots') or []
                valid = bool(week_compatible and row.get('projection_snapshot_id') == expected
                             and entries and len(entries) <= len(required))
                valid &= all(row.get(k) is None or str(row[k]) == str(v) for k, v in (
                    ('week', week), ('season', projection.get('season')),
                    ('scoring_profile_id', projection.get('scoring_profile_id'))))
                qualification = (row.get('reserve_capacity') or {}).get('qualification') or {}
                valid &= qualification.get('scoring_profile_id') in (None, projection.get('scoring_profile_id'))
                seen, slots, displayed = set(), [], []
                for entry in entries:
                    pid, slot = str(entry.get('asset_id') or ''), entry.get('slot')
                    evidence = (source.get('players') or {}).get(pid) or {}
                    valid &= bool(pid and pid not in seen and pid in (roster.get(phase) or [])
                                  and evidence.get('compatible') is True
                                  and slot in required and entry.get('position') in eligible_positions(evidence)
                                  and _eligible(entry.get('position') or '', slot or '')
                                  and same_number(entry.get('projected_points'), evidence.get('canonical_projection')))
                    seen.add(pid)
                    slots.append(slot)
                    displayed.append({**entry, 'name': (context.get('identities') or {}).get(pid)
                                      or 'Player identity not resolved',
                                      'availability': evidence.get('availability') or 'unknown',
                                      'source_timestamp': evidence.get('source_timestamp')})
                valid &= Counter(slots) + Counter(unsupported) == Counter(required)
                valid &= all(number(e.get('projected_points')) for e in entries)
                subtotal = total([e['projected_points'] for e in entries]) if valid else None
                valid &= same_number(subtotal, optimal.get('known_starters_subtotal'))
                complete = bool(valid and not unsupported and optimal.get('available') is True
                                and row.get('available') is True
                                and same_number(subtotal, (admitted['weekly'].get(week) or {}).get(phase)))
                reserve = row.get('reserve_capacity') or {}
                reserve_ids = {e.get('asset_id') for e in reserve.get('entries') or []}
                excluded = set(coverage.get('excluded_player_ids') or [])
                byes = set(row.get('known_bye_player_ids') or [])
                warnings = []
                for pid in sorted(set(roster.get(phase) or []) | excluded):
                    evidence = (source.get('players') or {}).get(pid) or {}
                    state = evidence.get('availability') or 'unknown'
                    roles = ('Starter' if pid in seen else 'Projected reserve' if pid in reserve_ids else 'Rostered player')
                    if pid in byes:
                        reason = 'Bye / no scheduled game in this supported week'
                    elif pid in excluded:
                        reason = ('Excluded from usable cover · ' + state.upper() if state in
                                  {'out', 'ir', 'pup', 'suspended', 'inactive', 'retired'} else
                                  'Excluded from the eligible roster pool; inspect IR/taxi or weekly participation evidence')
                    elif not number(evidence.get('canonical_projection')):
                        reason = 'No compatible projection recorded; not a zero-point replacement'
                    elif state != 'active':
                        reason = 'Availability ' + state + '; projected participation is not confirmed'
                    else:
                        continue
                    if week != projection.get('week'):
                        reason += '; recorded publication status, not an injury recovery date or a forecast that the status persists'
                    warnings.append({'player_id': pid, 'name': (context.get('identities') or {}).get(pid)
                                     or 'Player identity not resolved', 'role': roles, 'reason': reason})
                reserves = []
                for entry in reserve.get('entries') or []:
                    pid = entry.get('asset_id')
                    evidence = (source.get('players') or {}).get(pid) or {}
                    if (valid and pid not in seen and pid in (roster.get(phase) or []) and pid not in excluded
                            and evidence.get('compatible') is True
                            and entry.get('position') in eligible_positions(evidence)
                            and _eligible(entry.get('position') or '', entry.get('slot') or '')
                            and same_number(entry.get('projected_points'), evidence.get('canonical_projection'))):
                        reserves.append({**entry, 'name': (context.get('identities') or {}).get(pid)
                                         or 'Player identity not resolved'})
                reserve_valid = (valid and len(reserves) == len(reserve.get('entries') or [])
                    and len({e['asset_id'] for e in reserves}) == len(reserves)
                    and Counter(e['slot'] for e in reserves) <= Counter(required)
                    and same_number(total([e['projected_points'] for e in reserves]), reserve.get('known_subtotal')))
                if not reserve_valid:
                    reserves = []
                phases[phase] = {'state': 'complete' if complete else 'partial' if valid else 'unavailable',
                    'entries': displayed if valid else [], 'total': subtotal if complete else None,
                    'known_subtotal': subtotal if valid else None, 'unsupported_slots': unsupported if valid else [],
                    'reserves': reserves, 'reserve_complete': bool(reserve_valid and (reserve.get('qualification') or {}).get('calculation_supported') is True),
                    'reserve_limitations': (reserve.get('qualification') or {}).get('limitations') or [],
                    'warnings': warnings if week_compatible else [],
                    'missing_player_count': len(coverage.get('missing_player_ids') or []) if week_compatible else None}
            before = {e['asset_id'] for e in phases['pre']['entries']}
            after = {e['asset_id'] for e in phases['post']['entries']}
            weeks[week] = {'phases': phases, 'entered': sorted(after - before), 'left': sorted(before - after),
                           'projection_snapshot_id': expected, 'state': (admitted['weekly'].get(week) or {}).get('state')}
        sides[side] = weeks
    return {'sides': sides, **expected_context, 'identities': context.get('identities') or {}}


def render_lineup_risks(result, view):
    """Current-week incoming/starter risks only; no extrapolation across weeks."""
    inputs = (result.get('provenance') or {}).get('inputs') or {}
    week = (inputs.get('projection_evidence') or {}).get('week')
    lines = []
    for side, label, field in (('active', 'Your team', 'assets_received'),
                                ('partner', 'Their team', 'assets_sent')):
        row = view['sides'][side].get(week) or {}
        post = (row.get('phases') or {}).get('post') or {}
        relevant = {str(pid).removeprefix('player:') for pid in inputs.get(field) or []}
        relevant.update(e['asset_id'] for e in post.get('entries') or [])
        for warning in post.get('warnings') or []:
            if warning['player_id'] in relevant:
                lines.append(label + ' · Season ' + str(view['season']) + ' · Week ' + str(week)
                             + ': ' + warning['name'] + ' — ' + warning['reason'] + '.')
    return ''.join('<p class="tw-lineup-warning">' + escape(line) + '</p>' for line in dict.fromkeys(lines))


def render_lineup_details(result, *, admissions=None, view=None):
    view = view or lineup_detail_view(result, admissions=admissions)
    sections = []
    def text(value):
        return escape(str(value))
    def table(entries, label):
        required = (result.get('lineup_detail_context') or {}).get('required_slots') or []
        counts, seen = Counter(required), Counter()
        rows = []
        for e in sorted(entries, key=lambda row: required.index(row['slot'])):
            seen[e['slot']] += 1
            slot_label = e['slot'] + (' ' + str(seen[e['slot']]) if counts[e['slot']] > 1 else '')
            rows.append('<tr><th scope="row">' + text(slot_label) + '</th><td>' + text(e['name'])
                        + '<small>' + text(e['position']) + '</small></td><td>'
                        + manager_points(e['projected_points']) + '</td></tr>')
        rows = ''.join(rows)
        return '<table class="tw-lineup-table"><caption>' + label + '</caption><thead><tr><th>Slot</th><th>Player · position</th><th>Points</th></tr></thead><tbody>' + rows + '</tbody></table>'
    for side, label in (('active', 'Your franchise'), ('partner', 'Their franchise')):
        weeks = []
        for week, row in sorted(view['sides'][side].items()):
            phases = []
            for phase, title in (('pre', 'Before trade'), ('post', 'After trade')):
                p = row['phases'][phase]
                html = '<section><h5>' + title + '</h5>'
                if p['state'] == 'unavailable':
                    html += '<p>Individual slot evidence cannot be verified against this week’s compatible total. No complete lineup is shown.</p>'
                else:
                    html += table(p['entries'], title + ' · analytical optimal starters')
                    if p['state'] == 'complete':
                        html += '<p><b>Week total: ' + manager_points(p['total']) + '</b></p>'
                    else:
                        html += '<p>Known subtotal: ' + manager_points(p['known_subtotal']) + '; incomplete lineup, not a comparable team total. Missing eligible starters: ' + text(', '.join(p['unsupported_slots'])) + '.</p>'
                    if p['missing_player_count']:
                        html += '<p>' + str(p['missing_player_count']) + ' rostered player projections are missing; optimal among supported eligible players.</p>'
                    if p['reserves']:
                        html += table(p['reserves'], title + ' · disjoint projected reserve cover')
                    html += '<p>Reserve cover ' + ('has supported projection evidence; availability qualifications still apply.' if p['reserve_complete'] else 'is incomplete; missing replacement effects remain unknown.') + '</p>'
                    html += ''.join('<p class="tw-lineup-warning">' + text(x) + '</p>' for x in p['reserve_limitations'])
                html += ''.join('<p class="tw-lineup-warning">' + text(w['name'] + ' · ' + w['role'] + ': ' + w['reason']) + '</p>' for w in p['warnings'])
                phases.append(html + '</section>')
            changes = []
            for key, title in (('entered', 'Entering optimal starters'), ('left', 'Leaving optimal starters')):
                if row[key]:
                    changes.append(title + ': ' + ', '.join(view['identities'].get(pid) or 'Player identity not resolved' for pid in row[key]))
            timestamps = sorted({str(e['source_timestamp']) for p in row['phases'].values()
                                 for e in p['entries'] if e.get('source_timestamp')})
            observation = ('Source observation: ' + timestamps[0] + (' through ' + timestamps[-1] if len(timestamps) > 1 else '')
                           if timestamps else 'Source observation time is not recorded in this detail; publication qualifications remain in the full evidence.')
            weeks.append('<section class="tw-lineup-week"><h4>' + label + ' · Season ' + text(view['season']) + ' · Week ' + str(week) + '</h4><p>Selected league scoring · ' + text(row.get('state') or 'unsupported') + ' comparison.</p>'
                         + ''.join('<p>' + text(c) + '</p>' for c in changes)
                         + '<div class="tw-lineup-phases">' + ''.join(phases) + '</div><p class="tw-lineup-source">Compatible projection generation: ' + text(view['projection_generation']) + ' · weekly snapshot: ' + text(row['projection_snapshot_id']) + '</p><p class="tw-lineup-source">' + text(observation) + '</p></section>')
        sections.extend(weeks)
    if not sections:
        sections = ['<p>No compatible individual pre/post lineup evidence was retained for this evaluation.</p>']
    return ('<details class="tw-lineup-details"><summary>Before and after · both optimal lineups</summary>'
            '<p>Analytical optimal lineups, independently optimized before and after the proposed trade. These are not your submitted Sleeper starters; no lineup is changed. Conditional projections do not guarantee availability.</p>'
            '<p>Displayed points are rounded; team totals use unrounded projections.</p>'
            + ''.join(sections) + '</details>')
