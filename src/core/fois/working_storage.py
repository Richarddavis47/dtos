"""League-scoped compute scratch and transactional publication, never a DB copy."""
from __future__ import annotations

import hashlib
import json
from contextlib import closing
from pathlib import Path

from src.core.fois.repository import FOISRepository
from src.core.fois import state_storage
import zlib
from src.platform.storage_gate import connect


def _rows(connection, league_id):
    for table, predicate in (
        ("fois_scores_v2", "league_id=?"),
        ("fois_gm_tenures", "league_id=?"),
        ("fois_takeover_snapshots", "tenure_id IN (SELECT tenure_id FROM fois_gm_tenures WHERE league_id=?)"),
    ):
        rows = connection.execute(
            f"SELECT * FROM {table} WHERE {predicate} ORDER BY 1", (league_id,),
        ).fetchall()
        yield table, rows


def _identity(groups):
    digest = hashlib.sha256()
    for table, rows in groups:
        digest.update(json.dumps([table, [list(row) for row in rows]], separators=(",", ":")).encode())
    return digest.hexdigest()


def prepare(source: Path, target: Path, league_id: str) -> None:
    """Seed only current evaluations/ownership, not accumulated observations."""
    working = FOISRepository(target)
    with closing(connect(source, readonly=True)) as origin:
        origin.execute("BEGIN")
        groups = list(_rows(origin, league_id))
        # Carry only current roots' bounded delta dependencies, not historical
        # observations. Otherwise a scratch full base could collide with an
        # existing delta base and silently exceed the replay-depth bound.
        dependencies = {}
        def retain(identity):
            if identity in dependencies:
                return
            row = origin.execute('SELECT * FROM fois_semantic_states WHERE state_id=?', (identity,)).fetchone()
            if row is None:
                return
            if row[4] != league_id:
                raise RuntimeError('FOIS current dependency league mismatch')
            dependencies[identity] = row
            if row[1] == state_storage.DELTA_FORMAT:
                retain(json.loads(zlib.decompress(row[2]))['base'])
        for (payload,) in origin.execute('SELECT payload FROM fois_scores_v2 WHERE league_id=?', (league_id,)):
            retain(state_storage.split(json.loads(payload))[0])
    with working._connection() as destination:
        for table, rows in groups:
            if rows:
                destination.executemany(
                    f"INSERT INTO {table} VALUES ({','.join('?' for _ in rows[0])})", rows,
                )
        if dependencies:
            destination.executemany('INSERT INTO fois_semantic_states VALUES (?,?,?,?,?)', dependencies.values())
        destination.execute("CREATE TABLE compute_boundary(league_id TEXT PRIMARY KEY, identity TEXT)")
        destination.execute("INSERT INTO compute_boundary VALUES (?,?)", (league_id, _identity(groups)))
        destination.commit()


def publish(working_path: Path, repository: FOISRepository, league_id: str) -> None:
    """Merge one flight atomically, rejecting same-league concurrent advances.

    Other leagues and all prior observation history stay in place. A SQLite
    transaction also avoids replacing an inode beneath existing connections.
    """
    with repository._lock, repository._connection() as connection:
        connection.execute("ATTACH DATABASE ? AS flight", (str(working_path),))
        connection.execute("BEGIN IMMEDIATE")
        boundary = connection.execute(
            "SELECT identity FROM flight.compute_boundary WHERE league_id=?", (league_id,),
        ).fetchone()
        if boundary is None or _identity(_rows(connection, league_id)) != boundary[0]:
            raise RuntimeError("FOIS league evidence advanced before publication")
        for table in ("fois_scores_v2", "fois_gm_tenures", "fois_snapshot_history", "fois_semantic_states"):
            if connection.execute(
                f"SELECT 1 FROM flight.{table} WHERE league_id<>? LIMIT 1", (league_id,),
            ).fetchone():
                raise RuntimeError("FOIS compute publication league mismatch")
        # End prior active tenures before inserting a new active owner.
        connection.execute(
            "UPDATE fois_gm_tenures SET active=0 WHERE league_id=? AND tenure_id IN "
            "(SELECT tenure_id FROM flight.fois_gm_tenures WHERE active=0)", (league_id,),
        )
        for table in ("fois_scores_v2", "fois_gm_tenures"):
            columns = [row[1] for row in connection.execute(f"PRAGMA main.table_info({table})")]
            updates = ','.join(f'{column}=excluded.{column}' for column in columns[1:])
            connection.execute(
                f"INSERT INTO {table} SELECT * FROM flight.{table} WHERE true "
                f"ON CONFLICT({columns[0]}) DO UPDATE SET {updates}",
            )
        for table in ("fois_takeover_snapshots", "fois_semantic_states", "fois_snapshot_history", "fois_evidence_links"):
            connection.execute(f"INSERT OR IGNORE INTO {table} SELECT * FROM flight.{table}")
        connection.commit()
