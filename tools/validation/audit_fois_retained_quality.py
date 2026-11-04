"""Read-only quality diagnostic from retained sanitized panel, not a new export.

Only Results magnitudes survived that export's cleanup. Coverage is reproduced
alongside Results, never reverse-engineered into process quality.
"""
import json
from pathlib import Path

from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult


def panel(path):
    retained = json.loads(Path(path).read_text(encoding='utf-8'))
    output = {}
    for roster, manager in retained['managers'].items():
        owners = set(manager['owner_by_season'].values())
        if len(owners) != 1:
            raise ValueError('Split manager tenures before scoring Results')
        facts = FOISFacts('1313066632158924800', roster, next(iter(owners)),
                          tuple(SeasonResult(**s) for s in manager['results_by_season']),
                          expected_seasons=5)
        score = FOISEngine().evaluate(facts)
        result = next(c for c in score.category_scores if c.category_key == 'results')
        output[roster] = dict(
            results_score=result.normalized_score, results_grade=result.letter_grade,
            results_confidence=result.confidence, results_completeness=result.completeness,
            strengths=result.strengths, improvement_areas=result.weaknesses,
            decision_coverage=manager['categories'],
            roster_reference_coverage=manager['historical_roster_context'],
            decision_quality=None,
            decision_quality_reason='ASSESSMENT_MAGNITUDES_NOT_RETAINED_IN_COVERAGE_EXPORT',
            overall=None, overall_reason='NO_RECONSTRUCTIBLE_MULTI_CATEGORY_QUALITY',
        )
    return output


if __name__ == '__main__':
    print(json.dumps(panel('docs/BATCH4_PRODUCTION_EQUIVALENT_COVERAGE.json'), sort_keys=True))
