"""Digestible presentation of admitted season facts; no historical reconstruction."""
from html import escape


def season_history_summary(archive):
    season = archive['season']
    result = (archive.get('playoffs') or {}).get('result') or {}
    # Some admitted archives retain a franchise identifier but no roster-id
    # join. Do not manufacture that join from a display name or identifier.
    names = {str(row['roster_id']): row for row in archive.get('standings') or []
             if row.get('roster_id') is not None}
    achievements = []
    for key, label in (('champion_roster_id', 'Champion'), ('runner_up_roster_id', 'Finalist'),
                       ('qualified_roster_ids', 'Playoff qualification'), ('first_round_bye_roster_ids', 'First-round bye · playoff qualification'),
                       ('semifinal_roster_ids', 'Final Four')):
        raw = result.get(key)
        ids = raw if isinstance(raw, list) else [] if raw is None else [raw]
        for rid in dict.fromkeys(map(str, ids)):
            row = names.get(rid, {})
            name = row.get('team_name') or f'Franchise {rid}'
            manager = row.get('gm_name') or 'Season manager unavailable'
            achievements.append(f'<article class="card"><span>{escape(label)}</span><h4>{escape(name)}</h4>'
                                f'<p>{season} · season-recorded GM: {escape(manager)}</p></article>')
    # Canonical weekly results supply winners; never infer from current state or
    # compare playoff component weeks as separate round meetings.
    pairs, seen = {}, set()
    for week in archive.get('weeks') or []:
        for match in week.get('matchups') or []:
            teams = match.get('teams') or []
            identity = (week['week'], match.get('matchup_id'))
            if identity in seen or match.get('postseason') or len(teams) != 2:
                continue
            seen.add(identity)
            ids = tuple(sorted(str(team['roster_id']) for team in teams))
            winner = str(match.get('winner_roster_id'))
            tied = match.get('tie') is True
            if ids[0] == ids[1] or not (tied or winner in ids):
                continue
            row = pairs.setdefault(ids, {'meetings': 0, 'wins': {rid: 0 for rid in ids}, 'ties': 0})
            row['meetings'] += 1
            if tied:
                row['ties'] += 1
            else:
                row['wins'][winner] += 1
    meetings = []
    for (a, b), row in sorted(pairs.items()):
        aname = names.get(a, {}).get('team_name') or f'Franchise {a}'
        bname = names.get(b, {}).get('team_name') or f'Franchise {b}'
        meetings.append(f'<article class="card"><h4>{escape(aname)} vs {escape(bname)}</h4><p>{row["meetings"]} retained completed regular-season meetings</p>'
                        f'<p>{escape(aname)} wins: {row["wins"][a]} · {escape(bname)} wins: {row["wins"][b]} · Ties: {row["ties"]}</p></article>')
    return ('<section class="season-history-summary"><h3>Verified season achievements</h3>'
            '<p>Season franchise facts, not the current manager’s career or overall FOIS. '
            'A first-round bye counts as playoff qualification; round appearances are not counted once per component week.</p>'
            '<div class="grid">' + (''.join(achievements) or '<p>Verified postseason achievements unavailable.</p>') + '</div>'
            '<details><summary>Season franchise head-to-head</summary><p>Retained completed regular-season meetings only. '
            'Not an all-time or manager-tenure record. Playoff component weeks are excluded. '
            'These facts alone do not establish a rivalry or a career milestone.</p><div class="grid">'
            + (''.join(meetings) or '<p>Comparable completed meetings unavailable.</p>') + '</div></details></section>')


def season_draft_selections(archive):
    """Readable retained selections; never join to current owners or players."""
    names = {str(row['roster_id']): row.get('team_name')
             for row in archive.get('standings') or [] if row.get('roster_id') is not None}
    records = (archive.get('draft') or {}).get('picks') or []
    rows = []
    for record in records[:500]:
        payload = record.get('payload') or {}
        metadata = payload.get('metadata') or {}
        metadata = metadata if isinstance(metadata, dict) else {}
        player_id = str(record.get('player_id') or payload.get('player_id') or '')
        player_name = ' '.join(str(metadata.get(key) or '').strip()
                               for key in ('first_name', 'last_name')).strip()
        player = escape(player_name or ('Player ' + player_id if player_id else 'Player identity not recorded'))
        number = payload.get('pick_no')
        round_ = payload.get('round')
        # Sleeper picked_by is a user ID, not a franchise identity. Legacy
        # importer aliases also do not establish the exact original pick.
        original = payload.get('original_roster_id')
        owner = payload.get('selecting_roster_id') or payload.get('roster_id')
        def franchise(identity):
            return escape(str(names.get(str(identity)) or ('Franchise ' + str(identity)))) if identity is not None else 'Not recorded'
        rows.append('<li><b>' + ('Selection ' + escape(str(number)) if number is not None else 'Selection number not recorded')
                    + '</b>' + (' · round ' + escape(str(round_)) if round_ is not None else '')
                    + ' · ' + player + '<p>Original franchise: ' + franchise(original)
                    + ' · Selected by: ' + franchise(owner) + '</p></li>')
    if not rows:
        return '<p>No retained draft selections are available for this season. Missing records do not establish an empty draft.</p>'
    first = '<ol class="history-selections">' + ''.join(rows[:10]) + '</ol>'
    rest = ('<details><summary>More recorded selections · ' + str(len(rows) - 10) + '</summary><ol class="history-selections" start="11">'
            + ''.join(rows[10:]) + '</ol></details>') if len(rows) > 10 else ''
    return first + rest + '<p class="muted">Recorded draft selections, not current ownership or a complete trade history.</p>'


def season_postseason_results(archive):
    """Reuse the canonical retained-outcome guard before displaying brackets."""
    from src.core.history_context.playoffs import admitted_bracket_row, roster_identity
    names = {int(row['roster_id']): row.get('team_name')
             for row in archive.get('standings') or [] if roster_identity(row.get('roster_id')) is not None}
    def franchise(identity):
        return escape(str(names.get(identity) or ('Franchise ' + str(identity)))) if identity is not None else 'Not recorded'
    rows = []
    for record in ((archive.get('playoffs') or {}).get('brackets') or [])[:10]:
        payload = record.get('payload') or {}
        bracket_name = 'Championship bracket' if payload.get('type') == 'winners' else 'Consolation bracket' if payload.get('type') == 'consolation' else 'Recorded bracket'
        matches = []
        for raw in (payload.get('bracket') or [])[:100]:
            if not isinstance(raw, dict):
                continue
            row = admitted_bracket_row(raw, set(names))
            participants = franchise(row.get('t1')) + ' vs ' + franchise(row.get('t2'))
            outcome = 'Winner: ' + franchise(row['w']) if row.get('w') is not None else 'Winner not established from the retained result.'
            matches.append('<li>' + participants + '<p>' + outcome + '</p></li>')
        if matches:
            rows.append('<h4>' + bracket_name + '</h4><ul>' + ''.join(matches) + '</ul>')
    return ''.join(rows) or '<p>Detailed playoff match results are not retained. Any supported champion or placement is shown above; no bracket is reconstructed.</p>'
