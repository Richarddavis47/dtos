"""Scope-aware archive presentation using the shared Transactions filters."""

from __future__ import annotations

from collections import defaultdict
from math import ceil
from datetime import datetime

from services.transactions import PAGE_SIZES, filter_transactions, normalize_transactions, sort_transactions


def archive_view(graph, data: dict, filters: dict) -> dict:
    scope = filters.get('scope')
    rows = graph.transaction_archive() if scope in {'current_season', 'all_history'} else []
    if scope == 'current_season':
        rows = [r for r in rows if str(r['season']) == str((data.get('league') or {}).get('season'))]
    elif scope != 'all_history':
        rows = []
    rows = [r for r in rows if
            (filters.get('season') is None or r['season'] == filters['season'])
            and (filters.get('week') is None or r['week'] == filters['week'])
            and (not filters.get('status') or r['status'] == filters['status'])]
    by_season = defaultdict(list)
    for row in rows:
        by_season[row['season']].append(row)
    identities = graph._records('franchise_identity') if rows else []
    admitted = []
    originals = {}
    for season, source in by_season.items():
        teams = [{'roster_id': r['payload'].get('sleeper_roster_id'),
                  'team_name': r['payload'].get('dtos_display_name'),
                  'owner': r['payload'].get('sleeper_username')}
                 for r in identities if r['season'] == season]
        presentation_rows = []
        for row in source:
            raw = dict(row['raw'])
            # Canonical source time may use status_updated when created is
            # absent. This transient input never replaces the retained raw row.
            timestamp = row.get('occurred_at')
            raw['created'] = int(datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp() * 1000) if timestamp else 0
            presentation_rows.append(raw)
        normalized = normalize_transactions({'players': data.get('players') or {},
                                             'teams': teams, 'transactions': presentation_rows})
        originals.update({(season, r['sleeper_transaction_id']): r for r in source})
        for row in normalized:
            row['_source_season'] = season
        admitted.extend(filter_transactions(normalized, filters))
    ordered = sort_transactions(admitted, filters.get('sort') or 'date', filters.get('direction') or 'desc')
    size = int(filters.get('per_page') or 25)
    size = size if size in PAGE_SIZES else 25
    pages = max(1, ceil(len(ordered) / size))
    page = min(max(1, int(filters.get('page') or 1)), pages)
    selected = ordered[(page - 1) * size:page * size]
    return {'rows': [{**originals[(r['_source_season'], r['id'])],
                     'franchise_summary': ', '.join(t['team_name'] for t in r['teams']),
                     'asset_labels': [a['label'] for a in r['assets']]}
                    for r in selected],
            'total_filtered': len(ordered), 'page': page, 'page_count': pages, 'per_page': size,
            'owners': sorted({r['payload'].get('sleeper_username') for r in identities
                              if r['payload'].get('sleeper_username')}, key=str.casefold),
            'qualification': 'Manager filter uses season-observed managers; exact trade-time takeover dates are not established. Undated events cannot satisfy date filters.'}
