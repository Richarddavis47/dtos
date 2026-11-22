"""Run the released rendered controls with extra native-shaped fixture inputs."""
from pathlib import Path
from types import ModuleType
import json
import sys
import unittest

sys.path.insert(0, '/app')
from src.core.trade_intelligence.roster_space import _ir_designation

raw = json.loads(Path('/evidence/native-catalog-receipt.json').read_text())
draft_row = json.loads(Path('/evidence/historic-draft-native-excerpt.json').read_text())[0]
league = dict(league_id='league-1', season='2026')
for label, row, pid, expected in (
    ('current IR designation', raw['native_excerpts']['2133'], '2133', 'ir'),
    ('current Out designation', raw['native_excerpts']['5850'], '5850', 'out'),
    ('historical draft pair, applied as a hypothetical input', draft_row['metadata'], '2391', None),
    ('short IR alias and Out', dict(player_id='1-ir', status='IR', injury_status='Out'), '1-ir', None),
    ('inverse pair', dict(player_id='1-ir', status='Out', injury_status='IR'), '1-ir', None),
):
    result = _ir_designation(row, pid, league)
    print(json.dumps(dict(test=label,status=row['status'],injury_status=row['injury_status'],result=result,expected=expected)))
    assert result == expected

path = Path('/app/tests/test_bye_pickups.py')
source = path.read_text()
match = "            ('conflicting', 1, 'IR', 'Out', 0, timedelta(), 'could not confirm the Sleeper status for Example IR 1'),"
assert source.count(match) == 1
source = source.replace(match, '\n'.join((
    match,
    match.replace("'conflicting'", "'documented-pair'").replace("'IR', 'Out'", "'Injured Reserve', 'Out'"),
    match.replace("'conflicting'", "'inverse-pair'").replace("'IR', 'Out'", "'Out', 'IR'"),
)))
fixture = ModuleType('combined_ir_replay')
exec(compile(source, str(path), 'exec'), fixture.__dict__)
suite = unittest.TestSuite([fixture.ByePickupTests('test_ir_blockers_and_active_space_on_phone')])
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
