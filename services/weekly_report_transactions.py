"""Admit completed actions from an existing verified, week-bucketed season.

No fetch, writes, regrading or inference of calendar week from a timestamp.
Historical source league identity must match the selected report season league.
"""
from services.matchup_season import number


def transaction_facts(cached_season, *, league_id, season, week):
    unavailable = {'availability': 'unavailable', 'facts': [],
                   'reason': 'COMPATIBLE_WEEK_TRANSACTION_EVIDENCE_UNAVAILABLE'}
    if cached_season is None or str(cached_season.season) != str(season):
        return unavailable
    facts = cached_season.facts
    league = facts.get('league') or {}
    if str(league.get('league_id')) != str(league_id) or str(league.get('season')) != str(season):
        return unavailable
    buckets = facts.get('transactions') or {}
    rows = buckets.get(str(week))
    if not isinstance(rows, list):
        return unavailable
    selected = {}
    conflicts = set()
    for row in rows:
        kind = row.get('type')
        if row.get('status') != 'complete' or kind not in {'trade', 'waiver', 'free_agent'}:
            continue
        identity = str(row.get('transaction_id') or '')
        # The canonical source bucket owns the period. A conflicting embedded
        # leg is not silently reinterpreted as another week.
        if not identity or (row.get('leg') is not None and row['leg'] != week):
            continue
        adds, drops = row.get('adds') or {}, row.get('drops') or {}
        rosters = set(row.get('roster_ids') or []) | set(adds.values()) | set(drops.values())
        if not rosters or any(type(rid) is not int or rid <= 0 for rid in rosters):
            continue
        bid = number((row.get('settings') or {}).get('waiver_bid'))
        if bid is not None and bid < 0:
            bid = None
        reference = f'transactions/{league_id}/{season}/{week}/{identity}'
        item = {'identity': reference, 'transaction_id': identity, 'type': kind,
                'roster_ids': sorted(rosters), 'adds': dict(sorted(adds.items())),
                'drops': dict(sorted(drops.items())), 'faab': bid,
                'faab_semantic': 'recorded bid; not inferred spending by each participant',
                'period_semantic': 'canonical source week bucket',
                'source_generation': cached_season.checksum,
                'assessment': 'completed action only; no decision-quality conclusion'}
        if identity in selected and selected[identity] != item:
            conflicts.add(identity)
        selected[identity] = item
    return {'availability': 'partial' if conflicts else 'available',
            'facts': [selected[key] for key in sorted(selected) if key not in conflicts],
            'reason': 'CONFLICTING_TRANSACTION_IDENTITIES' if conflicts else None}
