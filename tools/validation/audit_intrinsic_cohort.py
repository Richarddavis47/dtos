"""Offline calibration diagnostics over retained public-source season summaries.

No network, provider calls, production writes or published player rankings.
"""
import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
from statistics import median, quantiles

from src.core.valuation.intrinsic_tiers import intrinsic_tier
from src.core.valuation.player_methodology import CURVES, ReferenceSeason, assess_intrinsic


def evaluate_cohort(source):
    season = int(source['as_of'][:4])
    evaluated = []
    for row in source['cohort']:
        summaries = tuple(ReferenceSeason(**item) for item in row['season_summaries'])
        age = row.get('model_age', row['age'])
        def assess(evidence=summaries, model_age=age):
            return assess_intrinsic(position=row['position'], age=model_age,
                current_season=season, seasons=evidence)
        baseline = assess()
        if baseline.value is None:
            continue
        short = assess(tuple(replace(item, games=7) for item in summaries))
        long = assess(tuple(replace(item, games=17) for item in summaries))
        if short.value != long.value or short.confidence > long.confidence:
            raise AssertionError('Sample confidence contaminated measured quality.')
        up = assess(tuple(replace(item, ppg=item.ppg * 1.1 if item.ppg is not None else None) for item in summaries))
        down = assess(tuple(replace(item, ppg=item.ppg * .9 if item.ppg is not None else None) for item in summaries))
        # Negative fantasy scores approach zero when multiplied by .9; only
        # nonnegative windows support this particular directional assertion.
        if all(item.ppg is None or item.ppg >= 0 for item in summaries):
            if not down.value <= baseline.value <= up.value:
                raise AssertionError('Production response is not monotonic.')
        latest = max((item for item in summaries if item.ppg is not None and item.games), key=lambda item: item.season)
        latest_only = assess((latest,))
        evaluated.append({'position': row['position'], 'value': baseline.value,
            'tier': intrinsic_tier(baseline.value).number, 'confidence': baseline.confidence,
            'assigned_team': bool(row.get('nfl_team')), 'partial_latest': latest.games < 8,
            'older': age is not None and age > CURVES[row['position']].longevity_reference,
            'production_up_delta': up.value - baseline.value,
            'production_down_delta': baseline.value - down.value,
            'latest_only_delta': latest_only.value - baseline.value,
            'age_year_delta': assess(model_age=age + 1).value - baseline.value if age is not None else None,
            'prior_method_delta': baseline.value - row['assessment']['value']})
    def summarize(rows):
        values = sorted(item['value'] for item in rows)
        return {'count': len(rows), 'range': [values[0], values[-1]] if values else [],
            'quartiles': quantiles(values) if len(values) > 1 else [],
            'tier_counts': dict(sorted(Counter(item['tier'] for item in rows).items())),
            'confidence_median': median(item['confidence'] for item in rows) if rows else None,
            'max_production_10pct_response': max((max(abs(item['production_up_delta']), abs(item['production_down_delta'])) for item in rows), default=0),
            'max_latest_only_change': max((abs(item['latest_only_delta']) for item in rows), default=0),
            'max_one_year_age_response': max((abs(item['age_year_delta']) for item in rows if item['age_year_delta'] is not None), default=0)}
    return {'status': 'diagnostic_not_acceptance', 'sample_quality_independence': 'PASS',
        'source_as_of': source['as_of'], 'source_seasons': source['production_seasons'],
        'all_historical': summarize(evaluated),
        'by_position': {p: summarize([r for r in evaluated if r['position'] == p]) for p in CURVES},
        'team_assigned_by_position': {p: summarize([r for r in evaluated if r['position'] == p and r['assigned_team']]) for p in CURVES},
        'partial_latest': summarize([r for r in evaluated if r['partial_latest']]),
        'older_productive': summarize([r for r in evaluated if r['older'] and r['value'] >= 500]),
        'maximum_prior_method_difference_including_age_rounding': max(abs(r['prior_method_delta']) for r in evaluated),
        'limitations': ['Candidate bands are not yet accepted decision cliffs.',
            'Team assignment is an explicit diagnostic subset, not proof of active dynasty eligibility.',
            'Older source artifact rounded age to two decimals; replay may differ by one point.',
            'No rookie NFL performance is fabricated; missing-evidence rookies require separate availability tests.',
            'Superflex is league utility, not an intrinsic cohort input.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate_cohort(json.loads(args.source.read_text(encoding='utf-8'))), sort_keys=True))
