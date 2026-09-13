"""Allowlisted derived assessment handoff; no canonical source payload copies."""
from collections import Counter
from statistics import mean
from src.core.fois.coverage import decision_evaluability
from src.core.historical_transaction_intelligence.models import HISTORICAL_TRANSACTION_METHOD_VERSION


DIMENSION_FIELDS = ('dimension', 'name', 'assessment', 'difference', 'change',
                    'scope', 'references', 'reference', 'baseline_reference',
                    'horizon_days', 'as_of', 'evidence_available')


def assessment_record(row, category, *, league_id, franchise_id):
    states = decision_evaluability(row, category)
    evaluation = row.get('decision_evaluation') or {}
    result = {
        'league_id': league_id, 'franchise_id': franchise_id,
        'owner_id': row.get('owner_id'), 'season': row.get('season'),
        'decision_id': row.get('transaction_id') or row.get('draft_id'),
        'selection': row.get('pick_number') if category == 'drafting' else None,
        'category': category, 'as_of': row.get('occurred_at'),
        'method': evaluation.get('method') or HISTORICAL_TRANSACTION_METHOD_VERSION,
        'history_generation': row.get('history_generation'),
        'market_generation': row.get('market_generation'),
    }
    for side in ('process', 'outcome'):
        scoped = evaluation.get(side) or {}
        dimensions = scoped.get('assessment') or []
        if category == 'trading' and side == 'process':
            dimensions = (row.get('process_evidence') or {}).get('historical_process_dimensions') or []
        result[side] = {
            'evaluability': states[side],
            'quality': scoped.get('quality') if evaluation else row.get(side + '_score'),
            'classification': row.get(side + '_classification') if not evaluation else None,
            'confidence': scoped.get('confidence', row.get(side + '_confidence')),
            'dimensions': [{key: d[key] for key in DIMENSION_FIELDS if key in d}
                           for d in dimensions if isinstance(d, dict)],
            'limitations': states['missing_' + side + '_requirements'],
        }
    return result


def assessment_summary(records):
    """Bounded active category evidence, without retaining decision payloads.

Numeric magnitudes and descriptive dimensions stay separate; neither coverage
nor an observed Market direction creates a missing quality magnitude.
"""
    result = {'method': 'fois-scoped-quality-1', 'activity': len(records)}
    for side in ('process', 'outcome'):
        values, confidence, supported_confidence = [], Counter(), Counter()
        classifications, limitations, dimensions = Counter(), Counter(), {}
        horizons = []
        for record in records:
            item = record[side]
            confidence[str(item.get('confidence'))] += 1
            limitations.update(item.get('limitations') or [])
            if item.get('quality') is not None:
                values.append(float(item['quality']))
                supported_confidence[str(item.get('confidence'))] += 1
                if item.get('classification'):
                    classifications[item['classification']] += 1
            for dimension in item.get('dimensions') or []:
                if dimension.get('evidence_available') is False:
                    continue
                name = dimension.get('dimension') or dimension.get('name')
                label = dimension.get('assessment')
                if name == 'later_observed_market_change':
                    change = dimension.get('change')
                    label = ('increased' if change > 0 else 'decreased' if change < 0
                             else 'unchanged') if change is not None else None
                    if dimension.get('horizon_days') is not None:
                        horizons.append(dimension['horizon_days'])
                if name and label:
                    dimensions.setdefault(name, Counter())[label] += 1
        result[side] = {
            'supported_magnitudes': len(values),
            'mean_magnitude': round(mean(values), 2) if values else None,
            'minimum_magnitude': min(values) if values else None,
            'maximum_magnitude': max(values) if values else None,
            'classification_distribution': dict(classifications),
            'confidence_distribution': dict(confidence),
            'supported_confidence_distribution': dict(supported_confidence),
            'limitations': dict(limitations),
            'dimensions': {key: dict(value) for key, value in dimensions.items()},
            'observation_horizon_days': {'minimum': min(horizons), 'maximum': max(horizons)} if horizons else None,
        }
    return result
