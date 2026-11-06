"""Declared high-cardinality sensitivity, no size matching or private data."""
import hashlib,json,sys
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0,'/app')
from src.core.data_platform.normalization import PlayerIdentityResolver
b=Path('/evidence');root=b/'fixture';payload=json.loads((root/'oneqb.json').read_text());data=payload['data']
for i,row in enumerate(data['players'].values()):
 row.update(birth_city=f'Unique fixture city {i}',college=f'Unique fixture university {i}',high_school=f'Unique fixture school {i}')
 row['birth_date']=f"{2026-int(row['age'])}-{1+(i//28)%12:02d}-{1+i%28:02d}"
resolver=PlayerIdentityResolver(data['players']);data['normalized_players']={pid:asdict(resolver.resolve(pid)) for pid in data['players']}
p=root/'oneqb-diverse.json';p.write_text(json.dumps(payload,separators=(',',':'),ensure_ascii=False));out=dict(scope='Synthetic sensitivity: same IDs, native scores, team/slot/scoring rules,991consumers; unique city/university/school fields and varied valid birth dates. Not private source cardinality. No file-size target.',bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_fixture='oneqb.json',players=len(data['players']),consumers=len(data['valuation_intelligence']['assets']))
(b/'diverse-fixture-metadata.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
