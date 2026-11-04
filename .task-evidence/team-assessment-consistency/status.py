from pathlib import Path
from collections import Counter
import json
b=Path('/workspace/team-assessment-consistency/canonical')
p=b/'tests.jsonl'
if p.exists():
 r=[json.loads(x) for x in p.read_text().splitlines()];print(dict(Counter(x['event'] for x in r)));print(r[-1]['test'])
p=b/'result.json'
if p.exists():print(p.read_text()[:1000])
