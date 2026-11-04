"""Explicit, reversible classification. Never called automatically at startup.

Payloads and player states stay in place. Operator manifests are private and
must identify exact payload hashes; names, dates, and broad predicates are not
authority to classify evidence.
"""
import hashlib
import json

CLASSIFICATION = 'UNSUPPORTED_LEGACY_PROVENANCE'
TABLE = 'projection_snapshot_quarantine'


def identities(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone():
        return set()
    return {row[0] for row in db.execute(f'SELECT snapshot_id FROM {TABLE}')}


def validate_publication(db, snapshot_id):
    """A new supported publication cannot inherit an unproved legacy source."""
    from . import retention, provenance_retention, state_storage
    if snapshot_id in identities(db):
        raise ValueError('Quarantined projection identity cannot be republished')
    payload = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (snapshot_id,)).fetchone()[0]
    envelope, _ = retention.unpack(payload)
    if envelope.get('sleeper_evidence_snapshot_id'):
        boundary = provenance_retention.stamp(envelope['generated_at'])
        rows = db.execute('SELECT observation_id,observed_at,fingerprint FROM projection_source_history '
                          'WHERE season=? AND week=? ORDER BY observation_id',
                          (envelope['season'], envelope['week'])).fetchall()
        eligible = [row for row in rows if provenance_retention.stamp(row[1]) <= boundary]
        if not eligible or eligible[-1][2] != envelope['sleeper_evidence_snapshot_id']:
            raise ValueError('Retained projection has no valid source provenance')
        oid = eligible[-1][0]
        source = db.execute('SELECT payload FROM projection_source_history WHERE observation_id=?', (oid,)).fetchone()[0]
        if (json.loads(source).get('$storage') == retention.PROVENANCE
                or not provenance_retention.visible(db, oid, boundary)):
            raise ValueError('Required source evidence was already expired')
    else:
        value = state_storage.decode(db, payload)
        if any(player.get('canonical_projection') is not None for player in value.get('players', {}).values()):
            raise ValueError('Supported projection publication requires source provenance')


def plan(db, manifest):
    """Read-only exact-set validation; no broad matching or automatic repair."""
    from . import retention, provenance_retention, state_storage
    if not manifest or len({row['snapshot_id'] for row in manifest}) != len(manifest):
        raise ValueError('Quarantine requires a nonempty exact unique manifest')
    targets = {row['snapshot_id'] for row in manifest}
    if identities(db) - targets:
        raise ValueError('Quarantine set differs from the reviewed manifest')
    retained, _ = retention.plan(db)
    for sid in retained - targets:
        # Newly discovered unsupported roots are not silently swept into scope.
        validate_publication(db, sid)
    for table in ('projection_publication_heads', 'projection_previous_heads',
                  'projection_checkpoint_roots', 'projection_actuals'):
        if db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
            if targets & {row[0] for row in db.execute(f'SELECT snapshot_id FROM {table}')}:
                raise ValueError('Quarantine target has a protected publication/event reference')
    for sid, payload in db.execute('SELECT snapshot_id,payload FROM projection_snapshots'):
        envelope, _ = retention.unpack(payload)
        if sid not in targets and targets & set((envelope.get('horizon_snapshot_ids') or {}).values()):
            raise ValueError('Quarantine target has a retained horizon reference')
    verified = []
    for item in sorted(manifest, key=lambda value: value['snapshot_id']):
        sid = item['snapshot_id']
        row = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (sid,)).fetchone()
        if row is None or hashlib.sha256(row[0].encode()).hexdigest() != item['payload_sha256']:
            raise ValueError('Quarantine exact payload identity changed')
        envelope, _ = retention.unpack(row[0])
        for key in ('league_id', 'season', 'week', 'scoring_profile_id', 'sleeper_evidence_snapshot_id'):
            if envelope.get(key) != item.get(key):
                raise ValueError('Quarantine scope/source identity changed')
        # Audit decoding verifies every content-addressed player reference.
        state_storage.decode(db, row[0], audit=True)
        try:
            # Prove THIS snapshot lacks its own required source closure. An
            # unrelated expired cache/event source cannot make a valid target
            # eligible for quarantine.
            provenance_retention.plan(db, {sid}, snapshot_only=True)
        except ValueError as exc:
            if str(exc) not in ('Retained projection has no valid source provenance',
                                'Required source evidence was already expired'):
                raise
        else:
            raise ValueError('Valid source provenance cannot be quarantined by this procedure')
        verified.append(dict(item))
    digest = hashlib.sha256(json.dumps(verified, sort_keys=True).encode()).hexdigest()
    return {'digest': digest, 'records': verified}


def apply(db, manifest, *, expected_digest):
    """Caller must own a transaction and separately authorize reclassification."""
    if not db.in_transaction:
        raise ValueError('Quarantine requires an explicit transaction')
    candidate = plan(db, manifest)
    if candidate['digest'] != expected_digest:
        raise ValueError('Quarantine manifest is stale')
    db.execute(f'CREATE TABLE IF NOT EXISTS {TABLE}(snapshot_id TEXT PRIMARY KEY, classification TEXT NOT NULL, manifest_digest TEXT NOT NULL, payload_sha256 TEXT NOT NULL, metadata TEXT NOT NULL)')
    for item in candidate['records']:
        record = (item['snapshot_id'], CLASSIFICATION, expected_digest, item['payload_sha256'], json.dumps(item, sort_keys=True))
        prior = db.execute(f'SELECT * FROM {TABLE} WHERE snapshot_id=?', (item['snapshot_id'],)).fetchone()
        if prior is not None and tuple(prior) != record:
            raise ValueError('Existing quarantine classification differs')
        db.execute(f'INSERT OR IGNORE INTO {TABLE} VALUES (?,?,?,?,?)', record)
    return candidate


def rollback(db, manifest, *, expected_digest):
    """Remove only this exact classification, never an original evidence row."""
    if not db.in_transaction:
        raise ValueError('Quarantine rollback requires an explicit transaction')
    candidate = plan(db, manifest)
    if candidate['digest'] != expected_digest:
        raise ValueError('Quarantine rollback identity changed')
    for item in candidate['records']:
        row = db.execute(f'SELECT manifest_digest FROM {TABLE} WHERE snapshot_id=?', (item['snapshot_id'],)).fetchone()
        if row is None or row[0] != expected_digest:
            raise ValueError('Quarantine rollback classification differs')
    db.executemany(f'DELETE FROM {TABLE} WHERE snapshot_id=?', ((item['snapshot_id'],) for item in candidate['records']))
