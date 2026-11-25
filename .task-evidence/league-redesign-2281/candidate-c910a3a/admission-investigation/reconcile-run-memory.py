"""Compare aligned first-deferral test evidence from preserved exact-source runs."""
import bisect
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sys
import zipfile

root = Path(__file__).resolve().parent
source = json.loads((root / 'source.json').read_text())
runs = [
    ('local attempt 1', root / 'prior-attempts/c910a3a-local-gate-attempt1/local-canonical-complete'),
    ('local attempt 2', root / 'prior-attempts/c910a3a-local-gate-attempt2/local-canonical'),
    ('hosted attempt 2', root / 'hosted-originals/canonical-original.zip'),
]
if '--complete' in sys.argv:
    runs.append(('local disk-backed', root / 'local-canonical'))

test_name = 'test_full_rosters_unseeded_strategies_and_qualified_zero_states_at_four_sizes'
fields = ('time', 'anon', 'file', 'shmem', 'inactive_file', 'active_file', 'kernel')
sequence = None
records = []
for label, path in runs:
    if path.suffix == '.zip':
        with zipfile.ZipFile(path) as archive:
            contents = {name: archive.read(name).decode() for name in ('result.json', 'memory.jsonl', 'tests.jsonl', 'canonical.log')}
    else:
        contents = {name: (path / name).read_text() for name in ('result.json', 'memory.jsonl', 'tests.jsonl', 'canonical.log')}
    result = json.loads(contents['result.json'])
    assert result['head'] == source['candidate'] and result['tree'] == source['tree']
    tests = [json.loads(row) for row in contents['tests.jsonl'].splitlines()]
    starts = [row for row in tests if row['event'] == 'start']
    order = [row['test'] for row in starts]
    if sequence is None:
        sequence = order
    assert sequence == order and len(starts) == source['expected_test_count']
    i = next(i for i, row in enumerate(starts) if row['test'].endswith(test_name))
    start, next_start = starts[i]['time'], starts[i + 1]['time']
    memory = [json.loads(row) for row in contents['memory.jsonl'].splitlines()]
    timeline = [row['time'] for row in memory]
    window = memory[bisect.bisect_left(timeline, start):bisect.bisect_left(timeline, next_start)]
    starts_at = [entry['time'] for entry in starts]
    largest_sample = max(window, key=lambda row: row['memory']['cgroup_current_bytes'])
    largest_sample_bytes = {**{key: largest_sample.get(key) for key in fields},
                            'current': largest_sample['memory']['cgroup_current_bytes']}
    observations = []
    for line in contents['canonical.log'].splitlines():
        if '"admitted":false' not in line or '"event":"trade_admission"' not in line:
            continue
        row = json.loads(line[line.find('{'):])
        probe = row['diagnostic']['observation']
        if probe['reason'] != 'capacity':
            continue
        instant = datetime.fromisoformat(row['timestamp']).timestamp()
        index = bisect.bisect_left(timeline, instant)
        observations.append({'timestamp': row['timestamp'], 'test_in_progress': starts[bisect.bisect_right(starts_at, instant) - 1]['test'],
                             'admission': probe, 'recovery': row['diagnostic']['recovery'],
                             'nearby_memory': [{**{key: sample.get(key) for key in fields}, 'current': sample['memory']['cgroup_current_bytes']}
                                               for sample in memory[max(0, index - 1):index + 1]]})
    assert window
    records.append({'run': label, 'test_events': Counter(row['event'] for row in tests), 'run_passed': result['passed'], 'kernel_peak_bytes': result['kernel_peak'],
                    'report_at_test_start_bytes': window[0]['memory']['cgroup_current_bytes'],
                    'first_affected_test': starts[i]['test'], 'test_order_zero_based': i,
                    'first_affected_test_shmem_peak_bytes': max(row.get('shmem', 0) for row in window),
                    'first_affected_test_cgroup_peak_sample': largest_sample_bytes,
                    'run_max_sampled_active_file_bytes': max(row.get('active_file', 0) for row in memory),
                    'capacity_deferrals': observations})
record = {'source': source, 'same_discovery_start_order': True, 'memory_sample_units': 'bytes', 'records': records,
          'claim_scope': 'Nearest sampled counters are observational. Isolated temporary file accounting and the full recovered run address different questions.'}
(root / 'local-hosted-memory-comparison.json').write_text(json.dumps(record, indent=2) + '\n')
for row in records:
    print(row['run'], row['test_events'], 'peak', row['kernel_peak_bytes'], 'affected test shmem', row['first_affected_test_shmem_peak_bytes'],
          'capacity deferrals', len(row['capacity_deferrals']))
