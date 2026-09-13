"""Focused source-parity replay for the missing exact draft-time branch only."""
import json
from collections import Counter, defaultdict
from pathlib import Path
from src.core.history_context.store import canonical_history_store, sleeper_season_cache
from src.core.fois.decision_evaluators import evaluate_decision


def main():
    retained=json.loads(Path('docs/BATCH4_PRODUCTION_EQUIVALENT_COVERAGE.json').read_text())
    league=retained['provenance']['league']
    for year, source in retained['provenance']['archives'].items():
        archive=sleeper_season_cache.read(league,int(year))
        assert archive and archive.checksum == source['source_semantic_checksum'], 'Source parity failed'
    _, selections=canonical_history_store.records(league,'draft_pick',limit=10000)
    result=defaultdict(Counter)
    for source in selections:
        assert source.get('occurred_at') is None, 'This replay supports only the proven missing-time branch'
        pick=source['payload']
        roster=str(pick['roster_id'])
        row=dict(draft_id=pick['draft_id'],player_id=pick['player_id'],pick_number=pick['pick_no'],
                 owner_id=retained['managers'][roster]['owner_by_season'][str(source['season'])],
                 league_id=league,occurred_at=None)
        process=evaluate_decision(row,'drafting')['process']
        result[roster].update([process['evaluability'],*process['reasons']])
    print(json.dumps({'scope':'verified_archive_missing_time_branch_only',
                      'managers':dict(result)},sort_keys=True))


if __name__=='__main__':
    main()
