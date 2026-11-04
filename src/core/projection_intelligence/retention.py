"""Explicitly admitted projection retention; never enabled on legacy stores by startup.

Active heads plus one predecessor, event/actual roots and eight recent source
transitions per season/week retain full evidence. Older source observations keep
identity/time provenance, not a broad player universe. Expired as-of evidence is
unavailable, never reconstructed from a later observation.
"""

import base64
import json
import zlib

POLICY = "projection-retention-v1"
PROVENANCE = "projection-provenance-v1"
SOURCE_WINDOW = 8
SCHEMA = """
CREATE TABLE IF NOT EXISTS projection_retention_policy(version TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS projection_previous_heads(league_id TEXT PRIMARY KEY,snapshot_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projection_checkpoint_roots(event_id TEXT PRIMARY KEY,snapshot_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projection_source_roots(event_id TEXT PRIMARY KEY,observation_id INTEGER NOT NULL);
"""


def unpack(payload):
    body = json.loads(payload)
    if body.get("$storage") == "projection-players-v1":
        body = json.loads(
            zlib.decompress(base64.b64decode(body["data"], validate=True))
        )
        return body["envelope"], body["players"]
    if body.get("$storage") == PROVENANCE:
        return body["envelope"], {}
    if "$storage" in body:
        raise ValueError("Unknown projection retention representation")
    return {k: v for k, v in body.items() if k != "players"}, {}


def enabled(db):
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='projection_retention_policy'").fetchone() is None:
        return False
    return (
        db.execute(
            "SELECT 1 FROM projection_retention_policy WHERE version=?", (POLICY,)
        ).fetchone()
        is not None
    )


def previous_head(db, league):
    if not enabled(db):
        return
    db.execute(
        "INSERT INTO projection_previous_heads SELECT league_id,snapshot_id FROM projection_publication_heads WHERE league_id=? "
        "ON CONFLICT(league_id) DO UPDATE SET snapshot_id=excluded.snapshot_id",
        (league,),
    )


def plan(db):
    tables = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    allowed = {
        "projection_snapshots",
        "projection_player_states",
        "projection_publication_heads",
        "projection_actuals",
        "projection_checkpoint_roots",
        "projection_source_roots",
        "projection_source_history",
        "sleeper_projection_snapshots",
        "projection_previous_heads",
        "projection_retention_policy",
        "projection_source_expiry",
        "projection_snapshot_quarantine",
        "sqlite_sequence",
    }
    if tables - allowed:
        raise ValueError("Unknown projection tables require retention review")
    snapshots = {}
    for sid, league, season, week, payload in db.execute(
        "SELECT snapshot_id,league_id,season,week,payload FROM projection_snapshots"
    ):
        envelope, _ = unpack(payload)
        if (envelope.get('projection_snapshot_id') != sid or str(envelope.get('league_id')) != str(league)
                or envelope.get('season') != season or envelope.get('week') != week):
            raise ValueError('Projection row/envelope identity mismatch')
        snapshots[sid] = envelope
    from . import quarantine
    quarantined = quarantine.identities(db)
    roots = set()
    for league, sid in db.execute(
        "SELECT league_id,snapshot_id FROM projection_publication_heads"
    ):
        if sid not in snapshots or str(snapshots[sid].get("league_id")) != str(league):
            raise ValueError("Missing or cross-league projection head")
        roots.add(sid)
    # Also retain the latest two single-week publications. The legacy publisher
    # can coexist with a horizon publisher; it must not lose its returned handle.
    recent = {}
    for sid, league in db.execute(
        "SELECT snapshot_id,league_id FROM projection_snapshots ORDER BY generated_at DESC,rowid DESC"
    ):
        if sid in quarantined:
            continue
        if recent.get(league, 0) < 2:
            roots.add(sid)
            recent[league] = recent.get(league, 0) + 1
    for table in (
        "projection_previous_heads",
        "projection_checkpoint_roots",
        "projection_actuals",
    ):
        if table in tables:
            roots.update(
                row[0]
                for row in db.execute(f"SELECT DISTINCT snapshot_id FROM {table}")
            )
    keep = set()

    def visit(sid, parent=None, week=None):
        if sid in quarantined:
            raise ValueError('Quarantined projection has a canonical retention root')
        if sid not in snapshots:
            raise ValueError("Missing retained projection snapshot")
        row = snapshots[sid]
        if parent is not None and (
            row.get("week") != int(week)
            or any(
                row.get(k) != parent.get(k)
                for k in (
                    "league_id",
                    "season",
                    "scoring_profile_id",
                    "model_version",
                    "contract_version",
                    "semantic_policy_version",
                )
            )
        ):
            raise ValueError("Projection horizon scope mismatch")
        if sid in keep:
            return
        keep.add(sid)
        manifest = row.get("horizon_snapshot_ids", {})
        if not isinstance(manifest, dict):
            raise ValueError("Invalid projection horizon")
        for w, child in manifest.items():
            if not str(w).isdigit() or not 1 <= int(w) <= 18 or not isinstance(child, str):
                raise ValueError('Invalid projection horizon identity')
            visit(child, row, w)

    for sid in sorted(roots):
        visit(sid)
    source_keep = set()
    counts = {}
    source_scopes = {
        (row[0], row[1])
        for row in db.execute("SELECT season,week FROM sleeper_projection_snapshots")
    }
    source_scopes.update(
        (snapshots[sid].get("season"), snapshots[sid].get("week")) for sid in keep
    )
    for oid, season, week in db.execute(
        "SELECT observation_id,season,week FROM projection_source_history ORDER BY observation_id DESC"
    ):
        scope = (season, week)
        if scope in source_scopes and counts.get(scope, 0) < SOURCE_WINDOW:
            source_keep.add(oid)
        counts[scope] = counts.get(scope, 0) + 1
    # A retained derived snapshot also roots the source known at its original
    # publication boundary. The recent-source window alone is not reachability:
    # quiet leagues and historical events can outlive eight source transitions.
    # Missing legacy sources remain missing; strict provenance admission still
    # rejects them. Never fabricate a source from a derived or current value.
    from .provenance_retention import stamp
    observations = {}
    expiry = dict(db.execute('SELECT observation_id,valid_until FROM projection_source_expiry')) if 'projection_source_expiry' in tables else {}
    for oid, season, week, observed, fingerprint in db.execute(
        "SELECT observation_id,season,week,observed_at,fingerprint "
        "FROM projection_source_history ORDER BY observation_id"
    ):
        observations.setdefault((season, week), []).append((oid, stamp(observed), fingerprint))
    for sid in keep:
        snapshot = snapshots[sid]
        fingerprint = snapshot.get('sleeper_evidence_snapshot_id')
        if not fingerprint:
            continue
        boundary = stamp(snapshot['generated_at'])
        group = observations.get((snapshot['season'], snapshot['week']), [])
        for index, row in enumerate(group):
            ends = [stamp(value) for value in (
                expiry.get(row[0]), group[index + 1][1] if index + 1 < len(group) else None,
            ) if value is not None]
            end = min(ends) if ends else None
            if row[2] == fingerprint and row[1] <= boundary and (end is None or boundary < end):
                source_keep.add(row[0])
    if "projection_source_roots" in tables:
        for (oid,) in db.execute("SELECT observation_id FROM projection_source_roots"):
            row = db.execute(
                "SELECT payload FROM projection_source_history WHERE observation_id=?", (oid,)
            ).fetchone()
            if row is None or json.loads(row[0]).get('$storage') == PROVENANCE:
                raise ValueError("Missing source event root")
            source_keep.add(oid)
    return keep, source_keep


def collect(db):
    """Caller owns the atomic publication transaction. Legacy policy stays inert."""
    if not enabled(db):
        return
    keep, source_keep = plan(db)
    from . import provenance_retention
    provenance_plan = None
    if provenance_retention.enabled(db):
        provenance_plan = provenance_retention.plan(db, keep)
        source_keep = set(provenance_plan['retained'])
    from . import quarantine
    quarantined = quarantine.identities(db)
    state_ids = set()
    for sid, payload in db.execute(
        "SELECT snapshot_id,payload FROM projection_snapshots"
    ).fetchall():
        if sid in keep or sid in quarantined:
            _, refs = unpack(payload)
            state_ids.update(ref[0] for ref in refs.values())
        else:
            db.execute("DELETE FROM projection_snapshots WHERE snapshot_id=?", (sid,))
    for oid, payload in db.execute(
        "SELECT observation_id,payload FROM projection_source_history"
    ).fetchall():
        envelope, refs = unpack(payload)
        if oid in source_keep:
            state_ids.update(ref[0] for ref in refs.values())
        elif provenance_plan is None and (refs or "players" in json.loads(payload)):
            compact = json.dumps(
                {"$storage": PROVENANCE, "envelope": envelope},
                sort_keys=True,
                separators=(",", ":"),
            )
            db.execute(
                "UPDATE projection_source_history SET payload=? WHERE observation_id=?",
                (compact, oid),
            )
    if provenance_plan is not None:
        provenance_retention.collect(db, provenance_plan)
    # Temporary table is connection-local and never adds a durable source copy.
    db.execute(
        "CREATE TEMP TABLE IF NOT EXISTS retained_projection_states(state_id TEXT PRIMARY KEY)"
    )
    db.execute("DELETE FROM retained_projection_states")
    db.executemany(
        "INSERT INTO retained_projection_states VALUES (?)",
        ((sid,) for sid in sorted(state_ids)),
    )
    missing = db.execute(
        "SELECT 1 FROM retained_projection_states r LEFT JOIN projection_player_states s USING(state_id) WHERE s.state_id IS NULL LIMIT 1"
    ).fetchone()
    if missing:
        raise ValueError("Missing retained player state")
    db.execute(
        "DELETE FROM projection_player_states WHERE state_id NOT IN (SELECT state_id FROM retained_projection_states)"
    )
    from src.platform.storage_monitor import observe
    observe(db, 'projection')


def pin_snapshot(db, *, event_id, snapshot_id):
    from . import quarantine, provenance_retention
    if snapshot_id in quarantine.identities(db):
        raise ValueError('Unsupported projection cannot become a canonical historical checkpoint')
    if (
        not event_id
        or not db.execute(
            "SELECT 1 FROM projection_snapshots WHERE snapshot_id=?", (snapshot_id,)
        ).fetchone()
    ):
        raise ValueError("Historical projection checkpoint must already exist")
    existing = db.execute(
        "SELECT snapshot_id FROM projection_checkpoint_roots WHERE event_id=?",
        (event_id,),
    ).fetchone()
    if existing and existing[0] != snapshot_id:
        raise ValueError("Historical projection event cannot be rewritten")
    payload = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (snapshot_id,)).fetchone()[0]
    envelope, _ = unpack(payload)
    if not envelope.get('sleeper_evidence_snapshot_id'):
        raise ValueError('Historical projection checkpoint requires source provenance')
    provenance_retention.plan(db, {snapshot_id})
    db.execute(
        "INSERT OR IGNORE INTO projection_checkpoint_roots VALUES (?,?)",
        (event_id, snapshot_id),
    )


def pin_source(db, *, event_id, observation_id):
    row = db.execute(
        "SELECT payload FROM projection_source_history WHERE observation_id=?",
        (observation_id,),
    ).fetchone()
    if not event_id or row is None or json.loads(row[0]).get("$storage") == PROVENANCE:
        raise ValueError("Historical source checkpoint must have retained evidence")
    existing = db.execute(
        "SELECT observation_id FROM projection_source_roots WHERE event_id=?",
        (event_id,),
    ).fetchone()
    if existing and existing[0] != observation_id:
        raise ValueError("Historical source event cannot be rewritten")
    db.execute(
        "INSERT OR IGNORE INTO projection_source_roots VALUES (?,?)",
        (event_id, observation_id),
    )
