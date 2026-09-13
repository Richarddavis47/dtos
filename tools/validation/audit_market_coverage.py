"""Bounded read-only coverage audit. Never outputs account/roster identities."""
from collections import Counter
from dataclasses import asdict
import json

from src.core.valuation.calibration import cached_market_results
from src.core.valuation.quote_eligibility import exclusion_reason


def audit(data):
    players = data.get('players') or {}
    market = data.get('market_data') or {}
    providers = market.get('providers') or {}
    relevant = {str(k) for k, p in players.items() if p.get('position') in {'QB', 'RB', 'WR', 'TE'}}
    results = cached_market_results(market, relevant)
    rostered = {str(p['id']) for t in data.get('teams', ()) for p in t.get('players', ())} & relevant
    starters = {str(p['id']) for t in data.get('teams', ()) for p in t.get('players', ()) if p.get('roster_slot') == 'Starter'} & relevant
    top = {k for k, row in providers.get('FantasyCalc', {}).items() if isinstance(row.get('rank'), (int, float)) and row['rank'] <= 50} & relevant
    groups = {'fantasy_relevant_retained': relevant, 'rostered': rostered, 'current_starters': starters,
              'bench_and_taxi': rostered - starters, 'top50_provider_rank': top,
              'rookies': {k for k in relevant if players[k].get('years_exp') == 0},
              'nfl_free_agents': {k for k in relevant if not players[k].get('team')}}
    coverage = {name: {'total': len(ids), 'available': sum(results[k].market_consensus is not None for k in ids)} for name, ids in groups.items()}
    reasons = {}
    for key in relevant:
        if results[key].market_consensus is not None:
            continue
        exclusions = [exclusion_reason(name, rows[key]) for name, rows in providers.items() if key in rows]
        reasons[key] = ('NO_CURRENT_PROVIDER_QUOTE' if not exclusions else
                        next((reason for reason in exclusions if reason), 'CANONICAL_MARKET_SELECTION_DEFECT_OR_FORMAT_CONFLICT'))
    names = {'Josh Allen', 'Jayden Daniels', 'Baker Mayfield', 'Bijan Robinson', 'Derrick Henry',
             "Ja'Marr Chase", 'DJ Moore', 'George Kittle', 'Jonnu Smith', 'Joe Mixon',
             'Tyreek Hill', 'Omarion Hampton', 'Jalen Hurts', 'Jordan Love'}
    sample = []
    for key in sorted(relevant):
        player = players[key]
        if player.get('full_name') not in names:
            continue
        quotes = {name: {field: row.get(field) for field in ('value', 'confidence', 'format', 'format_details',
                  'source_updated_at', 'retrieved_at', 'rank')} for name, rows in providers.items() if (row := rows.get(key))}
        sample.append({'player_id': key, 'name': player.get('full_name'), 'quotes': quotes,
                       'market': asdict(results[key]), 'evidence_state': results[key].evidence_state})
    return {'coverage': coverage, 'unavailable_reasons': dict(Counter(reasons.values())),
            'provider_mapped_counts': {name: len(rows) for name, rows in providers.items()},
            'sample': sample}


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--sample', action='store_true')
    args = parser.parse_args()
    if args.cache is None:
        from config import CACHE_FILE
        args.cache = CACHE_FILE
    result = audit(json.loads(args.cache.read_text(encoding='utf-8'))['data'])
    if not args.sample:
        result.pop('sample')
    print(json.dumps(result))
