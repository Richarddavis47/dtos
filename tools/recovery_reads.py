"""Read-only deployed-codec/schema checks, without service initialization."""
from contextlib import closing
import json
import sqlite3

from src.core.fois.repository import _score
from src.core.fois import state_storage as fois_codec
from src.core.projection_intelligence import state_storage as projection_codec


def open_readonly(path):
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    db.execute('PRAGMA query_only=ON')
    return db


def fois_reads(path, leagues):
    result = {}
    with closing(open_readonly(path)) as db:
        for league in leagues:
            rows = list(db.execute('SELECT score_key,payload FROM fois_scores_v2 WHERE league_id=?', (league,)))
            if not rows:
                raise ValueError('Required FOIS league is absent')
            history = 0
            for identity, raw in rows:
                score = _score(json.loads(raw))
                if score.league_id != league or score.score_key != identity:
                    raise ValueError('FOIS current scope mismatch')
                for (payload,) in db.execute('SELECT payload FROM fois_snapshot_history WHERE score_key=? ORDER BY generated_at DESC LIMIT 2', (identity,)):
                    decoded = fois_codec.decode(db, payload)
                    score = _score(decoded)
                    if score.league_id != league or score.score_key != identity:
                        raise ValueError('FOIS history scope mismatch')
                    history += 1
            result[league] = {'current': len(rows), 'historical': history}
    return result


def projection_reads(path, leagues):
    result = {}
    with closing(open_readonly(path)) as db:
        for league in leagues:
            row = db.execute('SELECT s.payload FROM projection_publication_heads h JOIN projection_snapshots s ON s.snapshot_id=h.snapshot_id WHERE h.league_id=?', (league,)).fetchone()
            if not row:
                raise ValueError('Required Projection league is absent')
            head = projection_codec.decode(db, row[0])
            if head['league_id'] != league:
                raise ValueError('Projection head scope mismatch')
            weeks = set()
            for week, identity in head.get('horizon_snapshot_ids', {}).items():
                row = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (identity,)).fetchone()
                if not row:
                    raise ValueError('Projection horizon reference is missing')
                state = projection_codec.decode(db, row[0])
                if (state['league_id'] != league or state['season'] != head['season']
                        or int(state['week']) != int(week)):
                    raise ValueError('Projection horizon scope mismatch')
                weeks.add(int(week))
            result[league] = {'season': head['season'], 'week': head['week'], 'horizon': sorted(weeks),
                              'players': len(head.get('players', {}))}
    return result


def mixed_reads(fois_path, projection_path, leagues):
    if not leagues or len(set(leagues)) != len(leagues):
        raise ValueError('Explicit distinct acceptance leagues required')
    return {'passed': True, 'scope': 'read-only deployed model and storage-codec checks',
            'fois': fois_reads(fois_path, leagues),
            'projection': projection_reads(projection_path, leagues)}
