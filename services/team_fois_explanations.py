"""Read-only adapters for accepted Team Strength and FOIS assessments."""
from src.core.explanations import (
    Availability as A, EvidenceContext, EvidenceItem, EvidenceKind as K,
    Explanation, Statement,
)
from services.trade_explanation import HORIZONS


def _item(ctx, key, label, value, unit, state=None, kind=K.DERIVED):
    return EvidenceItem(key, label, kind, ctx, key, unit,
                        state or (A.UNAVAILABLE if value is None else A.AVAILABLE),
                        None if value is None else str(value))


def team_strength_explanation(profile: dict, *, league_id: str, roster_id: int) -> Explanation:
    # The active caller passes the identity from the same admitted
    # TeamAssessment, never an independently selected team or user parameter.
    from src.core.intelligence.team_strength import METHOD_VERSION
    ctx = EvidenceContext('team_strength', f'roster:{roster_id}', profile['generation'], METHOD_VERSION, league_id)
    evidence, limits = [], []
    for key, label in HORIZONS.items():
        row = profile['horizons'][key]
        evidence.append(_item(ctx, key, f'{label} complete optimal-lineup total', row['total'], 'fantasy points'))
        for field, title in (('weeks_requested', 'requested weeks'), ('weeks_supported', 'supported weeks')):
            value = None if row.get(field) is None else ', '.join(map(str, row[field])) or 'none'
            evidence.append(_item(ctx, f'{key}.{field}', f'{label} {title}', value, 'week identities'))
        if row.get('availability') == 'partial':
            limits.append(Statement('INCOMPLETE_WEEKLY_LINEUPS', f'{label} is incomplete; the supported subtotal is not the full horizon.', (key,)))
            evidence.append(_item(ctx, f'{key}.subtotal', f'{label} supported subtotal only',
                                  row.get('supported_week_subtotal'), 'fantasy points',
                                  A.PARTIAL if row.get('supported_week_subtotal') is not None else A.UNAVAILABLE))
    for week, row in sorted(profile.get('weekly', {}).items(), key=lambda item: int(item[0])):
        evidence.append(_item(ctx, f'depth.{week}', f'Week {week} supported reserve slots',
                              (row.get('reserve_capacity') or {}).get('supported_slots'), 'lineup slots'))
        bye = row.get('known_bye_player_ids') if row.get('bye_evidence_availability') == 'supported' else None
        evidence.append(_item(ctx, f'bye.{week}', f'Week {week} known NFL-bye players',
                              None if bye is None else ', '.join(map(str, bye)) or 'none', 'player identities', kind=K.SOURCE))
    return Explanation('Team Strength explained', league_id, (ctx,), tuple(evidence),
        Statement('WEEKLY_OPTIMAL_CONTEXT', 'Separate horizons describe supported optimal lineups, not submitted starters.', ('current_week',)),
        limitations=tuple(limits), advanced=(Statement('PLAYOFF_WINDOW_SCOPE',
            'Playoff-window strength is opponent-independent and does not establish qualification or a locked opponent.', ('playoff_window',)),))


def fois_explanation(score, *, league_id: str) -> Explanation:
    if score.league_id != league_id:
        raise ValueError('FOIS explanation league mismatch')
    ctx = EvidenceContext('fois', f'franchise:{score.franchise_id}/tenure:{score.tenure_id or score.owner_id}',
                          score.score_key, score.model_version, league_id)
    evidence = [_item(ctx, 'overall', 'Overall FOIS', score.overall_score, 'FOIS score'),
                _item(ctx, 'confidence', 'Evidence confidence, not manager quality', score.confidence, 'evidence support'),
                _item(ctx, 'coverage', 'Evidence coverage', score.completeness, 'coverage'),
                _item(ctx, 'tenure', 'Assessed manager tenure', score.tenure_id or score.owner_id, 'tenure identity')]
    limits = []
    for category in score.category_scores:
        key = category.category_key
        evidence.append(_item(ctx, key, category.category_name, category.normalized_score, 'category score'))
        if category.normalized_score is None:
            limits.append(Statement('CATEGORY_EVIDENCE_INSUFFICIENT',
                f'{category.category_name}: insufficient evidence for a grade, not poor performance.', (key,)))
        for dimension in ('process', 'outcome'):
            row = (category.details or {}).get(dimension) or {}
            if row:
                evidence.append(_item(ctx, f'{key}.{dimension}', f'{category.category_name} · {dimension} magnitude',
                                      row.get('mean_magnitude'), 'accepted assessment magnitude'))
                evidence.append(_item(ctx, f'{key}.{dimension}.sample', f'{category.category_name} · {dimension} supported sample',
                                      row.get('supported_magnitudes'), 'decisions'))
                for field, label in (('confidence_distribution', 'evidence confidence'),
                                     ('classification_distribution', 'accepted conclusions'),
                                     ('limitations', 'evidence limitations')):
                    values = row.get(field) or {}
                    if values:
                        evidence.append(_item(ctx, f'{key}.{dimension}.{field}',
                            f'{category.category_name} · {dimension} {label}',
                            '; '.join(f'{name}: {count}' for name, count in sorted(values.items())),
                            'retained classifications and counts'))
    return Explanation('FOIS evidence explained', league_id, (ctx,), tuple(evidence),
        Statement('CANONICAL_OVERALL_FOIS',
                  'Overall FOIS is unavailable from the currently supported categories.' if score.overall_score is None
                  else f'Overall FOIS: {score.overall_score} · {score.overall_letter_grade or "Grade unavailable"}', ('overall',)),
        confidence=(Statement('EVIDENCE_SUPPORT', 'Confidence describes evidence support, not outcome probability or manager quality.', ('confidence',)),),
        limitations=tuple(limits), advanced=(Statement('TENURE_SCOPE',
            'This assessment is manager-tenure evidence. Franchise history remains separate; Results is only one category.', ('tenure',)),))
