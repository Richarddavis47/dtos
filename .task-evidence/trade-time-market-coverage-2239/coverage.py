"""Bounded existing replay inventory; source observations are never fabricated."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib, json, sys
sys.path.insert(0, '/app')
from src.core.history_context.timestamps import canonical_transaction_timestamp

root = Path('/app/tests/fixtures')
files = ('trade_timeline_sources.json', 'trade_faab_source.json',
         'historical_archive_source.json', 'home_news_recent_trades.json')
rows, inputs = {}, []
for name in files:
    p = root/name
    data = json.loads(p.read_text())
    groups = data.get('leagues') or [data]
    count = 0
    for group in groups:
        league = group.get('league') or {}
        league_id = league.get('league_id') or group.get('league_id')
        if name == 'historical_archive_source.json':
            league_id = data['provenance']['url'].split('/league/')[1].split('/')[0]
        ts = group.get('transactions') or []
        if isinstance(ts, dict): ts = [r for batch in ts.values() for r in batch]
        for tx in ts:
            if tx.get('type') != 'trade' or tx.get('status') != 'complete': continue
            key = (str(league_id), str(tx['transaction_id']))
            stamp, provenance = canonical_transaction_timestamp(tx)
            prior = rows.get(key)
            if prior:
                assert prior['timestamp'] == stamp
                prior['input_files'].append(name)
                continue
            players = set((tx.get('adds') or {})) | set((tx.get('drops') or {}))
            picks = {(str(p.get('season')), p.get('round'), p.get('roster_id')) for p in tx.get('draft_picks') or []}
            rows[key] = dict(input_files=[name], timestamp=stamp,
                timestamp_field=provenance['field'], player_assets=len(players), exact_pick_assets=len(picks),
                pick_identity_complete=all(all(v is not None for v in p) for p in picks),
                faab_present=bool(tx.get('waiver_budget')),
                paired_retained_market_observations=None)
            count += 1
    inputs.append(dict(file=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size,
        provenance=data.get('provenance') or {'source':data.get('source'),'retrieved_at':data.get('retrieved_at')},
        newly_distinct_completed_trades=count,
        retained_market_population_supplied=False))
summary = dict(observed_at=datetime.now(timezone.utc).isoformat(),source='Existing retained Sleeper capture fixtures; no new source requests',
    inputs=inputs,distinct_completed_trades=len(rows),
    transaction_instants_known=sum(bool(r['timestamp']) for r in rows.values()),
    asset_appearances=sum(r['player_assets']+r['exact_pick_assets'] for r in rows.values()),
    seasons_by_transaction_utc=dict(Counter(r['timestamp'][:4] if r['timestamp'] else 'unknown' for r in rows.values())),
    exact_pick_appearances=sum(r['exact_pick_assets'] for r in rows.values()),
    faab_packages=sum(r['faab_present'] for r in rows.values()),
    supplied_real_market_observations=0,verified_real_quote_trade_overlap=0,
    real_trade_quote_coverage='UNKNOWN: none of these retained source captures supplies a Market population; no authorized production store read was available',
    production_missing_observations=None,
    warning='0 demonstrated overlaps is not a measured zero in production. Arkham has no completed trade in the retained timeline capture; this is not evidence it has no trades.',
    trades=list(rows.values()))
Path('/evidence/coverage.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('trades','inputs')},indent=2))
