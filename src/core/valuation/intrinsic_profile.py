"""Independent, horizon-explicit intrinsic evidence without false price precision.

Observed quality, weekly expectation and longevity are not interchangeable units.
No standalone long-term scalar is published until its utility mapping is validated.
"""
from .forward_evidence import ForwardEvidence, assess_forward_context
from .player_methodology import IntrinsicAssessment


PROFILE_VERSION = 'intrinsic-evidence-profile-1'


def build_intrinsic_profile(quality: IntrinsicAssessment, forward: ForwardEvidence, *,
                            player_id: str, season: int, week: int, as_of: str) -> dict:
    current = assess_forward_context(forward, player_id=player_id, season=season, week=week, as_of=as_of)
    components = {item.name: item for item in quality.components}
    production = components.get('reference_production')
    usage = components.get('supporting_usage')
    longevity = components.get('position_lifecycle')
    return {'player_id': player_id, 'method_version': PROFILE_VERSION,
        'historical_method_version': quality.method_version,
        'demonstrated_quality': {'score': production.score if production else None,
            'scale': '0–100 position-reference production quality', 'seasons': quality.seasons,
            'sample_confidence': quality.confidence, 'effective_games': quality.effective_games},
        'latest_observed_usage': {'score': usage.score if usage else None, 'season': quality.usage_season,
            'limitation': 'Observed role, not a current share or persistence probability.'},
        'current_opportunity': {key: current[key] for key in ('current_team', 'depth_order', 'availability')},
        'current_availability': {key: current[key] for key in ('current_status', 'injury_designation')},
        'near_term_expectation': {'points': current['weekly_reference_projection'],
            'season': season, 'week': week, 'state': current['projection_state'], 'horizon': 'one_week'},
        'longevity_context': {'score': longevity.score if longevity else None,
            'limitation': 'Position-specific age context, not a career length or points forecast.'},
        'intrinsic_value': None, 'intrinsic_tier': None,
        'presentation': 'evidence_profile_not_long_term_price',
        'reason_codes': tuple(dict.fromkeys((*current['reason_codes'], 'SCALAR_UTILITY_MAPPING_NOT_VALIDATED')))}
