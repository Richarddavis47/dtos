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
