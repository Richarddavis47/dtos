"""One disposable read-only history producer. Stdout is an anonymous spool."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import threading


def _parent_lifetime():
    # The parent keeps stdin open for this child's entire lifetime. Unlike a
    # cancelled Python future, parent death must not leave unowned CPU work.
    while os.read(sys.stdin.fileno(), 1):
        pass
    os._exit(1)


def produce(spec, stream):
    from fastapi.encoders import jsonable_encoder
    from src.core.fois.models import FOIS_MODEL_VERSION
    from src.core.fois.repository import FOISRepository

    repository = FOISRepository(Path(spec['database']), readonly=True)
    league_id, gm_id = spec['league_id'], spec['gm_id']
    score = repository.score_for_gm(league_id, gm_id, FOIS_MODEL_VERSION)
    if score is None:
        return 3
    metadata = {**spec['metadata'],
        'brain_snapshot_id': score.brain_snapshot_id,
        'brain_version': score.brain_version,
        'generation_timestamp': score.generated_at,
        'confidence': score.confidence, 'completeness': score.completeness,
        'evidence_state': ('retained_not_revalidated' if spec['retained'] else score.evidence_state)}
    if spec['kind'] == 'profile':
        tenure = repository.tenure_for_gm(league_id, gm_id)
        metadata.update(profile=jsonable_encoder(score), tenure=jsonable_encoder(tenure),
            takeover=jsonable_encoder(repository.takeover(tenure.tenure_id)) if tenure else None)

    def encoded(value):
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()

    # Match the existing JSONResponse wire representation, without retaining
    # the complete tuple or a second full jsonable_encoder object graph.
    stream.write(encoded(metadata)[:-1])
    key = b',"history":[' if spec['kind'] == 'profile' else b',"timeline":['
    stream.write(key)
    first = True
    for row in repository.iter_timeline(league_id, gm_id, current=score):
        if spec['kind'] == 'profile' and row.evaluation_kind == 'current_canonical':
            continue
        if not first:
            stream.write(b',')
        stream.write(encoded(jsonable_encoder(row)))
        first = False
    stream.write(b'],"gm_quality_is_not_team_quality":true}' if spec['kind'] == 'profile' else b']}')
    stream.flush()
    return 0


def main():
    spec = json.loads(sys.stdin.buffer.readline())
    threading.Thread(target=_parent_lifetime, daemon=True).start()
    try:
        return produce(spec, sys.stdout.buffer)
    except Exception as exc:
        from src.core.fois.state_delta import InvalidDeltaError
        # No payload, paths, credentials or exception strings cross this pipe.
        return 4 if isinstance(exc, InvalidDeltaError) else 5


if __name__ == '__main__':
    raise SystemExit(main())
