"""Admitted FOIS operational retention; historical assessment roots are sacred.

Existing history is protected at admission, never retroactively called churn.
New operational observations retain eight rows per score identity. Canonical
assessment roots and their delta ancestors are never evicted by a byte budget.
"""
from __future__ import annotations

import hashlib
import json
import zlib
from . import state_storage

VERSION = 'fois-retention-v1'
OPERATIONAL_LIMIT = 8
MATERIAL_SCORE_DELTA = 5.0
SCHEMA = (
    'CREATE TABLE IF NOT EXISTS fois_retention_policy(version TEXT PRIMARY KEY,legacy_max_rowid INTEGER NOT NULL)',
    'CREATE TABLE IF NOT EXISTS fois_assessment_roots(snapshot_id TEXT PRIMARY KEY,reason TEXT NOT NULL)',
)


def enabled(db):
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='fois_retention_policy'").fetchone()
    return bool(exists and db.execute('SELECT 1 FROM fois_retention_policy WHERE version=?', (VERSION,)).fetchone())


def inventory_digest(db):
    digest = hashlib.sha256()
    for table in ('fois_scores_v2', 'fois_snapshot_history', 'fois_semantic_states'):
        digest.update(table.encode())
        for row in db.execute(f'SELECT * FROM {table} ORDER BY 1'):
            for value in row:
                body = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
                digest.update(len(body).to_bytes(8, 'big'))
                digest.update(body)
    return digest.hexdigest()


def admit(db, *, expected_digest):
    if inventory_digest(db) != expected_digest:
        raise ValueError('FOIS retention dry-run is stale')
    for statement in SCHEMA:
        db.execute(statement)
    cutoff = db.execute('SELECT coalesce(max(rowid),0) FROM fois_snapshot_history').fetchone()[0]
    # Re-admission must not promote later operational churn to canonical history.
    db.execute('INSERT OR IGNORE INTO fois_retention_policy VALUES (?,?)', (VERSION, cutoff))


def _material(before, after):
    for field in ('model_version', 'configuration_version', 'evidence_version',
                  'category_definition_version', 'evaluation_start_season', 'evaluation_end_season',
                  'tenure_id', 'gm_id', 'owner_id', 'tenure_started_at',
                  'overall_letter_grade', 'evidence_state', 'provisional'):
        if before.get(field) != after.get(field):
            return True
    def number_changed(a, b):
        return (a is None) != (b is None) or (a is not None and b is not None
                                             and abs(float(a) - float(b)) >= MATERIAL_SCORE_DELTA)
    if number_changed(before.get('overall_score'), after.get('overall_score')):
        return True
    old = {c['category_key']: c for c in before.get('category_scores', [])}
    new = {c['category_key']: c for c in after.get('category_scores', [])}
    if old.keys() != new.keys():
        return True
    for key, row in new.items():
        prior = old[key]
        if prior.get('letter_grade') != row.get('letter_grade') or number_changed(prior.get('normalized_score'), row.get('normalized_score')):
            return True
        # Preserve independent process/outcome availability and assessments;
        # unknown detail fields are not silently discarded as non-semantic.
        if _details_material(prior.get('details'), row.get('details')):
            return True
    return False


def _details_material(before, after):
    """Only the known scoped-summary schema permits operational exclusions.

    Elapsed observation horizon is not a new decision. Magnitude drift uses the
    same material boundary as category quality, compared to the last retained
    assessment (so cumulative movement is not lost). Coverage, distributions,
    limitations, activity and unknown schemas remain conservatively material.
    """
    if before == after:
        return False
    if not isinstance(before, dict) or not isinstance(after, dict):
        return True
    if before.get('method') != 'fois-scoped-quality-1' or after.get('method') != 'fois-scoped-quality-1':
        return True
    left, right = dict(before), dict(after)
    for side in ('process', 'outcome'):
        a, b = dict(left.pop(side, {}) or {}), dict(right.pop(side, {}) or {})
        a.pop('observation_horizon_days', None)
        b.pop('observation_horizon_days', None)
        for field in ('mean_magnitude', 'minimum_magnitude', 'maximum_magnitude'):
            old, new = a.pop(field, None), b.pop(field, None)
            if (old is None) != (new is None):
                return True
            if old is not None and abs(float(old) - float(new)) >= MATERIAL_SCORE_DELTA:
                return True
        if a != b:
            return True
    return left != right


def record(db, snapshot_id):
    """Classify a newly published assessment, without modifying its quality."""
    if not enabled(db):
        return
    row = db.execute('SELECT score_key,payload FROM fois_snapshot_history WHERE snapshot_id=?', (snapshot_id,)).fetchone()
    if row is None:
        raise ValueError('Missing FOIS assessment observation')
    prior = db.execute('''SELECT h.payload FROM fois_snapshot_history h
        JOIN fois_assessment_roots r ON r.snapshot_id=h.snapshot_id
        WHERE h.score_key=? ORDER BY h.rowid DESC LIMIT 1''', (row[0],)).fetchone()
    state = state_storage.decode(db, row[1])
    if prior is None or _material(state_storage.decode(db, prior[0]), state):
        reason = 'INITIAL_ASSESSMENT' if prior is None else 'MATERIAL_ASSESSMENT_CHANGED'
        db.execute('INSERT OR IGNORE INTO fois_assessment_roots VALUES (?,?)', (snapshot_id, reason))


def plan(db):
    """Read-only mark phase; validate every retained delta before any deletion."""
    if not enabled(db):
        raise ValueError('FOIS retention is not admitted')
    cutoff = db.execute('SELECT legacy_max_rowid FROM fois_retention_policy WHERE version=?', (VERSION,)).fetchone()[0]
    keep = {r[0] for r in db.execute('SELECT snapshot_id FROM fois_assessment_roots')}
    keep.update(r[0] for r in db.execute('SELECT snapshot_id FROM fois_snapshot_history WHERE rowid<=?', (cutoff,)))
    keep.update(r[0] for r in db.execute('''SELECT snapshot_id FROM
        (SELECT snapshot_id,row_number() OVER(PARTITION BY score_key ORDER BY rowid DESC) n
         FROM fois_snapshot_history) WHERE n<=?''', (OPERATIONAL_LIMIT,)))
    all_rows = dict(db.execute('SELECT snapshot_id,payload FROM fois_snapshot_history'))
    if keep - all_rows.keys():
        raise ValueError('Missing canonical FOIS assessment root')
    reachable = set()
    def visit(identity):
        if identity in reachable:
            return
        state_storage._state(db, identity, set())
        row = db.execute('SELECT format,payload FROM fois_semantic_states WHERE state_id=?', (identity,)).fetchone()
        reachable.add(identity)
        if row[0] == state_storage.DELTA_FORMAT:
            visit(json.loads(zlib.decompress(row[1]))['base'])
    for sid in keep:
        value = json.loads(all_rows[sid])
        if value.get('$storage') == state_storage.FORMAT:
            visit(value['state_id'])
    for (payload,) in db.execute('SELECT payload FROM fois_scores_v2'):
        identity = state_storage.split(json.loads(payload))[0]
        if db.execute('SELECT 1 FROM fois_semantic_states WHERE state_id=?', (identity,)).fetchone():
            visit(identity)
    states = {r[0] for r in db.execute('SELECT state_id FROM fois_semantic_states')}
    return {'retained_observations': sorted(keep), 'reclaimable_observations': sorted(all_rows.keys() - keep),
            'retained_states': sorted(reachable), 'reclaimable_states': sorted(states - reachable)}


def collect(db):
    if not enabled(db):
        return
    candidate = plan(db)
    db.executemany('DELETE FROM fois_snapshot_history WHERE snapshot_id=?',
                   ((k,) for k in candidate['reclaimable_observations']))
    db.executemany('DELETE FROM fois_semantic_states WHERE state_id=?',
                   ((k,) for k in candidate['reclaimable_states']))
    from src.platform.storage_monitor import observe
    observe(db, 'fois')
    return candidate
