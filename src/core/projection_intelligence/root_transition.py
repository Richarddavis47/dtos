"""Explicit operational rebase; never invoked by startup or ordinary reads.

Candidates must already be prepared in the store. Caller must hold the existing
maintenance/writer-quiescence guard through acceptance or reversal. Exact old
roots are checkpoint-pinned while pending, including across restart. No source
repair, quarantine, collection, or policy activation occurs here.
"""
from __future__ import annotations

from . import provenance_retention, quarantine, retention, state_storage

SCOPE = ('league_id', 'season', 'week', 'scoring_profile_id', 'model_version',
         'contract_version', 'semantic_policy_version')


def stage(db, source, *, league, active, previous):
    """Import exact prepared closures only; caller owns destination transaction.

    Source connection must be read-only and hold a stable read transaction.
    Source observation IDs are local surrogate keys, never copied over unrelated
    destination IDs. Original payloads, fingerprints and time boundaries remain.
    No operational root or retention policy is changed; no collection runs.
    """
    if not db.in_transaction or not source.in_transaction or not source.execute('PRAGMA query_only').fetchone()[0]:
        raise ValueError('Staging needs destination transaction and stable read-only source')
    published = roots(source, league)
    if not published['active'] or published['active'][0] != active or published['previous'] != previous:
        raise ValueError('Prepared pair is not the accepted active/previous publication pair')
    proof = validate_pair(source, league, active, previous)
    snapshots = [source.execute('SELECT * FROM projection_snapshots WHERE snapshot_id=?', (sid,)).fetchone() for sid in sorted(proof['snapshots'])]
    observations = [source.execute('SELECT * FROM projection_source_history WHERE observation_id=?', (oid,)).fetchone() for oid in proof['sources']]
    ids = set()
    for row in snapshots + observations:
        _, references = retention.unpack(row[-1])
        ids.update(ref[0] for ref in references.values())
    for sid in sorted(ids):
        row = source.execute('SELECT payload FROM projection_player_states WHERE state_id=?', (sid,)).fetchone()
        if not row:
            raise ValueError('Prepared source state missing')
        prior = db.execute('SELECT payload FROM projection_player_states WHERE state_id=?', (sid,)).fetchone()
        if prior and prior[0] != row[0]:
            raise ValueError('Prepared source-state identity collision')
        db.execute('INSERT OR IGNORE INTO projection_player_states VALUES (?,?)', (sid, row[0]))
    for row in observations:
        _, season, week, observed, fingerprint, payload = tuple(row)
        existing = db.execute('SELECT observation_id,payload FROM projection_source_history WHERE season=? AND week=? AND observed_at=? AND fingerprint=?', (season, week, observed, fingerprint)).fetchone()
        if existing:
            if existing[1] != payload:
                raise ValueError('Prepared observation identity collision')
            continue
        latest = db.execute('SELECT observed_at FROM projection_source_history WHERE season=? AND week=? ORDER BY observation_id DESC LIMIT 1', (season, week)).fetchone()
        if latest and provenance_retention.stamp(latest[0]) >= provenance_retention.stamp(observed):
            raise ValueError('Prepared source boundary is stale; do not reorder history')
        db.execute('INSERT INTO projection_source_history(season,week,observed_at,fingerprint,payload) VALUES (?,?,?,?,?)', (season, week, observed, fingerprint, payload))
    for row in snapshots:
        prior = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (row[0],)).fetchone()
        if prior and prior[0] != row[-1]:
            raise ValueError('Prepared snapshot identity collision')
        db.execute('INSERT OR IGNORE INTO projection_snapshots VALUES (?,?,?,?,?,?)', tuple(row))
    validate_pair(db, league, active, previous)
    return proof


def roots(db, league):
    active = db.execute('SELECT snapshot_id,published_at FROM projection_publication_heads WHERE league_id=?', (league,)).fetchone()
    previous = db.execute('SELECT snapshot_id FROM projection_previous_heads WHERE league_id=?', (league,)).fetchone()
    return {'active': list(active) if active else None, 'previous': previous[0] if previous else None}


def validate_pair(db, league, active, previous):
    from .service import snapshot_compatibility
    if active == previous:
        raise ValueError('Rollback requires a distinct accepted publication')
    visited = set()

    def visit(sid, parent=None, week=None):
        record = db.execute('SELECT league_id,season,week,payload FROM projection_snapshots WHERE snapshot_id=?', (sid,)).fetchone()
        if not record:
            raise ValueError('Missing operational candidate')
        row = state_storage.decode(db, record[3])
        if (str(record[0]) != league or row.get('league_id') != league or
                row.get('projection_snapshot_id') != sid or record[1:3] != (row.get('season'), row.get('week'))):
            raise ValueError('Operational candidate scope mismatch')
        if snapshot_compatibility(row)[0] != 'compatible' or not row.get('sleeper_evidence_snapshot_id'):
            raise ValueError('Operational candidate requires supported source evidence')
        if parent is not None and (row['week'] != int(week) or any(row.get(k) != parent.get(k) for k in SCOPE if k != 'week')):
            raise ValueError('Operational horizon scope mismatch')
        quarantine.validate_publication(db, sid)
        if sid not in visited:
            visited.add(sid)
            manifest = row.get('horizon_snapshot_ids') or {}
            if manifest and set(map(int, manifest)) != set(row.get('weeks_requested') or []):
                raise ValueError('Operational horizon coverage mismatch')
            for w, child in manifest.items():
                visit(child, row, w)
        return row

    new, prior = visit(active), visit(previous)
    if any(new.get(k) != prior.get(k) for k in SCOPE):
        raise ValueError('Operational predecessor scope mismatch')
    if new.get('weeks_requested') != prior.get('weeks_requested'):
        raise ValueError('Operational predecessor horizon mismatch')
    if provenance_retention.stamp(prior['generated_at']) >= provenance_retention.stamp(new['generated_at']):
        raise ValueError('Operational predecessor must precede active publication')
    proof = provenance_retention.plan(db, visited)
    for oid in proof['retained']:
        payload = db.execute('SELECT payload FROM projection_source_history WHERE observation_id=?', (oid,)).fetchone()[0]
        # Validate all content-addressed source states, not only the receipt.
        state_storage.decode(db, payload)
    return {'active': new, 'previous': prior, 'snapshots': visited, 'sources': proof['retained']}


def switch(db, *, league, active, previous, expected_old, transition_id, check_read=None):
    """One SQLite commit updates both roots; failure leaves old roots unchanged."""
    if db.in_transaction:
        raise ValueError('Root switch owns its transaction')
    db.execute('BEGIN IMMEDIATE')
    try:
        if roots(db, league) != expected_old:
            raise ValueError('Operational roots changed since review')
        proof = validate_pair(db, league, active, previous)
        prefix = 'operational-transition:' + transition_id + ':'
        if db.execute('SELECT 1 FROM projection_checkpoint_roots WHERE event_id IN (?,?)', (prefix+'active', prefix+'previous')).fetchone():
            raise ValueError('Transition identity already pending')
        for name, sid in (('active', (expected_old['active'] or [None])[0]), ('previous', expected_old['previous'])):
            if sid:
                db.execute('INSERT INTO projection_checkpoint_roots VALUES (?,?)', (prefix+name, sid))
        db.execute('INSERT INTO projection_publication_heads VALUES (?,?,?) ON CONFLICT(league_id) DO UPDATE SET snapshot_id=excluded.snapshot_id,published_at=excluded.published_at', (league, active, proof['active']['generated_at']))
        db.execute('INSERT INTO projection_previous_heads VALUES (?,?) ON CONFLICT(league_id) DO UPDATE SET snapshot_id=excluded.snapshot_id', (league, previous))
        if check_read:
            check_read(db, proof)
        manifest = {'league': league, 'old': expected_old, 'new': roots(db, league), 'prefix': prefix}
        db.commit()
        return manifest
    except BaseException:
        db.rollback()
        raise


def finish(db, manifest, *, accept, reviewed_reclassification=None):
    """Accept or reverse exact pending roots; never runs collection.

    After successful post-switch reads, an explicit exact-manifest classifier
    may run within acceptance, after old operational pins are removed. This is
    not automatic discovery: caller supplies the already reviewed classification
    procedure. Failure restores pins and all classifications transactionally.
    """
    if db.in_transaction:
        raise ValueError('Transition completion owns its transaction')
    if reviewed_reclassification is not None and not accept:
        raise ValueError('Reversal cannot reclassify old evidence')
    db.execute('BEGIN IMMEDIATE')
    try:
        league, prefix = manifest['league'], manifest['prefix']
        if roots(db, league) != manifest['new']:
            raise ValueError('Cannot complete a superseded operational transition')
        expected_pins = {(prefix+name, sid) for name, sid in
                         (('active', (manifest['old']['active'] or [None])[0]), ('previous', manifest['old']['previous'])) if sid}
        actual = {tuple(row) for row in db.execute('SELECT event_id,snapshot_id FROM projection_checkpoint_roots WHERE event_id IN (?,?)', (prefix+'active', prefix+'previous'))}
        if actual != expected_pins:
            raise ValueError('Pending transition protection changed')
        validate_pair(db, league, manifest['new']['active'][0], manifest['new']['previous'])
        if not accept:
            old = manifest['old']
            if old['active']:
                db.execute('UPDATE projection_publication_heads SET snapshot_id=?,published_at=? WHERE league_id=?', (*old['active'], league))
            else:
                db.execute('DELETE FROM projection_publication_heads WHERE league_id=?', (league,))
            if old['previous']:
                db.execute('UPDATE projection_previous_heads SET snapshot_id=? WHERE league_id=?', (old['previous'], league))
            else:
                db.execute('DELETE FROM projection_previous_heads WHERE league_id=?', (league,))
        db.execute('DELETE FROM projection_checkpoint_roots WHERE event_id IN (?,?)', (prefix+'active', prefix+'previous'))
        if accept:
            if reviewed_reclassification:
                reviewed_reclassification(db)
            retained, _ = retention.plan(db)
            provenance_retention.plan(db, retained)
        db.commit()
    except BaseException:
        db.rollback()
        raise
