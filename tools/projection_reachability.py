"""Read-only projection graph inventory. Never imports application services.

Run against a retained copy or a read-only production connection. The report
classifies physical rows; UNREACHABLE_LEGACY is not permission to delete them.
Historical/event roots must be supplied before an operator approves a GC plan.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib


FORMAT = "projection-players-v1"
CLASSES = ("ACTIVE_REACHABLE", "HISTORICAL_CHECKPOINT_REACHABLE",
           "SOURCE_PROVENANCE_REQUIRED", "REBUILDABLE", "UNREACHABLE_LEGACY", "UNKNOWN")


def unpack(value: str) -> tuple[dict, dict]:
    body = json.loads(value)
    if body.get('$storage') == 'projection-provenance-v1':
        return body['envelope'], {}
    if "$storage" not in body:
        return body, {}
    if body.get("$storage") != FORMAT:
        raise ValueError("Unknown projection storage format")
    decoded = json.loads(zlib.decompress(base64.b64decode(body["data"], validate=True)))
    envelope, references = decoded["envelope"], decoded["players"]
    if not isinstance(envelope, dict) or not isinstance(references, dict):
        raise ValueError("Invalid projection envelope")
    if any(not isinstance(ref, list) or len(ref) != 2
           or not isinstance(ref[0], str) for ref in references.values()):
        raise ValueError("Invalid projection player references")
    return envelope, references


def horizon_references(envelope: dict) -> dict[str, str]:
    """Week keys are labels, never snapshot identities."""
    manifest = envelope.get("horizon_snapshot_ids", {})
    if not isinstance(manifest, dict):
        raise ValueError("Horizon must map week to snapshot identity")
    if any(not str(week).isdigit() or not 1 <= int(week) <= 18
           or not isinstance(identity, str) or not identity
           for week, identity in manifest.items()):
        raise ValueError("Invalid horizon manifest")
    return manifest


def analyze(connection: sqlite3.Connection, *, historical_ids=(), details=False) -> dict:
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"projection_snapshots", "projection_player_states"} <= tables:
        raise ValueError("Unsupported projection store")
    totals = {key: Counter(rows=0, payload_bytes=0) for key in CLASSES}
    records, errors, snapshots = [], [], {}
    state_classes = {}
    snapshot_classes = {}
    allowed = {'projection_snapshots', 'projection_player_states', 'projection_publication_heads',
               'projection_actuals', 'projection_checkpoint_roots', 'projection_source_roots',
               'projection_source_history', 'sleeper_projection_snapshots',
               'projection_previous_heads', 'projection_retention_policy'}
    for table in sorted(tables - allowed - {'sqlite_sequence'}):
        errors.append(dict(table=table, reason='UNKNOWN_TABLE_REQUIRES_REVIEW'))

    def record(table, identity, classification, size, reason):
        totals[classification].update(rows=1, payload_bytes=size)
        if details:
            records.append(dict(table=table, identity=identity, classification=classification,
                                payload_bytes=size, reason=reason))

    for sid, league, season, week, stamp, payload in connection.execute(
            "SELECT snapshot_id,league_id,season,week,generated_at,payload FROM projection_snapshots"):
        try:
            envelope, refs = unpack(payload)
            if (str(envelope.get("league_id")) != str(league)
                    or envelope.get("season") != season or envelope.get("week") != week
                    or envelope.get("projection_snapshot_id") != sid):
                raise ValueError("Snapshot row/envelope identity mismatch")
            horizon_references(envelope)
            # Keep only envelopes in memory. Production contains millions of
            # historical references; retaining every decoded map is unbounded.
            snapshots[sid] = (envelope, {}, len(payload.encode()), stamp)
        except (ValueError, KeyError, TypeError, zlib.error) as exc:
            snapshots[sid] = ({}, {}, len(payload.encode()), stamp)
            snapshot_classes[sid] = "UNKNOWN"
            errors.append(dict(snapshot_id=sid, reason=str(exc)))

    def mark(sid, classification, *, parent=None, week=None):
        if sid not in snapshots:
            errors.append(dict(snapshot_id=sid, reason="MISSING_SNAPSHOT", parent=parent))
            return
        envelope, _, _, _ = snapshots[sid]
        if snapshot_classes.get(sid) == "UNKNOWN":
            return
        if parent:
            origin = snapshots[parent][0]
            if (any(envelope.get(k) != origin.get(k) for k in
                    ("league_id", "season", "scoring_profile_id", "model_version", "contract_version"))
                    or envelope.get("week") != int(week)):
                errors.append(dict(snapshot_id=sid, reason="HORIZON_SCOPE_MISMATCH", parent=parent))
                snapshot_classes[sid] = "UNKNOWN"
                return
        if snapshot_classes.get(sid) == "ACTIVE_REACHABLE":
            return
        snapshot_classes[sid] = classification
        for w, child in horizon_references(envelope).items():
            if child == sid:
                if envelope.get("week") != int(w):
                    errors.append(dict(snapshot_id=sid, reason="SELF_REFERENCE_WEEK_MISMATCH"))
                continue
            if parent is not None:
                errors.append(dict(snapshot_id=sid, reason="NESTED_HORIZON"))
                continue
            mark(child, classification, parent=sid, week=w)

    heads = list(connection.execute("SELECT league_id,snapshot_id FROM projection_publication_heads")) if "projection_publication_heads" in tables else []
    for league, sid in heads:
        if sid in snapshots and str(snapshots[sid][0].get("league_id")) != str(league):
            errors.append(dict(snapshot_id=sid, reason="HEAD_LEAGUE_MISMATCH"))
            snapshot_classes[sid] = "UNKNOWN"
        else:
            mark(sid, "ACTIVE_REACHABLE")
    if 'projection_previous_heads' in tables:
        for league, sid in connection.execute('SELECT league_id,snapshot_id FROM projection_previous_heads'):
            if sid in snapshots and str(snapshots[sid][0].get('league_id')) != str(league):
                errors.append(dict(snapshot_id=sid, reason='PREVIOUS_HEAD_LEAGUE_MISMATCH'))
            mark(sid, 'ACTIVE_REACHABLE')
    # Also retain bounded single-week publications coexisting with horizon heads.
    latest = {}
    for sid, league in connection.execute('SELECT snapshot_id,league_id FROM projection_snapshots ORDER BY generated_at DESC,rowid DESC'):
        if latest.get(league, 0) < 2:
            mark(sid, 'ACTIVE_REACHABLE')
            latest[league] = latest.get(league, 0) + 1
    historical = set(historical_ids)
    if "projection_actuals" in tables:
        historical.update(r[0] for r in connection.execute("SELECT DISTINCT snapshot_id FROM projection_actuals"))
    if "projection_checkpoint_roots" in tables:
        historical.update(r[0] for r in connection.execute("SELECT snapshot_id FROM projection_checkpoint_roots"))
    for sid in sorted(historical):
        mark(sid, "HISTORICAL_CHECKPOINT_REACHABLE")

    priorities = {name: i for i, name in enumerate(CLASSES)}
    def state_refs(refs, classification):
        for ref in refs.values():
            sid = ref[0]
            existing = state_classes.get(sid)
            if existing is None or priorities[classification] < priorities[existing]:
                state_classes[sid] = classification

    for sid, payload in connection.execute("SELECT snapshot_id,payload FROM projection_snapshots ORDER BY snapshot_id"):
        _, _, size, _ = snapshots[sid]
        classification = snapshot_classes.get(sid, "UNREACHABLE_LEGACY")
        if classification not in ("UNREACHABLE_LEGACY", "UNKNOWN"):
            _, refs = unpack(payload)
            state_refs(refs, classification)
        record("projection_snapshots", sid, classification, size,
               "Reachability from current/event roots" if classification != "UNREACHABLE_LEGACY"
               else "Superseded snapshot; historical retention review required")
    source_latest, source_keep = {}, set()
    if "projection_source_history" in tables:
        source_scopes = {(env.get('season'), env.get('week')) for sid, (env, _, _, _) in snapshots.items()
                         if snapshot_classes.get(sid) in ('ACTIVE_REACHABLE', 'HISTORICAL_CHECKPOINT_REACHABLE')}
        if 'sleeper_projection_snapshots' in tables:
            source_scopes.update((row[0], row[1]) for row in connection.execute('SELECT season,week FROM sleeper_projection_snapshots'))
        for season, week, oid in connection.execute(
                'SELECT season,week,observation_id FROM projection_source_history ORDER BY observation_id DESC'):
            scope = season, week
            if scope in source_scopes and source_latest.get(scope, 0) < 8:
                source_keep.add(oid)
            source_latest[scope] = source_latest.get(scope, 0) + 1
        if 'projection_source_roots' in tables:
            for (oid,) in connection.execute('SELECT observation_id FROM projection_source_roots'):
                source_keep.add(oid)
        for oid, season, week, payload in connection.execute(
                "SELECT observation_id,season,week,payload FROM projection_source_history"):
            classification = "SOURCE_PROVENANCE_REQUIRED" if oid in source_keep else "UNREACHABLE_LEGACY"
            try:
                _, refs = unpack(payload)
                if classification != "UNREACHABLE_LEGACY":
                    state_refs(refs, classification)
            except (ValueError, KeyError, TypeError, zlib.error) as exc:
                classification = "UNKNOWN"
                errors.append(dict(source_observation_id=oid, reason=str(exc)))
            record("projection_source_history", oid, classification, len(payload.encode()),
                   "Current source observation" if classification == "SOURCE_PROVENANCE_REQUIRED"
                   else "Historical source observation; event dependencies require review")
    # A state-id ordering forces millions of random table lookups on the large
    # legacy store. Scan physical rows; sort only optional report metadata below.
    for sid, size in connection.execute("SELECT state_id,length(payload) FROM projection_player_states"):
        classification = state_classes.pop(sid, "UNREACHABLE_LEGACY")
        record("projection_player_states", sid, classification, size, "Referenced content-addressed player state")
    for sid, classification in state_classes.items():
        errors.append(dict(state_id=sid, classification=classification, reason="MISSING_PLAYER_STATE"))
    if "sleeper_projection_snapshots" in tables:
        for identity, size in connection.execute("SELECT fingerprint,length(payload) FROM sleeper_projection_snapshots"):
            record("sleeper_projection_snapshots", identity, "REBUILDABLE", size, "Bounded current provider cache")
    page_size = connection.execute("PRAGMA page_size").fetchone()[0]
    summary = dict(classifications={k: dict(v) for k, v in totals.items()},
                   publication_heads=len(heads), historical_roots=len(historical),
                   unresolved_references=errors, graph_valid=not errors,
                   physical_bytes=connection.execute("PRAGMA page_count").fetchone()[0] * page_size,
                   freelist_bytes=connection.execute("PRAGMA freelist_count").fetchone()[0] * page_size,
                   deletion_authorized=False,
                   estimate_note="Payload bytes exclude SQLite pages/indexes. Historical source rows retain compact provenance, not their broad player payload. Not a reclaim guarantee.")
    if details:
        summary["rows"] = sorted(records, key=lambda row: (row['table'], str(row['identity'])))
    summary["report_sha256"] = hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--historical-snapshot", action="append", default=[])
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    with closing(sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        print(json.dumps(analyze(connection, historical_ids=args.historical_snapshot, details=args.details), sort_keys=True))


if __name__ == "__main__":
    main()
