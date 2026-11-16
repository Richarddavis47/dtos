"""One observed subsequent package per original receipt, never allocated proceeds.

Uses the canonical graph and directed-consideration contract. No acquisition,
prices, persistent lineage, recursion into returned assets or new runtime owner.
"""
from collections import OrderedDict
from datetime import datetime

from src.core.gm_behavioral_intelligence.diagnostics import _movement_evidence
from src.core.history_context.timestamps import canonical_utc_timestamp

COMPLETED = {'complete', 'completed'}


def next_exchanges(graph, dossier, branches, *, franchise, label, bounds, selections,
                   max_events=100, max_assets=40):
    packages = OrderedDict()
    stamp = canonical_utc_timestamp(dossier.get('occurred_at'))
    root_time = datetime.fromisoformat(stamp) if stamp else None
    def interval(event):
        low, high = bounds(event)
        return (datetime.fromisoformat(low) if low else None,
                datetime.fromisoformat(high) if high else None)
    root_source = str(dossier['source']['source_league_id'])
    root_raw = dossier.get('raw_transaction') or {}
    _, root_moves, _, _ = _movement_evidence(root_raw)
    root_record = graph.store.transaction_record(graph.league_id, dossier['transaction_id'])
    root_conflict = not root_record or root_record['payload'].get('history_transaction_conflict')
    seasons = graph._records('league_season')
    links = {}
    for row in seasons:
        source = str(row['payload'].get('sleeper_season_league_id') or graph.league_id)
        links.setdefault(source, set()).add((row['season'], str(row['payload'].get('previous_league_id') or '')))
    remaining = max_events

    def source_supported(event):
        source = str(event.get('source_league_id') or '')
        if event['season'] < dossier['season']:
            return False
        if source == root_source:
            return event['season'] == dossier['season']
        visited = set()
        while source != root_source and source not in visited:
            visited.add(source)
            rows = links.get(source) or set()
            if len(rows) != 1:
                return False
            season, previous = next(iter(rows))
            previous_rows = links.get(previous) or set()
            if len(previous_rows) != 1 or next(iter(previous_rows))[0] >= season:
                return False
            source = previous
        return source == root_source

    def identity(move):
        kind, asset, *_ = move
        return 'DTOS-P-' + asset if kind == 'player' else asset

    def resolve(branch):
        nonlocal remaining
        original = branch['asset_id']
        receipts = [m for m in root_moves if identity(m) == original]
        if root_conflict or not root_time or len(receipts) != 1:
            return None, 'Original receipt identity, transaction agreement or time is not established.'
        owner = f'{graph.league_id}:franchise:{receipts[0][3]}'
        current, boundary, converted_selection = original, root_time, None
        conversion_low = None
        for _ in range(2):  # At most the original asset and its exact selected player.
            grouped = OrderedDict()
            for event in graph.events(asset_id=current):
                if event['event_status'].casefold() not in COMPLETED or event['event_type'] in {'pick_snapshot', 'roster_snapshot'}:
                    continue
                if event.get('parent_id') == dossier['trade_id']:
                    continue
                if converted_selection and event['event_type'] == 'draft_selection' and str(event['source_record_id']) == converted_selection:
                    continue
                low, high = interval(event)
                if not low or not high or low > high:
                    return None, 'Missing event dates prevent identifying the first later exchange.'
                if conversion_low is not None and high >= conversion_low and low <= boundary:
                    return None, 'Equal or overlapping conversion and movement dates leave the continuation unknown.'
                if high < boundary:
                    continue
                if low <= boundary:
                    return None, 'Equal or overlapping event dates leave the continuation unknown.'
                key = (event.get('parent_id'), event['source_record_id'], event['event_type'])
                grouped.setdefault(key, []).append(event)
            if len(grouped) > remaining:
                remaining = 0
                return None, 'The bounded event limit was reached; the first later exchange is unknown.'
            remaining -= len(grouped)
            ordered = sorted(grouped.values(), key=lambda rows: interval(rows[0]))
            if not ordered:
                return None, 'No supported next exchange in the retained records; missing history may contain later movements.'
            rows = ordered[0]
            event = rows[0]
            low, high = interval(event)
            if len(ordered) > 1 and interval(ordered[1][0])[0] <= high:
                return None, 'Equal or overlapping event dates leave the continuation unknown.'
            if not source_supported(event):
                return None, 'The source league-season chain does not establish this continuation.'
            senders = {e['from_franchise_id'] for e in rows if e.get('from_franchise_id')}
            receivers = {e['to_franchise_id'] for e in rows if e.get('to_franchise_id')}
            if event['event_type'] == 'pick_exercise' and current == original:
                selection = selections.get(str(event['source_record_id']))
                if not selection or not selection.get('player_id') or receivers != {owner} or senders:
                    return None, 'The exact pick conversion and recipient ownership are not established.'
                current = 'DTOS-P-' + str(selection['player_id'])
                converted_selection = str(event['source_record_id'])
                conversion_low, boundary = low, high
                continue
            if event['event_type'] not in {'trade', 'pick_transfer'} or not str(event.get('parent_id') or '').startswith('TRADE-'):
                return None, 'A release, acquisition or other intervening movement ends this original receipt’s continuation.'
            if senders != {owner} or len(receivers) != 1 or owner in receivers:
                return None, 'A missing or conflicting ownership transition prevents attributing this return to the original recipient.'
            record = graph.store.transaction_record(graph.league_id, event['source_record_id'])
            reference = graph.trade_reference(event['parent_id'])
            if (not record or str(graph._source_league(record)) != str(event['source_league_id'])
                    or record['season'] != event['season'] or not reference
                    or record['payload'].get('history_transaction_conflict')):
                return None, 'Conflicting or unresolved transaction identity prevents a supported package.'
            raw = record['payload']
            parties, moves, complete, categories = _movement_evidence(raw)
            valid = [m for m in moves if identity(m) == current and m[2] == receipts[0][3]]
            if (str(raw.get('status', '')).casefold() not in COMPLETED or raw.get('type') != 'trade'
                    or len(valid) != 1 or not parties):
                return None, 'The completed transaction does not establish the exact outgoing asset.'
            if len(moves) > max_assets or len(parties) > max_assets:
                return None, 'The package presentation limit was reached; open the later trade for its source evidence.'
            pid = event['parent_id']
            if pid not in packages:
                movements = []
                for kind, asset, sender, receiver, amount in moves:
                    asset_id = 'DTOS-P-' + asset if kind == 'player' else asset
                    movements.append({'kind': kind, 'asset_id': asset_id,
                        'label': f'{amount:g} FAAB' if kind == 'faab' else label(asset_id),
                        'sender': franchise(f'{graph.league_id}:franchise:{sender}', event['season']),
                        'receiver': franchise(f'{graph.league_id}:franchise:{receiver}', event['season'])})
                packages[pid] = {'trade_id': pid, 'transaction_id': event['source_record_id'],
                    'source_league_id': event['source_league_id'], 'occurred_at': low.isoformat().replace('+00:00', 'Z'),
                    'season': event['season'], 'url': reference['url'], 'complete': complete,
                    'supported_categories': categories, 'movements': movements,
                    'participants': [franchise(f'{graph.league_id}:franchise:{p}', event['season']) for p in parties],
                    'followed_branches': [], 'limitations': [] if complete else [
                        'Some consideration is missing or invalid. Supported movements are shown; the full package return is unknown.']}
            packages[pid]['followed_branches'].append({'asset_id': original, 'label': branch['label'],
                'outgoing_asset_id': current, 'outgoing_label': label(current), 'recipient_id': owner,
                'converted': current != original})
            return pid, None
        return None, 'The bounded conversion could not establish a subsequent exchange.'

    for branch in branches[:max_assets]:
        pid, reason = resolve(branch)
        branch['next_exchange'] = {'trade_id': pid, 'reason': reason,
            'state': 'observed' if pid else 'unknown'}
    return list(packages.values())
