"""Qualify contradictory completed records before canonical key collapse."""
from hashlib import sha256
import json

from .timestamps import canonical_transaction_timestamp


def conflicting_transactions(transactions):
    # Per publication, not across older caches and their authoritative refresh.
    # Repeated endpoint buckets are observations, not ordered corrections.
    from src.core.gm_behavioral_intelligence.diagnostics import _movement_evidence
    versions, conflicts = {}, set()
    for raw in transactions:
        identity = str(raw.get('transaction_id') or '')
        if not identity or str(raw.get('status', '')).casefold() not in {'complete', 'completed'}:
            continue
        parties, moves, complete, categories = _movement_evidence(raw)
        stamp = canonical_transaction_timestamp(raw)[0]
        semantic = (raw.get('type'), stamp, parties, sorted(moves), complete, categories)
        if not complete:
            # Unsupported legs must not disappear from the conflict test.
            semantic += ({k: raw.get(k) for k in ('adds', 'drops', 'draft_picks', 'waiver_budget', 'roster_ids')},)
        digest = sha256(json.dumps(semantic, sort_keys=True, default=str).encode()).digest()
        if identity in versions and versions[identity] != digest:
            conflicts.add(identity)
        versions[identity] = digest
    return conflicts


def qualify_transaction_rows(rows):
    conflicts = conflicting_transactions(r['payload'] for r in rows if r['entity_type'] in {'trade', 'transaction'})
    for row in rows:
        if row['entity_type'] in {'trade', 'transaction'} and str(row['source_record_id']) in conflicts:
            row['payload'] = {**row['payload'], 'history_transaction_conflict': True}
    return rows
