"""Factual retained franchise events. No graphs, grades, forecasting or providers."""
import json

from src.core.gm_behavioral_intelligence.activity import summarize_activity
from src.core.history_context.assets import future_pick_id
from src.core.history_context.coverage import transaction_coverage_summary
from src.core.history_context.ownership import reconcile_ownership


def franchise_timeline(graph, roster_id, *, page=1, per_page=25):
    roster_id = str(roster_id)
    target = f'{graph.league_id}:franchise:{roster_id}'
    version = graph.store.dataset_version(graph.league_id)
    def retained(kind):
        # Missing optional families must not fall back to projecting every
        # player-week/matchup family merely to display a factual ledger.
        if kind not in graph._records_cache:
            reader = getattr(graph.store, 'optional_records', graph.store.records)
            count, rows = reader(graph.league_id, kind, limit=100_000)
            graph._records_cache[kind] = rows
            if count > len(rows):
                graph._partial_record_families.add(kind)
        return graph._records_cache[kind]

    identities = retained('franchise_identity')
    own = [r for r in identities if r.get('franchise_id') == target]
    reader = getattr(graph.store, 'transaction_coverage', None)
    coverage = reader(graph.league_id) if reader else {'seasons': []}
    sources = {r['season']: r for r in coverage.get('seasons') or []}
    league_rows = retained('league_season')
    for r in league_rows:
        p = r['payload']
        sources.setdefault(r['season'], {'season': r['season'],
            'source_league_id': p.get('sleeper_season_league_id'),
            'previous_league_id': p.get('previous_league_id'), 'source_status': p.get('status')})

    def identity(rid, year):
        rows = [r['payload'] for r in identities if r['season'] == year
                and str(r['payload'].get('sleeper_roster_id')) == str(rid)]
        names = {r.get('dtos_display_name') for r in rows if r.get('dtos_display_name')}
        return next(iter(names)) if len(names) == 1 else 'Franchise identity not established'

    # Existing ownership rules join only actual source continuation links.
    facts = []
    for year, source in sources.items():
        if source.get('source_league_id'):
            facts.append({'league': {'league_id': source['source_league_id'], 'season': year,
                'previous_league_id': source.get('previous_league_id')},
                'rosters': [{'roster_id': r['payload'].get('sleeper_roster_id'),
                    'owner_id': r['payload'].get('owner_id'), 'co_owners': r['payload'].get('co_owners') or []}
                    for r in identities if r['season'] == year]})
    source_ids = [r['league']['league_id'] for r in facts]
    try:
        ownership = (reconcile_ownership(facts) if len(set(source_ids)) == len(source_ids) else
                     {'ownership_changes': [], 'gaps': [{'reason': 'conflicting_season_source_identity'}]})
    except ValueError:
        ownership = {'ownership_changes': [], 'gaps': [{'reason': 'invalid_source_continuation'}]}
    linked, cursor = set(), str(graph.league_id)
    by_source = {str(r['source_league_id']): r for r in sources.values() if r.get('source_league_id')}
    while cursor in by_source and cursor not in linked:
        linked.add(cursor)
        cursor = str(by_source[cursor].get('previous_league_id') or '')

    retained('trade')
    retained('transaction')
    archived = graph.transaction_archive()
    unique, conflicts = {}, set()
    for r in archived:
        key = (r['source']['source_league_id'], r['sleeper_transaction_id'])
        value = json.dumps({k: r[k] for k in ('season', 'type', 'status', 'roster_ids', 'adds', 'drops', 'draft_picks', 'waiver_budget')}, sort_keys=True)
        if key in unique and unique[key][0] != value:
            conflicts.add(key)
        unique[key] = value, r
    completed = set()
    summarize_activity(((r['season'], r['source']['source_league_id'], r['raw']) for _, r in unique.values()), [],
        on_completed=lambda league, tid: completed.add((league, tid)))
    events, attempts = [], []
    for key, (_, r) in unique.items():
        parties = {str(x) for x in r['roster_ids']}
        parties.update(str(x) for field in ('adds', 'drops') for x in r[field].values())
        parties.update(str(p.get(k)) for p in r['draft_picks'] for k in ('previous_owner_id', 'owner_id'))
        if roster_id not in parties:
            continue
        year = r['season']
        incompatible = (sources.get(year) or {}).get('source_identity_compatible') is False
        admitted = key in completed and key not in conflicts and not r.get('malformed_consideration') and not incompatible
        row = {'id': r['sleeper_transaction_id'], 'kind': r['type'], 'season': year,
            'week': r['week'], 'occurred_at': r['occurred_at'], 'status': r['status'],
            'source_league_id': key[0], 'completed': admitted, 'assets': [],
            'attribution': 'source-linked roster-slot continuity' if str(key[0]) in linked else 'franchise continuity unconfirmed',
            'reason': 'Conflicting retained transaction versions; movements withheld.' if key in conflicts else
                      'Retained source season is incompatible with the cache-season context; completed movement withheld.' if incompatible else
                      'Malformed source consideration; movements withheld.' if r.get('malformed_consideration') else
                      'Completed movement is supported in this source-season roster slot; continuity with the current franchise is unconfirmed.' if admitted and str(key[0]) not in linked else
                      'Not an admitted completed transaction; no asset movement is inferred.' if not admitted else None,
            'detail_url': r['trade_dossier_url'] if admitted else None}
        if admitted:
            for pid in sorted(set(r['adds']) | set(r['drops'])):
                row['assets'].append({'kind': 'player', 'id': pid,
                    'label': graph.player_identity(pid)['display_label'],
                    'from': identity(r['drops'][pid], year) if pid in r['drops'] else 'Free-agent pool / source not recorded',
                    'to': identity(r['adds'][pid], year) if pid in r['adds'] else 'Released / destination not recorded'})
            for pick in r['draft_picks']:
                exact = future_pick_id(pick, year)
                row['assets'].append({'kind': 'pick', 'id': exact,
                    'label': f"{pick.get('season') or 'Year unknown'} round {pick.get('round') or 'unknown'} · original franchise: "
                             + (identity(pick.get('roster_id'), year) if pick.get('roster_id') is not None else 'not established'),
                    'from': identity(pick.get('previous_owner_id'), year), 'to': identity(pick.get('owner_id'), year)})
            for transfer in r['waiver_budget']:
                amount = transfer.get('amount')
                from math import isfinite
                if isinstance(amount, (int, float)) and not isinstance(amount, bool) and isfinite(amount) and amount >= 0:
                    row['assets'].append({'kind': 'faab', 'id': None, 'label': f'{amount:g} FAAB',
                        'from': identity(transfer.get('sender'), year), 'to': identity(transfer.get('receiver'), year)})
        (events if admitted else attempts).append(row)

    drafts = retained('draft_pick')
    selections = {}
    for r in drafts:
        p = r['payload']
        if r.get('franchise_id') != target:
            continue
        if (sources.get(r['season']) or {}).get('source_identity_compatible') is False:
            continue
        key = (p.get('source_league_id'), p.get('selection_id'))
        if not key[0] or not key[1] or not p.get('player_id'):
            continue  # No invented selecting owner, selection identity or player.
        if key in selections:
            continue
        exact = future_pick_id(p, r['season'], selection=True)
        selections[key] = {'id': key[1], 'kind': 'draft selection', 'season': r['season'],
            'week': None, 'occurred_at': r.get('occurred_at'), 'status': 'observed selection',
            'source_league_id': key[0], 'completed': True,
            'attribution': 'source-linked roster-slot continuity' if str(key[0]) in linked else 'franchise continuity unconfirmed',
            'reason': 'Exact selection time is not recorded.' if not r.get('occurred_at') else None,
            'draft_bounds': [p.get('draft_start_at'), p.get('draft_last_pick_at')],
            'detail_url': None, 'assets': [{'kind': 'selection', 'id': exact,
                'label': f"{r['season']} round {p.get('round') or 'unknown'} · selection {p.get('pick_no')} · " + graph.player_identity(p['player_id'])['display_label'],
                'from': 'Original franchise: ' + (identity(p['original_roster_id'], r['season']) if p.get('original_roster_id') else 'not established'),
                'to': identity(p.get('selecting_roster_id'), r['season'])}]}
    events.extend(selections.values())
    years = set(sources) | {r['season'] for r in own} | {r['season'] for r in events + attempts}
    seasons = []
    for year in sorted(years, reverse=True):
        rows = [r for r in events if r['season'] == year]
        movements = [r for r in rows if r['kind'] != 'draft selection']
        context = sources.get(year) or {}
        summary = transaction_coverage_summary(context, records_present=bool(movements or any(r['season'] == year for r in attempts)))
        observed_identity = any(r['season'] == year for r in own)
        if summary['state'] == 'complete' and (not observed_identity or str(context.get('source_league_id')) not in linked or any(r['season'] == year
                and (r['reason'].startswith('Conflicting') or str(r['status']).casefold() in {'complete', 'completed'}) for r in attempts)):
            summary.update(state='partial', reason='Source periods are acquired, but franchise identity/continuity, conflicting records or unsupported completed-status consideration prevents a complete franchise conclusion.')
        if summary['state'] == 'complete' and graph._partial_record_families & {'trade', 'transaction'}:
            summary.update(state='partial', reason='The bounded retained transaction view is truncated; no empty or complete franchise conclusion is inferred.')
        seasons.append({**summary, 'season': year, 'source_league_id': context.get('source_league_id'),
            'source_generation': context.get('source_generation'), 'identity_observed': observed_identity,
            'prepared_current_fingerprint': context.get('prepared_current_fingerprint'),
            'completed_transactions': len(movements), 'draft_selections': len(rows) - len(movements),
            'no_activity_supported': summary['state'] == 'complete' and observed_identity and not movements,
            'draft_note': 'Observed individual selections; transaction-period coverage does not establish complete draft coverage.',
            'continuity': 'source-linked roster-slot continuity' if str(context.get('source_league_id')) in linked else 'franchise continuity unconfirmed'})
    stable = graph.store.dataset_version(graph.league_id) == version
    if not stable:
        for s in seasons:
            s.update(state='unknown', no_activity_supported=False, reason='Retained source changed while this page was assembled; reload to review coherent coverage.')
    events.sort(key=lambda r: (r['season'], r['occurred_at'] or '', r['id']), reverse=True)
    per_page = per_page if per_page in (10, 25, 50) else 25
    pages = max(1, (len(events) + per_page - 1) // per_page)
    page = min(max(1, page), pages)
    return {'franchise_id': target, 'seasons': seasons, 'events': events[(page - 1) * per_page:page * per_page],
        'attempts': attempts[:50], 'attempts_total': len(attempts), 'total': len(events), 'page': page,
        'pages': pages, 'per_page': per_page, 'ownership': ownership, 'stable_source': stable,
        'earlier_link_gap': bool(cursor), 'provider_calls': 0,
        'qualification': 'Managers are season observations, not verified trade-time actors. Ownership changes do not backdate decisions to the current manager. Undated events have no proven within-season order.'}
