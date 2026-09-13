"""Local-only replay of the authorized bounded production evidence export."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import zipfile
from dataclasses import asdict


def main():
    root = Path('.validation/batch4-assessment-transfer').resolve()
    archive = root / 'dtos-batch4-assessments.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '45f2af23af87344888ece78173deaee834e7609ce0a04b09b6d314dae4a1cafe'
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('manifest.json'))
        body = z.read('tables.json')
    assert hashlib.sha256(body).hexdigest() == manifest['tables_sha256']
    cache = Path(os.environ['TEMP']) / 'sleeper-season-cache'
    folder = cache / hashlib.sha256(manifest['league'].encode()).hexdigest()[:16]
    for year, expected in manifest['archives'].items():
        retained = json.loads(gzip.decompress((folder / (year + '.json.gz')).read_bytes()))
        assert retained['checksum'] == expected['checksum'], year
    os.environ['DTOS_HISTORY_STORAGE_ROOT'] = str(root)
    os.environ['DTOS_DURABLE_HISTORY_REQUIRED'] = 'false'
    os.environ['DTOS_CACHE_FILE'] = str(root / 'cache.json')
    os.environ['DTOS_INTELLIGENCE_CHECKPOINT_FILE'] = str(root / 'replay.sqlite3')
    os.environ['DTOS_METADATA_DB_FILE'] = str(root / 'metadata.sqlite3')
    os.environ['DTOS_SLEEPER_SEASON_CACHE_ROOT'] = str(cache)
    from src.core.intelligence_memory import intelligence_checkpoint_store
    from src.core.history_context.store import canonical_history_store
    from src.core.intelligence_memory.checkpoint_flight import checkpoint_read_flight
    from src.core.fois.history import load_results_history
    from tools.validation.audit_fois_decision_coverage import manager_panel
    tables = json.loads(body)
    with sqlite3.connect(root / 'replay.sqlite3') as connection:
        for table in ('global_market_observations', 'intelligence_checkpoints', 'market_observation_references'):
            for row in tables[table]:
                keys = list(row)
                connection.execute('INSERT OR IGNORE INTO ' + table + ' (' + ','.join(keys) + ') VALUES (' + ','.join('?' for _ in keys) + ')', [row[k] for k in keys])
    with checkpoint_read_flight(intelligence_checkpoint_store) as reader:
        histories = load_results_history(canonical_history_store, manifest['league'], checkpoint_reader=reader)
        panel = manager_panel(histories, league_id=manifest['league'])
        output = {'provenance': manifest, 'checkpoint_generation': reader.generation, 'managers': panel}
    (root / 'assessment-panel.json').write_text(json.dumps(output, sort_keys=True), encoding='utf-8')
    # Exercise the actual preparation -> attribution -> engine -> repository
    # path outside production, using the same verified history. Do not derive
    # active category quality from the diagnostic report's coverage counts.
    from src.core.fois.repository import FOISRepository
    from src.core.fois.service import FOISService
    repository = FOISRepository(root / 'active-fois.sqlite3')
    teams = []
    for roster, history in histories.items():
        owners = set(history.get('owner_by_season', {}).values())
        if len(owners) != 1:
            raise ValueError('Day Traders active proof requires explicit tenure splitting')
        teams.append({'roster_id': int(roster), 'owner_id': next(iter(owners)), 'players': []})
    scores = FOISService(repository)._generate_sync({
        'league': {'league_id': manifest['league'], 'season': '2026'},
        'teams': teams, 'fois_history': histories,
    })
    active = {
        'source_tables_sha256': manifest['tables_sha256'],
        'scope': 'verified production-equivalent Day Traders; local active preparation',
        'managers': [{
            'franchise_id': score.franchise_id, 'owner_id': score.owner_id,
            'model_version': score.model_version,
            'overall': score.overall_score, 'overall_grade': score.overall_letter_grade,
            'confidence': score.confidence, 'coverage': score.completeness,
            'strengths': score.strengths, 'weaknesses': score.weaknesses,
            'categories': [asdict(category) for category in score.category_scores],
        } for score in scores],
    }
    Path('docs/BATCH4_ACTIVE_QUALITY_PANEL.json').write_text(
        json.dumps(active, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'managers': len(panel), 'counts': manifest['counts'], 'panel': str(root / 'assessment-panel.json')}))


if __name__ == '__main__':
    main()
