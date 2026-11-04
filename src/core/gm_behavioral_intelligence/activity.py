"""Bounded observed transaction activity, separated from manager intentions."""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite

from src.core.history_context.timestamps import canonical_utc_timestamp


def _rid(value):
    return str(int(value)) if not isinstance(value, bool) and str(value).isdigit() and int(value) > 0 else None


def _counts():
    return {'completed_trades': 0, 'completed_waivers': 0, 'completed_adds': 0,
        'completed_drops': 0, 'completed_transactions': 0,
        'waiver_attempts': dict.fromkeys(('failed', 'pending', 'cancelled', 'unknown'), 0),
        'other_attempts': dict.fromkeys(('failed', 'pending', 'cancelled', 'unknown'), 0),
        'faab_spent': None, 'faab_sent': None, 'faab_received': None, 'faab_supported_transfers': 0, 'faab_priced_claims': 0, 'faab_unavailable_claims': 0,
        'undated_events': 0, 'incomplete_consideration': 0, 'references': []}


def summarize_activity(rows, teams, owner_for=None, *, on_completed=None):
    """Deduplicate before counting; no fetching, persistence, grades or prices.

    Keys include the actual source league, not only its roster number. Conflicting
    versions are withheld rather than choosing by iteration or retrieval time.
    Explicit completion status establishes a decision, not a dated sequence.
    """
    current = {str(t.get('roster_id')): t for t in teams if isinstance(t, dict)}
    result = {'teams': {rid: {'franchise': _counts(), 'manager': _counts()} for rid in current},
        'total': _counts(), 'conflicting_identities': 0, 'unqualified_records': 0,
        'attribution': 'Franchise observations across acquired periods; manager attribution requires historical owner evidence. Current ownership does not backdate decisions.'}
    unique, conflicts = {}, set()
    fields = ('transaction_id', 'type', 'status', 'roster_ids', 'adds', 'drops',
              'draft_picks', 'waiver_budget', 'created', 'status_updated', 'settings')
    for season, league, original in rows:
        if not isinstance(original, dict) or not league or str(original.get('league_id') or league) != str(league):
            result['unqualified_records'] += 1
            continue
        tid = original.get('transaction_id')
        if isinstance(tid, bool) or not isinstance(tid, (str, int)) or not str(tid) or len(str(tid)) > 100:
            result['unqualified_records'] += 1
            continue
        row = {key: original[key] for key in fields if key in original}
        row['transaction_id'] = str(tid)
        raw_ids = row.get('roster_ids')
        ids = [_rid(x) for x in raw_ids] if isinstance(raw_ids, list) else []
        if not ids or None in ids or len(ids) != len(set(ids)):
            result['unqualified_records'] += 1
            continue
        row['roster_ids'] = sorted(ids, key=int)
        row['type'] = str(row.get('type') or '').casefold()
        status = str(row.get('status') or '').casefold()
        row['status'] = {'completed': 'complete', 'canceled': 'cancelled'}.get(status, status)
        if isinstance(row.get('settings'), dict):
            row['settings'] = {'waiver_bid': row['settings'].get('waiver_bid')}
        key = (str(league), str(tid))
        value = (season, row)
        if key in unique and unique[key] != value:
            conflicts.add(key)
        unique[key] = value
    result['conflicting_identities'] = len(conflicts)
    now = datetime.now(timezone.utc)
    for (league, tid), (season, row) in sorted(unique.items()):
        if (league, tid) in conflicts:
            continue
        kind, status = row['type'], row['status']
        stamp = canonical_utc_timestamp(row.get('status_updated'))
        created = canonical_utc_timestamp(row.get('created'))
        dated = bool(stamp and datetime.fromisoformat(stamp) <= now and
                     (not created or datetime.fromisoformat(stamp) >= datetime.fromisoformat(created)))
        future = any(x and datetime.fromisoformat(x) > now for x in (stamp, created))
        completed = status == 'complete' and not future and kind in {'waiver', 'free_agent', 'drop', 'trade'}
        state = status if status in {'failed', 'pending', 'cancelled'} else 'unknown'
        if completed and on_completed is not None:
            on_completed(league, tid)
        reference = {'transaction_id': tid, 'source_league_id': league, 'season': season,
                     'completion_at': stamp if dated else None}
        ids = row['roster_ids']
        sides = [(result['total'], None)]
        for rid in ids:
            if rid not in current:
                continue
            sides.append((result['teams'][rid]['franchise'], rid))
            observed_owner = owner_for(season, rid) if owner_for is not None else None
            if observed_owner and str(current[rid].get('owner_id') or '') == str(observed_owner):
                sides.append((result['teams'][rid]['manager'], rid))
        for counts, rid in sides:
            if len(counts['references']) < 12:
                counts['references'].append(reference)
            counts['undated_events'] += int(not dated)
            if not completed:
                counts['waiver_attempts' if kind == 'waiver' else 'other_attempts'][state] += 1
                continue
            counts['completed_transactions'] += 1
            counts['completed_waivers'] += int(kind == 'waiver')
            counts['completed_trades'] += int(kind == 'trade')
            for field, target in (('adds', 'completed_adds'), ('drops', 'completed_drops')):
                moves = row.get(field)
                if moves is None:
                    moves = {}
                if not isinstance(moves, dict):
                    counts['incomplete_consideration'] += 1
                    continue
                for player_id, owner in moves.items():
                    destination = _rid(owner)
                    if not isinstance(player_id, str) or not player_id or destination not in ids:
                        counts['incomplete_consideration'] += 1
                    elif rid is None or destination == rid:
                        counts[target] += 1
            if kind == 'trade':
                transfers = row.get('waiver_budget') or []
                if not isinstance(transfers, list):
                    counts['incomplete_consideration'] += 1
                    transfers = []
                seen = set()
                for transfer in transfers:
                    if not isinstance(transfer, dict):
                        counts['incomplete_consideration'] += 1
                        continue
                    sender, receiver = _rid(transfer.get('sender')), _rid(transfer.get('receiver'))
                    amount = transfer.get('amount')
                    if (sender not in ids or receiver not in ids or sender == receiver
                            or not isinstance(amount, (int, float)) or isinstance(amount, bool)
                            or not isfinite(amount) or amount < 0):
                        counts['incomplete_consideration'] += 1
                        continue
                    identity = (sender, receiver, amount)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    if rid is None or rid == sender:
                        counts['faab_sent'] = (counts['faab_sent'] or 0) + amount
                    if rid is None or rid == receiver:
                        counts['faab_received'] = (counts['faab_received'] or 0) + amount
                    counts['faab_supported_transfers'] += int(rid is None or rid in (sender, receiver))
            if kind == 'waiver':
                bid = (row.get('settings') or {}).get('waiver_bid') if isinstance(row.get('settings'), dict) else None
                if len(ids) == 1 and isinstance(bid, (int, float)) and not isinstance(bid, bool) and isfinite(bid) and bid >= 0:
                    counts['faab_priced_claims'] += 1
                    counts['faab_spent'] = (counts['faab_spent'] or 0) + bid
                else:
                    counts['faab_unavailable_claims'] += 1
    return result


def activity_text(counts):
    attempts = counts.get('waiver_attempts') or {}
    return (f"{counts.get('completed_waivers', 0)} completed waiver claims · "
        f"{attempts.get('failed', 0)} failed · {attempts.get('pending', 0)} pending · "
        f"{attempts.get('cancelled', 0)} cancelled · {attempts.get('unknown', 0)} unknown-status waiver attempts. "
        f"{counts.get('completed_adds', 0)} completed player additions · {counts.get('completed_drops', 0)} completed drops. "
        'These are observed franchise decisions, not current-manager preferences; missing periods are not zero activity.')
