"""Local-only candidate player panel; one approved public Market snapshot.

Never publish this diagnostic as current DTOS rankings or provider consensus.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

import httpx

from src.core.data_platform.provider_activation import FANTASYCALC_URL
from src.core.valuation.intrinsic_tiers import intrinsic_tier
from src.core.valuation.normalization import normalize_value, prepare_distribution
from src.core.valuation.player_methodology import ReferenceSeason, assess_intrinsic, METHOD_VERSION
from src.core.valuation.forward_evidence import ForwardEvidence
from src.core.valuation.intrinsic_profile import build_intrinsic_profile


def panel(source, market):
    distribution = prepare_distribution('FantasyCalc', [r['value'] for r in market['players']])
    evidence = {r['player_id']: r for r in source['cohort']}
    result = []
    for quote in market['players']:
        old = evidence.get(quote['player_id'])
        if old and old['position'] != quote['position']:
            raise ValueError('Exact player ID has conflicting positions; review identity before comparison.')
        samples = tuple(ReferenceSeason(**s) for s in old['season_summaries']) if old else ()
        age = old.get('model_age', old['age']) if old else quote.get('age')
        assessment = assess_intrinsic(position=quote['position'], age=age,
            current_season=int(source['as_of'][:4]), seasons=samples)
        normalized = normalize_value('FantasyCalc', quote['value'], prepared_distribution=distribution,
            updated_at=market['retrieved_at'], provider_confidence=85)
        components = {c.name: c.contribution for c in assessment.components}
        result.append({**quote, 'intrinsic': assessment.value,
            'intrinsic_tier': intrinsic_tier(assessment.value).number,
            'confidence': assessment.confidence, 'market_normalized': normalized.normalized_value,
            'components': components, 'season_evidence': [asdict(s) for s in samples],
            'age_used': age, 'projection_influence': 'None; no standardized long-horizon projection admitted',
            'limitations': list(assessment.limitations)})
    ranked = sorted([r for r in result if r['intrinsic'] is not None], key=lambda r: (-r['intrinsic'], r['player_id']))
    positions = {}
    for rank, row in enumerate(ranked, 1):
        positions[row['position']] = positions.get(row['position'], 0) + 1
        row['intrinsic_rank'] = rank
        row['intrinsic_position_rank'] = positions[row['position']]
    selected = []
    for position, count in (('QB', 15), ('RB', 8), ('WR', 8), ('TE', 8)):
        selected.extend([r for r in ranked if r['position'] == position][:count])
    selected.extend(sorted([r for r in result if r['intrinsic'] is None], key=lambda r: r['market_rank'])[:8])
    disagreements = sorted(ranked, key=lambda r: abs(r['intrinsic'] - r['market_normalized']), reverse=True)[:10]
    selected.extend(disagreements)
    rows = list({r['player_id']: r for r in selected}.values())
    return rows, len(ranked), disagreements


def render(rows, count, market, source):
    lines = ['# Batch 3 — actual candidate player outputs', '',
        '**Diagnostic only — not released. Scalars below are rejected candidate research, not accepted intrinsic prices. The horizon-explicit profile follows.**', '',
        f'Method: `{METHOD_VERSION}`. Production: 2019–2025; metadata boundary: {source["as_of"]}.',
        f'Market retrieved: {market["retrieved_at"]}. Source: {FANTASYCALC_URL}', '',
        f'Intrinsic ranks below cover only {count} scored players matched by exact Sleeper ID to this Market snapshot.',
        'They are not the full global player universe. Market ranks/tier are FantasyCalc’s own 12-team, 2-QB/PPR dynasty ranks/tier, NOT consensus.',
        'Intrinsic quality is league-neutral; no calibrated overall Superflex utility distribution is available yet. Comparing these ranks directly as one concept is a FORMAT MISMATCH.',
        'Intrinsic tier numbers use provisional independent bands; numbers do not imply equivalence to provider tiers.', '',
        '| Player | Pos | Intrinsic / cohort rank / positional rank / tier | Market normalized (raw) / rank / provider tier | Confidence | Production + usage + lifecycle contributions |',
        '| --- | --- | --- | --- | ---: | --- |']
    for row in rows:
        c = row['components']
        lines.append(f"| {row['name']} | {row['position']} | {row['intrinsic']} / {row.get('intrinsic_rank', '—')} / {row.get('intrinsic_position_rank', '—')} / {row['intrinsic_tier']} | {row['market_normalized']} ({row['value']}) / {row['market_rank']} / {row['market_tier']} | {row['confidence']} | " + ' + '.join(str(round(c.get(k, 0), 1)) if k in c else 'Unavailable' for k in ('reference_production', 'supporting_usage', 'position_lifecycle')) + ' |')
    lines += ['', '## Evidence and outlier review', '',
        'Projection contribution is absent for every row: a league-scored weekly forecast is not admitted as a global multi-year forecast. No prospect prior is invented.',
        'A missing row of NFL evidence requires coverage/lifecycle investigation; it is not automatically a data defect or a poor player.',
        'Large gaps are not automatically bargains: raw quality and a forward-looking, format-specific trading price are different concepts.', '']
    for row in rows:
        samples = row['season_evidence']
        evidence = '; '.join(f"{s['season']}: {s['games']}g, {s['ppg']:.2f} reference PPG, usage {s['usage']}" if s['ppg'] is not None else f"{s['season']}: scoring incomplete" for s in samples)
        classification = 'LOW CONFIDENCE' if row['confidence'] < 55 else (
            'METHODOLOGY DEFECT — historical quality alone does not establish current dynasty value'
            if abs(row['intrinsic'] - row['market_normalized']) > 300 else 'FORMAT MISMATCH / methodology review pending')
        lines += [f"### {row['name']}", f"Age used: {row['age_used']}. Classification: **{classification}**.",
            evidence or 'No matched scored NFL evidence; intrinsic unavailable.',
            'Reason: production quality uses position-weighted recent seasons; latest observed usage supports role; longevity is position-specific. Market prices additionally reflect format and forward expectations not represented by this evidence-only candidate.', '']
    lines += ['## Acceptance blockers', '',
        '- Tier and cross-position utility calibration remain provisional.',
        '- Major price/quality gaps require individual evidence review; none is automatically classified JUSTIFIED.',
        '- Missing-history player identity/lifecycle verification is required before treating them as rookies.',
        '- Current projection/role adapter and downstream reconciliation remain unfinished.',
        '- Do not release this candidate or start Batch 4.']
    return '\n'.join(lines) + '\n'


def render_forward(rows, report):
    contexts = {item['evidence']['player_id']: item for item in report['players']}
    lines = ['', '## Current forward evidence — separate from demonstrated quality', '',
        f"Observed {report['observed_at']}; Sleeper season {report['season']}, week {report['week']}.",
        'Fixed reference scoring, not account scoring. Status/depth are source metadata, not inferred playing probability.',
        'Evidence-profile presentation is selected: scalar dynasty utility is unavailable because its mapping is unvalidated, not because a precise multi-year forecast is required.', '',
        '| Player | Historical quality /100 | Historical confidence | Longevity context /100 | Team / status / designation | Depth | Weekly projection / state |',
        '| --- | ---: | ---: | ---: | --- | ---: | --- |']
    for row in rows:
        item = contexts[row['player_id']]
        evidence = ForwardEvidence(**item['evidence'])
        quality = assess_intrinsic(position=row['position'], age=row['age_used'], current_season=report['season'],
            seasons=tuple(ReferenceSeason(**sample) for sample in row['season_evidence']))
        profile = build_intrinsic_profile(quality, evidence, player_id=row['player_id'],
            season=report['season'], week=report['week'], as_of=report['observed_at'])
        near = profile['near_term_expectation']
        lines.append(f"| {row['name']} | {profile['demonstrated_quality']['score']} | {quality.confidence} | {profile['longevity_context']['score']} | {evidence.team} / {evidence.status} / {evidence.injury_designation} | {evidence.depth_order} | {near['points']} / {near['state']} |")
    lines += ['', 'Interpretation: Jonnu/Mixon-class gaps now have explicit current-role/projection evidence, but this does not prove a trade bargain/overpay.',
        'A questionable designation is not a recovery forecast. Missing team metadata alone is not retirement. Zero weekly projection is not zero career utility.',
        'A prospect can have supported weekly expectation with unavailable historical quality; neither field fills the other.']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2] / '.validation'
    cache = root / 'batch3-panel-market.json'
    if not cache.exists():
        response = httpx.get(FANTASYCALC_URL, timeout=40)
        response.raise_for_status()
        quotes = []
        for r in response.json():
            p = r.get('player') or {}
            if p.get('sleeperId') is None or p.get('position') not in {'QB', 'RB', 'WR', 'TE'}:
                continue
            quotes.append({'player_id': str(p['sleeperId']), 'name': p['name'], 'position': p['position'],
                'age': p.get('maybeAge'), 'value': r['value'], 'market_rank': r['overallRank'], 'market_tier': r.get('maybeTier')})
        cache.write_text(json.dumps({'retrieved_at': datetime.now(timezone.utc).isoformat(), 'players': quotes}), encoding='utf-8')
    market = json.loads(cache.read_text(encoding='utf-8'))
    source = json.loads(args.source.read_text(encoding='utf-8'))
    rows, count, gaps = panel(source, market)
    document = render(rows, count, market, source)
    forward = root / 'batch3-forward-context-v2.json'
    if forward.exists():
        document += render_forward(rows, json.loads(forward.read_text(encoding='utf-8')))
    (root / 'batch3-player-panel.md').write_text(document, encoding='utf-8')
    print(json.dumps({'matched_ranked': count, 'panel_players': len(rows), 'status': 'diagnostic_blockers_remain'}))
