"""Evidence-backed depth presentation, never a player-count quality score."""
from src.core.decision_engine.models.evaluation import Evaluation, EvaluationFactor, EvaluationHorizon


def evaluate_position_depth(profile, position, diagnostics=None):
    facts = ((diagnostics or {}).get('positions') or {}).get(position) or {}
    room = profile.position_rooms[position]
    return Evaluation(EvaluationHorizon.DEPTH, None, facts.get('classification', 'Uncertain'), 0,
        facts.get('interpretation', 'Compatible Sleeper legal-lineup replacement evidence is unavailable.'),
        (EvaluationFactor('Observed roster', str(room.total_players), 0,
                          'Player count is context, not usable depth or a quality score.', 'Sleeper roster'),
         EvaluationFactor('Injury / eligibility evidence', str(room.injured), 0,
                          'Known IR/taxi/out/bye restrictions are excluded; uncertain injury availability qualifies conclusions.', 'Sleeper status'),
         EvaluationFactor('Legal replacement evidence', str(facts.get('remove_one') or 'Unavailable'), 0,
                          'Complete legal assignments; removal costs and disjoint reserves are not summed.', 'Canonical Sleeper projections')),
        tuple((diagnostics or {}).get('limitations') or ('Missing projections are unavailable, not zero.',)))


def evaluate_depth(profile, diagnostics=None):
    positions = {position: evaluate_position_depth(profile, position, diagnostics)
                 for position in ('QB', 'RB', 'WR', 'TE')}
    return Evaluation(EvaluationHorizon.DEPTH, None, 'Distinct evidence dimensions', 0,
        'Legal-lineup needs, replacement protection and conditional expendability are separate; no count-derived depth grade.',
        tuple(EvaluationFactor(pos, row.grade, 0, row.summary, 'Canonical roster diagnostics')
              for pos, row in positions.items()),
        tuple((diagnostics or {}).get('limitations') or ())), positions
