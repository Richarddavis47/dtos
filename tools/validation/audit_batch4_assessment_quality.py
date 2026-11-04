"""Bounded quality panel from actual derived assessments, never coverage scores.

No database access, source payload copying, or production writes. Ordinal trade
conclusions remain ordinal: the median is not converted to an academic grade.
Waiver exchange direction is not promoted to overall acquisition quality.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

from src.core.fois.configuration import DEFAULT_FOIS_CONFIGURATION
from src.core.fois.facts import FOISFacts, SeasonResult
from src.core.fois.results import ResultsScorer
from src.core.historical_transaction_intelligence.models import ProcessClassification


TRADE_ORDER = tuple(item.value for item in (
    ProcessClassification.POOR, ProcessClassification.QUESTIONABLE,
    ProcessClassification.DEFENSIBLE, ProcessClassification.SOUND,
    ProcessClassification.STRONG))


def summarize(records, side):
    """Equal-decision ordinal summary; no partial/default or impact imputation."""
    confidence, limitations, dimensions = Counter(), Counter(), {}
    conclusions, horizons = [], []
    supported_confidence = Counter()
    seen = set()
    for record in records:
        identity = tuple(record.get(k) for k in (
            'league_id', 'franchise_id', 'owner_id', 'season', 'category',
            'decision_id', 'selection'))
        if identity in seen:
            raise ValueError('Duplicate decision in quality panel')
        seen.add(identity)
        assessment = record[side]
        confidence[str(assessment.get('confidence'))] += 1
        limitations.update(assessment.get('limitations') or [])
        classification = assessment.get('classification')
        if (assessment.get('quality') is not None
                and classification in TRADE_ORDER and side == 'process'):
            # Only the evaluator's supported conclusion participates. Partial
            # descriptions with no magnitude cannot acquire a default score.
            conclusions.append(classification)
            supported_confidence[str(assessment.get('confidence'))] += 1
        for dimension in assessment.get('dimensions') or []:
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
    ordered = sorted(conclusions, key=TRADE_ORDER.index)
    minimum = DEFAULT_FOIS_CONFIGURATION.minimum_sample_sizes['trades']
    center = None
    if len(ordered) >= minimum:
        # Even samples retain both central labels rather than inventing an
        # interpolated continuous magnitude between ordinal classifications.
        center = list(dict.fromkeys((ordered[(len(ordered)-1)//2], ordered[len(ordered)//2])))
    return {
        'activity': len(records), 'supported_process_conclusions': len(ordered),
        'process_conclusion_distribution': dict(Counter(conclusions)),
        'central_supported_process_conclusion': center,
        'minimum_trade_sample': minimum,
        'confidence_distribution': dict(confidence),
        'supported_conclusion_confidence': dict(supported_confidence),
        'limitations': dict(limitations),
        'dimension_distributions': {k: dict(v) for k, v in dimensions.items()},
        'outcome_horizon_days': {'minimum': min(horizons), 'maximum': max(horizons)} if horizons else None,
        'grade': None,
        'scope': 'supported dimensions only; no inferred full-category letter grade',
    }


def panel(source):
    output = {}
    league = source['provenance']['league']
    for franchise, manager in source['managers'].items():
        owners = set(manager['owner_by_season'].values())
        if len(owners) != 1:
            raise ValueError('Split GM tenures before quality aggregation')
        owner = next(iter(owners))
        categories = {}
        for category, evidence in manager['categories'].items():
            records = evidence['derived_assessments']
            for record in records:
                if (record['league_id'] != league or str(record['franchise_id']) != str(franchise)
                        or record['owner_id'] != owner):
                    raise ValueError('Assessment league/franchise/GM mismatch')
            categories[category] = {side: summarize(records, side) for side in ('process', 'outcome')}
            if category == 'waivers':
                categories[category]['faab'] = {k: v for k, v in evidence.items() if 'faab' in k}
        facts = FOISFacts(league, franchise, owner,
                          tuple(SeasonResult(**s) for s in manager['results_by_season']), expected_seasons=5)
        result = ResultsScorer(DEFAULT_FOIS_CONFIGURATION).score(facts)
        output[franchise] = {
            'owner_id': owner,
            'results': {'score': result.normalized_score, 'grade': result.letter_grade,
                        'confidence': result.confidence, 'strengths': result.strengths,
                        'improvement_areas': result.weaknesses},
            'categories': categories,
            'roster': {'coverage': manager['historical_roster_context'], 'quality': None,
                       'reason': 'REFERENCES_ESTABLISH_CONTEXT_NOT_ROSTER_QUALITY'},
            'overall': None,
            'overall_reason': 'SCOPED_DECISION_CONCLUSIONS_DO_NOT_ESTABLISH_COMPLETE_CATEGORY_QUALITY',
        }
    return output


def main():
    source_path = Path('.validation/batch4-assessment-transfer/assessment-panel.json')
    raw = source_path.read_bytes()
    source = json.loads(raw)
    result = {'source_report_sha256': hashlib.sha256(raw).hexdigest(),
              'checkpoint_generation': source['checkpoint_generation'],
              'method': 'batch4-supported-ordinal-diagnostic-1', 'managers': panel(source)}
    target = Path('docs/BATCH4_MULTI_CATEGORY_QUALITY_PANEL.json')
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'{len(result["managers"])} manager quality profiles: {target}')


if __name__ == '__main__':
    main()
