"""A realistic Unicode league label sensitivity, without file-size targeting."""
from pathlib import Path
import hashlib,json
b=Path('/evidence');p=b/'fixture'/'oneqb-unicode.json';x=json.loads((b/'fixture/oneqb.json').read_text());x['data']['league']['name']='Unicode fixture league 🏈';p.write_text(json.dumps(x,separators=(',',':'),ensure_ascii=False));out=dict(scope='One explicitly fictional Unicode league name; same complete structural cohort, IDs, source scores, scoring, slots and consumer disclosures. Not private Granite contents.',bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest());(b/'unicode-fixture-metadata.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
