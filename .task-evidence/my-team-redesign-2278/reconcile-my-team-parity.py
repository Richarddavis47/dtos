"""Compare rendered facts from the same disposable prepared fixture inputs."""
import hashlib
import json
from pathlib import Path

from common import BASE, load_source, write_json

source = load_source()
result_paths = [BASE / path / 'semantic-outputs.json' for path in ('before-final', 'after-final')]
before, after = (json.loads(path.read_text()) for path in result_paths)
assert before.keys() == after.keys()
for family in before:
    assert before[family] == after[family], f'Rendered evidence changed for {family}'

assert before['covered_chain']['state'] == 'covered'
assert len(before['covered_chain']['moves']) == 2
assert before['conditional_chain']['state'] == 'conditional'
assert any('on injured reserve' in text for text in before['conditional_chain']['qualification'])
assert before['shortfall']['state'] == 'shortfall'
assert '0 / 1,000' in before['add_drop'] and 'All starting slots covered' in before['add_drop']
assert 'No completed roster move verified' in before['franchise_activity']
assert 'Playoff race' in before['season_playoffs_and_coverage']
assert 'Source' in before['depth'] or 'sources' in before['depth']
assert '2027' in before['draft_capital']

write_json(BASE / 'my-team-parity.json', {
    'source': source, 'passed': True, 'matched_prepared_families': sorted(before),
    'source_time': (BASE / 'fixture-time.txt').read_text().strip(),
    'scope': 'Rendered Chromium on disposable, matching prepared fixture inputs. Read-only application paths.',
    'normalization': 'Relocated roster navigation, layout whitespace, relative elapsed display and real run-clock timestamps are normalized. The new rendered confirmed kickoff label is checked by the browser suite. Stable IDs, moves, availability states and reason text are compared.',
    'originals': [{'path': str(path.relative_to(BASE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                  for path in result_paths],
})
