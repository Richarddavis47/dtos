"""Build a separately admitted compact projection copy; never replace the source.

Unknown tables, invalid references, scope mismatches and failed output equality
abort. This tool is for local rehearsal; production replacement needs separate
operator authorization and an exclusive storage gate/quiesced publisher.
"""

from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

from src.core.projection_intelligence import retention, state_storage

ALLOWED = {
    "projection_snapshots",
    "projection_publication_heads",
    "projection_actuals",
    "sleeper_projection_snapshots",
    "projection_source_history",
    "projection_player_states",
    "projection_retention_policy",
    "projection_previous_heads",
    "projection_checkpoint_roots",
    "projection_source_roots",
}


def verify_copy(source_path, target_path):
    """Independently verify the exact admitted retention transform, read-only.

    Unlike a current-head comparison, this also checks all metadata, expired
    source provenance, actuals, roots and the exact reachable player-state set.
    Neither connection initializes application schemas.
    """
    with closing(sqlite3.connect(Path(source_path).resolve().as_uri() + '?mode=ro', uri=True)) as source, closing(
        sqlite3.connect(Path(target_path).resolve().as_uri() + '?mode=ro', uri=True)
    ) as target:
        for db in (source, target):
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('Projection integrity failed')
            if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone():
                raise ValueError('Projection triggers/views require review')
        def tables(db):
            return {r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
        original, compact = tables(source), tables(target)
        policy_tables = {'projection_retention_policy', 'projection_previous_heads',
                         'projection_checkpoint_roots', 'projection_source_roots'}
        if original - ALLOWED or compact != original | policy_tables:
            raise ValueError('Projection table identity changed')
        keep, source_keep = retention.plan(source)
        references = set()
        counts = {}
        for table in sorted(compact - {'projection_player_states', 'projection_retention_policy'}):
            if table not in original:
                if target.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]:
                    raise ValueError('Unexpected new retention roots')
                continue
            columns = [r[1] for r in source.execute(f'PRAGMA table_info("{table}")')]
            if list(source.execute(f'PRAGMA table_info("{table}")')) != list(target.execute(f'PRAGMA table_info("{table}")')):
                raise ValueError('Projection column semantics changed')
            actual = iter(target.execute(f'SELECT * FROM "{table}" ORDER BY rowid'))
            count = 0
            for row in source.execute(f'SELECT * FROM "{table}" ORDER BY rowid'):
                record = dict(zip(columns, row))
                if table == 'projection_snapshots' and record['snapshot_id'] not in keep:
                    continue
                expected = list(row)
                if table in ('projection_snapshots', 'projection_source_history'):
                    envelope, refs = retention.unpack(record['payload'])
                    if table == 'projection_source_history' and record['observation_id'] not in source_keep:
                        expected[columns.index('payload')] = json.dumps(
                            {'$storage': retention.PROVENANCE, 'envelope': envelope},
                            sort_keys=True, separators=(',', ':'))
                    else:
                        references.update(ref[0] for ref in refs.values())
                if next(actual, None) != tuple(expected):
                    raise ValueError(f'Projection retained evidence changed: {table}')
                count += 1
            if next(actual, None) is not None:
                raise ValueError(f'Unexpected retained projection rows: {table}')
            counts[table] = count
        if target.execute('SELECT version FROM projection_retention_policy').fetchall() != [(retention.POLICY,)]:
            raise ValueError('Wrong projection retention policy')
        if {r[0] for r in target.execute('SELECT state_id FROM projection_player_states')} != references:
            raise ValueError('Projection reachable state set changed')
        for identity in references:
            old = source.execute('SELECT * FROM projection_player_states WHERE state_id=?', (identity,)).fetchone()
            new = target.execute('SELECT * FROM projection_player_states WHERE state_id=?', (identity,)).fetchone()
            if old is None or old != new:
                raise ValueError('Projection player evidence changed')
        # Validate retained horizon/league identities independently in the target.
        retention.plan(target)
        return {'retained_evidence_equal': True, 'retained_counts': counts,
                'player_states': len(references), 'policy': retention.POLICY}


def build_copy(source_path, target_path, *, maximum_bytes, reserve_bytes=0):
    source_path, target_path = Path(source_path).resolve(), Path(target_path).absolute()
    if target_path.exists() or target_path.is_symlink() or source_path == target_path:
        raise ValueError("Target must be a new local file, not the source")
    if (
        maximum_bytes < 4096
        or shutil.disk_usage(target_path.parent).free
        < maximum_bytes * 2 + reserve_bytes
    ):
        raise ValueError("Insufficient admitted copy headroom")
    with closing(
        sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)
    ) as source:
        source.execute("PRAGMA query_only=ON")
        source.execute("BEGIN")
        schemas = dict(
            source.execute(
                "SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        )
        if set(schemas) - ALLOWED:
            raise ValueError("Unknown projection tables require retention review")
        if source.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone():
            raise ValueError('Projection triggers/views require retention review')
        keep, source_keep = retention.plan(source)
        state_ids = set()
        proof = hashlib.sha256()
        counts = {}
        with closing(sqlite3.connect(target_path)) as target:
            target.execute("PRAGMA synchronous=FULL")
            target.execute(f"PRAGMA max_page_count={maximum_bytes // 4096}")
            for sql in schemas.values():
                target.execute(sql)
            target.executescript(retention.SCHEMA)
            for table in sorted(schemas):
                if table in ("projection_player_states", "projection_retention_policy"):
                    continue
                columns = [
                    row[1] for row in source.execute(f'PRAGMA table_info("{table}")')
                ]
                retained = 0
                for values in source.execute(f'SELECT * FROM "{table}" ORDER BY rowid'):
                    values = list(values)
                    record = dict(zip(columns, values))
                    if (
                        table == "projection_snapshots"
                        and record["snapshot_id"] not in keep
                    ):
                        continue
                    if table in ("projection_snapshots", "projection_source_history"):
                        payload = record["payload"]
                        envelope, refs = retention.unpack(payload)
                        if (
                            table == "projection_source_history"
                            and record["observation_id"] not in source_keep
                        ):
                            values[columns.index("payload")] = json.dumps(
                                {
                                    "$storage": retention.PROVENANCE,
                                    "envelope": envelope,
                                },
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                        else:
                            state_ids.update(ref[0] for ref in refs.values())
                    target.execute(
                        f'INSERT INTO "{table}" VALUES ({",".join("?" for _ in values)})',
                        values,
                    )
                    retained += 1
                counts[table] = retained
            for identity in sorted(state_ids):
                row = source.execute(
                    "SELECT * FROM projection_player_states WHERE state_id=?",
                    (identity,),
                ).fetchone()
                if row is None:
                    raise ValueError("Missing referenced player state")
                target.execute("INSERT INTO projection_player_states VALUES (?,?)", row)
            target.execute(
                "INSERT INTO projection_retention_policy VALUES (?)",
                (retention.POLICY,),
            )
            for (sql,) in source.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
            ):
                target.execute(sql)
            target.commit()
            for table, identity_column, retained_ids in (
                ("projection_snapshots", "snapshot_id", keep),
                ("projection_source_history", "observation_id", source_keep),
            ):
                for identity in sorted(retained_ids):
                    old = source.execute(
                        f"SELECT payload FROM {table} WHERE {identity_column}=?",
                        (identity,),
                    ).fetchone()[0]
                    new = target.execute(
                        f"SELECT payload FROM {table} WHERE {identity_column}=?",
                        (identity,),
                    ).fetchone()[0]
                    if json.loads(old).get("$storage") == retention.PROVENANCE:
                        if old != new:
                            raise ValueError("Historical provenance changed")
                        continue
                    a, b = (
                        state_storage.decode(source, old),
                        state_storage.decode(target, new),
                    )
                    if a != b:
                        raise ValueError("Retained projection output changed")
                    proof.update(
                        json.dumps(
                            [table, identity, a], sort_keys=True, separators=(",", ":")
                        ).encode()
                    )
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Compact output integrity failed")
            counts["projection_player_states"] = len(state_ids)
    return {
        "before_bytes": source_path.stat().st_size,
        "after_bytes": target_path.stat().st_size,
        "reclaimed_bytes": source_path.stat().st_size - target_path.stat().st_size,
        "retained_counts": counts,
        "retained_outputs_sha256": proof.hexdigest(),
        "retained_outputs_equal": True,
        "source_unchanged": True,
    }
