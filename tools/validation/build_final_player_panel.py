"""Read-only retained-source panel through candidate evidence/Market contracts.

No network, production writes, hypothetical intrinsic prices or provider blending.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from src.core.valuation.forward_evidence import ForwardEvidence
from src.core.valuation.intrinsic_profile import build_intrinsic_profile
from src.core.valuation.player_methodology import ReferenceSeason, assess_intrinsic
from src.core.valuation.normalization import normalize_value, prepare_distribution
from src.core.valuation.consensus import build_canonical_consensus


def build(source, market, forward):
    history = {row['player_id']: row for row in source['cohort']}
    contexts = forward['players']
    if isinstance(contexts, list):
        contexts = {row['evidence']['player_id']: row for row in contexts}
    distribution = prepare_distribution('FantasyCalc', (row['value'] for row in market['players']))
    rows = []
    for quote in market['players']:
        key = quote['player_id']
        past = history.get(key, {})
        if past and past['position'] != quote['position']:
            raise ValueError(f'Identity position conflict: {key}')
        age = past.get('model_age', past.get('age', quote.get('age')))
        quality = assess_intrinsic(position=quote['position'], age=age, current_season=forward['season'],
            seasons=tuple(ReferenceSeason(**row) for row in past.get('season_summaries', ())))
        evidence = ForwardEvidence(**contexts[key]['evidence'])
        profile = build_intrinsic_profile(quality, evidence, player_id=key, season=forward['season'],
            week=forward['week'], as_of=forward['observed_at'])
        normalized = normalize_value('FantasyCalc', quote['value'], prepared_distribution=distribution,
            updated_at=None, provider_confidence=85)
        price = build_canonical_consensus((normalized,))
        rows.append({'player_id': key, 'name': quote['name'], 'position': quote['position'],
            'age': age, 'market': {**asdict(price), 'evidence_state': price.evidence_state,
                'raw_price': quote['value'], 'provider': 'FantasyCalc',
                'format': 'dynasty; requested 12 teams/numQbs=2/PPR1; TE premium default unknown',
                'rank': quote['market_rank'], 'rank_scope': 'provider published overall universe',
                'position_rank': None, 'tier': quote.get('market_tier'),
                'retrieved_at': market['retrieved_at'], 'source_updated_at': None},
            'profile': profile, 'league_adjusted_utility': None, 'league_adjusted_rank': None,
            'forward_generation': evidence.generation, 'limitations': list(quality.limitations)})
    return rows


def select(rows):
    chosen = {}
    def add(items):
        for row in items:
            if len(chosen) < 57:
                chosen[row['player_id']] = row
    add(row for row in rows if row['name'] in {'Jayden Daniels', 'Josh Allen', 'George Kittle', 'Jonnu Smith', 'Joe Mixon', 'Jordan Love'})
    ordered = sorted(rows, key=lambda row: (row['market']['rank'], row['player_id']))
    for position, count in (('QB', 15), ('RB', 8), ('WR', 8), ('TE', 8)):
        add([row for row in ordered if row['position'] == position][:count])
    add([row for row in ordered if not row['profile']['demonstrated_quality']['seasons']][:6])
    add([row for row in ordered if row['profile']['near_term_expectation']['points'] is None][:4])
    add(sorted(rows, key=lambda row: (row['profile']['demonstrated_quality']['sample_confidence'], row['market']['rank']))[:4])
    add(ordered)
    if len(chosen) != 57:
        raise ValueError('Exactly 57 diagnostic players required.')
    return list(chosen.values())


def render(rows, market, forward):
    def show(value):
        return 'Unavailable' if value is None else str(value)
    lines = ['# Batch 3 — final-semantics 57-player diagnostic', '',
        '**Retained-source candidate diagnostic; not released/current rankings or production acceptance.**', '',
        f"Market retrieved {market['retrieved_at']}; forward observed {forward['observed_at']}, season {forward['season']} week {forward['week']}.",
        'Historical production covers the retained seven-season source audit. The current candidate functions recompute profiles; rejected research scalar outputs are not consumed.',
        'All Market outputs below are SINGLE-PROVIDER MARKET: FantasyCalc, requested 12-team/2QB/PPR1; TE-premium default unknown. DynastyProcess is excluded from this result, not averaged or treated as missing corroboration.',
        'Provider rank/tier are source-defined, not intrinsic ranks. Global positional rank was not retained and is unavailable. League-adjusted utility/rank are unavailable. Weekly points use the fixed reference scoring, not a particular account.',
        'Raw price and DTOS normalized provider-specific index are separate units. Provider publication time is unknown; confidence uses unknown source freshness, not retrieval time as a fabricated publication date.', '',
        '| Player | Pos / age | Market raw / normalized / provider overall rank / tier | Market confidence | Quality / sample confidence | Latest usage / season | Weekly points / state | Longevity | Team / status / designation / depth |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in rows:
        p, m = row['profile'], row['market']
        q, usage, near = p['demonstrated_quality'], p['latest_observed_usage'], p['near_term_expectation']
        opportunity, status = p['current_opportunity'], p['current_availability']
        lines.append(f"| {row['name']} | {row['position']} / {show(row['age'])} | {m['raw_price']} / {m['market_consensus']} / {m['rank']} / {show(m['tier'])} | {m['confidence_score']} | {show(q['score'])} / {q['sample_confidence']} | {show(usage['score'])} / {show(usage['season'])} | {show(near['points'])} / {near['state']} | {show(p['longevity_context']['score'])} | {show(opportunity['current_team'])} / {show(status['current_status'])} / {show(status['injury_designation'])} / {show(opportunity['depth_order'])} |")
    lines += ['', '## Comparison with rejected diagnostics', '',
        'METHODOLOGY DEFECT corrected: the prior long-term intrinsic scalar/rank/tier is withdrawn for every player, not recalibrated to external consensus. Historical production quality and longevity remain separate profile dimensions. No bargain/overpay label is supported by unlike-unit comparisons.',
        'FORMAT MISMATCH: provider rank is not an intrinsic or league-adjusted rank. No cross-provider disagreement percentage is computed from unproven compatible scales.',
        'LOW CONFIDENCE: absent/short NFL samples limit evidence support, not quality. Missing projection remains missing; it never becomes zero dynasty utility.', '',
        'The JSON companion retains the complete evidence profiles, generations and limitations for individual outlier review. Panel generation alone does not certify that review or close release acceptance.']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.validation'))
    args = parser.parse_args()
    paths = [args.root / name for name in ('batch3-seven-season-calibration.json', 'batch3-panel-market.json', 'batch3-forward-context-v2.json')]
    source, market, forward = [json.loads(path.read_text(encoding='utf-8')) for path in paths]
    all_rows = build(source, market, forward)
    rows = select(all_rows)
    payload = {'status': 'diagnostic_review_required', 'players': rows,
        'source_checksums': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}}
    (args.root / 'batch3-final-player-panel.json').write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
    (args.root / 'batch3-final-player-panel.md').write_text(render(rows, market, forward), encoding='utf-8')
    print(json.dumps({'panel_players': len(rows), 'evaluated_players': len(all_rows), 'status': payload['status']}))
