"""Bounded read-only source panel; not a claim of deployed candidate acceptance."""
import argparse
import asyncio
import json
import tempfile
from time import perf_counter
from pathlib import Path
from copy import deepcopy

import httpx

from src.core.data_platform.provider_activation import refresh_public_market
from src.core.data_platform.pick_quotes import canonical_pick_market
from src.core.valuation.normalization import prepare_market_normalization


async def main(league_ids, output_path=None):
    from src.core.history_context.metadata import MinimalMetadataStore
    from src.core.intelligence.pick_context import prepare_pick_context, pick_portfolio
    started = perf_counter()
    reports = []
    contexts = []
    async with httpx.AsyncClient(timeout=30) as client:
        market = await refresh_public_market(client)
        prepare_market_normalization(market)
        for league_id in league_ids:
            async def read(suffix):
                response = await client.get(f'https://api.sleeper.app/v1/league/{league_id}{suffix}')
                response.raise_for_status()
                return response.json()
            league, rosters, transfers = await asyncio.gather(read(''), read('/rosters'), read('/traded_picks'))
            season = int(league['season'])
            rounds = int(league['settings']['draft_rounds'])
            ids = {int(r['roster_id']) for r in rosters}
            years = {season + i for i in (1, 2, 3)} | {int(p['season']) for p in transfers if int(p['season']) > season}
            owners = {}
            conflicts = 0
            for p in transfers:
                key = (int(p['season']), int(p['round']), int(p['roster_id']))
                if key in owners and owners[key] != int(p['owner_id']):
                    conflicts += 1
                owners[key] = int(p['owner_id'])
            rows = []
            for year in sorted(years):
                for rnd in range(1, rounds + 1):
                    for original in sorted(ids):
                        owner = owners.get((year, rnd, original), original)
                        pick = dict(year=year, round=rnd, original_roster_id=original, current_owner_id=owner)
                        evidence = canonical_pick_market(pick, market)
                        quote = evidence.get('quote') or {}
                        rows.append({**pick, 'range': 'UNKNOWN', 'range_confidence': 'unavailable',
                                     'quote_type': quote.get('pick_type'), 'provider': quote.get('provider'),
                                     'price': evidence['normalized_market_price'], 'availability': evidence['availability']})
            data = {'league': league, 'teams': [{'roster_id': roster} for roster in sorted(ids)],
                    'pick_ledger': rows, 'market_data': market}
            # Real source identities, active synchronization preparation and
            # consumer portfolio path; temporary history only for this proof.
            with tempfile.TemporaryDirectory() as directory:
                store = MinimalMetadataStore(Path(directory)/'metadata.sqlite3')
                preparation = prepare_pick_context(data, store, observed_at='diagnostic')
                replay = prepare_pick_context(data, store, observed_at='replay')
            for row in data['pick_ledger']:
                evidence = canonical_pick_market(row, market)
                quote = evidence.get('quote') or {}
                row.update(range=row['projected_range'], range_confidence=row['projected_range_confidence'],
                           quote_type=quote.get('pick_type'), provider=quote.get('provider'),
                           price=evidence['normalized_market_price'], availability=evidence['availability'])
            rows = data['pick_ledger']
            portfolios = {str(team['roster_id']): pick_portfolio(team['picks_owned'], league_id=league_id,
                            generation=preparation['method']) for team in data['teams']}
            contexts.append(deepcopy(data))
            samples = {}
            for row in rows:
                key = (row['year'], row['round'], row['original_roster_id'] != row['current_owner_id'])
                samples.setdefault(key, row)
            report = {'league_id': league_id, 'source_season': season,
                              'scope': 'real source through candidate preparation; prior production ownership proof retained',
                              'count': len(rows), 'rounds': rounds,
                              'playoff_teams': league['settings'].get('playoff_teams'),
                              'playoff_start': league['settings'].get('playoff_week_start'),
                              'ownership_conflicts': conflicts,
                              'unknown_owners': sum(r['current_owner_id'] not in ids for r in rows),
                              'traded_count': sum(r['current_owner_id'] != r['original_roster_id'] for r in rows),
                              'priced_count': sum(r['price'] is not None for r in rows),
                              'samples': list(samples.values()), 'portfolio_context': portfolios,
                              'history_first_writes': preparation['semantic_history_writes'],
                              'history_unchanged_replay_writes': replay['semantic_history_writes']}
            reports.append(report)
            print(json.dumps(report))
    # Exercise the same preparation and metadata instance across A -> B -> A.
    # This tests preparation isolation, not authenticated session switching.
    signatures = []
    with tempfile.TemporaryDirectory() as directory:
        store = MinimalMetadataStore(Path(directory)/'parity.sqlite3')
        for supplied in (contexts[0], contexts[-1], contexts[0]):
            active = deepcopy(supplied)
            prepare_pick_context(active, store, observed_at='round-trip')
            league_id = str(active['league']['league_id'])
            signatures.append({'league': active['league'], 'picks': active['pick_ledger'],
                'portfolios': {str(t['roster_id']): pick_portfolio(t['picks_owned'], league_id=league_id,
                    generation='round-trip') for t in active['teams']}})
    assert signatures[0] == signatures[2]
    preparation_ms = round((perf_counter() - started) * 1000, 3)
    from tools.validation.pick_prepared_read_proof import authenticated_prepared_reads
    read_proof = authenticated_prepared_reads(contexts)
    print(json.dumps({'preparation_including_source_fetch_ms': preparation_ms, 'authenticated_reads': read_proof}))
    if output_path:
        Path(output_path).write_text(json.dumps({'panels': reports,
            'candidate_context_round_trip_equal': signatures[0] == signatures[2],
            'preparation_including_source_fetch_ms': preparation_ms,
            'authenticated_reads': read_proof,
            'parity_scope': 'active preparation with shared metadata; authenticated session/FOIS live parity remains pending'},
            sort_keys=True, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('league_ids', nargs='+')
    parser.add_argument('--output')
    args = parser.parse_args()
    asyncio.run(main(args.league_ids, args.output))
