"""Explicitly admitted reachability collection for projection source provenance.

No startup adoption. A reviewed dry-run digest is required before activation.
Retained observations carry their original validity end, so collection cannot
bridge an unavailable historical interval with older evidence.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

VERSION = "projection-provenance-reachability-v1"
SCHEMA = """
CREATE TABLE IF NOT EXISTS projection_source_expiry(
 observation_id INTEGER PRIMARY KEY, valid_until TEXT
);
"""


def stamp(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Projection provenance needs timezone-aware boundaries")
    return parsed.astimezone(timezone.utc).isoformat()


def enabled(db):
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='projection_retention_policy'").fetchone()
    return bool(exists and db.execute(
        "SELECT 1 FROM projection_retention_policy WHERE version=?", (VERSION,)
    ).fetchone())


def plan(db, retained_snapshots):
    """Read-only complete plan. Unknown/missing references fail closed."""
    from .retention import PROVENANCE, unpack

    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expiry = dict(db.execute("SELECT observation_id,valid_until FROM projection_source_expiry")) if 'projection_source_expiry' in tables else {}
    rows = list(db.execute("SELECT observation_id,season,week,observed_at,fingerprint,payload FROM projection_source_history ORDER BY observation_id"))
    by_scope = {}
    for row in rows:
        boundary = stamp(row[3])
        scope = (row[1], row[2])
        group = by_scope.setdefault(scope, [])
        if group and boundary < stamp(group[-1][3]):
            raise ValueError("Projection source time order is invalid")
        group.append(row)
    ends = {}
    for group in by_scope.values():
        for index, row in enumerate(group):
            candidates = [v for v in (
                expiry.get(row[0]),
                stamp(group[index + 1][3]) if index + 1 < len(group) else None,
            ) if v is not None]
            end = min(map(stamp, candidates)) if candidates else None
            if end is not None and end < stamp(row[3]):
                raise ValueError("Projection source validity interval is invalid")
            ends[row[0]] = end

    keep = set()
    # One current and one rollback source per provider-cache scope. No arbitrary
    # refresh history window; cache seasons are bounded by the publisher.
    for scope in db.execute("SELECT DISTINCT season,week FROM sleeper_projection_snapshots"):
        keep.update(row[0] for row in by_scope.get(tuple(scope), [])[-2:])
    for sid in retained_snapshots:
        row = db.execute("SELECT payload FROM projection_snapshots WHERE snapshot_id=?", (sid,)).fetchone()
        if row is None:
            raise ValueError("Missing projection snapshot root")
        envelope, _ = unpack(row[0])
        fingerprint = envelope.get('sleeper_evidence_snapshot_id')
        if not fingerprint:
            # Internal/unsupported projections need no invented external source.
            continue
        boundary = stamp(envelope['generated_at'])
        matching = [r for r in by_scope.get((envelope['season'], envelope['week']), [])
                    if r[4] == fingerprint and stamp(r[3]) <= boundary
                    and (ends[r[0]] is None or boundary < ends[r[0]])]
        if not matching:
            raise ValueError("Retained projection has no valid source provenance")
        keep.add(matching[-1][0])
    if 'projection_source_roots' in tables:
        keep.update(r[0] for r in db.execute("SELECT observation_id FROM projection_source_roots"))
    lookup = {r[0]: r for r in rows}
    if keep - lookup.keys():
        raise ValueError("Missing projection source root")
    for oid in keep:
        if json.loads(lookup[oid][5]).get('$storage') == PROVENANCE:
            # Do not upgrade an expired receipt into full historical evidence.
            raise ValueError("Required source evidence was already expired")
    fingerprint = hashlib.sha256()
    for row in rows:
        fingerprint.update(json.dumps(list(row), separators=(',', ':')).encode())
    fingerprint.update(json.dumps([sorted(retained_snapshots), sorted(keep), sorted(ends.items())], separators=(',', ':')).encode())
    return {
        'policy': VERSION, 'digest': fingerprint.hexdigest(),
        'retained': sorted(keep), 'reclaimable': sorted(lookup.keys() - keep),
        'reclaimable_payload_bytes': sum(len(lookup[k][5].encode()) for k in lookup.keys() - keep),
        'valid_until': {k: ends[k] for k in sorted(keep)},
    }


def admit(db, *, expected_digest):
    """Caller owns transaction and explicit cleanup authorization; never startup."""
    from . import retention
    if not retention.enabled(db):
        raise ValueError("Projection generation retention must be admitted first")
    snapshots, _ = retention.plan(db)
    candidate = plan(db, snapshots)
    if candidate['digest'] != expected_digest:
        raise ValueError("Projection retention dry-run is stale")
    # execute, not executescript: never commit the caller's transaction.
    db.execute("CREATE TABLE IF NOT EXISTS projection_source_expiry(observation_id INTEGER PRIMARY KEY, valid_until TEXT)")
    db.execute("INSERT OR IGNORE INTO projection_retention_policy VALUES (?)", (VERSION,))
    return candidate


def collect(db, candidate):
    """Apply only inside the publisher's atomic transaction, after admission."""
    if not enabled(db):
        raise ValueError("Projection provenance collection is not admitted")
    for oid, boundary in candidate['valid_until'].items():
        db.execute("INSERT INTO projection_source_expiry VALUES (?,?) ON CONFLICT(observation_id) DO UPDATE SET valid_until=excluded.valid_until WHERE valid_until IS NOT excluded.valid_until", (oid, boundary))
    db.executemany("DELETE FROM projection_source_history WHERE observation_id=?", ((k,) for k in candidate['reclaimable']))
    db.execute("DELETE FROM projection_source_expiry WHERE observation_id NOT IN (SELECT observation_id FROM projection_source_history)")


def visible(db, observation_id, boundary):
    if not enabled(db):
        return True
    row = db.execute("SELECT valid_until FROM projection_source_expiry WHERE observation_id=?", (observation_id,)).fetchone()
    # A just-appended row in the same transaction may not yet have a boundary.
    return row is None or row[0] is None or stamp(boundary) < stamp(row[0])
