"""Private bounded real-source proactive search proof, no production writes."""
import cProfile
import hashlib
import json
import pstats
from time import perf_counter
from unittest.mock import patch

from services.trade_intelligence import (generate_trade_workflow, evaluate_trade_request, _trade_for_eligible,
    _proposal_payload, _SearchProjectionReader, _trade_projection_service)
from services.recommended_trade_search import construct
from src.core.intelligence import build_trade_evidence_context


def recommended_samples(data, workspace):
    before = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    assessments = []
    def capture(*args, **kwargs):
        result = evaluate_trade_request(*args, **kwargs)
        assessments.append(result)
        return result
    profiler = cProfile.Profile()
    with patch('services.trade_intelligence.evaluate_trade_request', side_effect=capture):
        profiler.enable()
        result = generate_trade_workflow(data, {'workflow': 'recommended', 'active_roster_id': workspace['active_roster_id']})
        profiler.disable()
    start = perf_counter()
    json.dumps(result, default=str)
    serialization = perf_counter() - start
    evidence = build_trade_evidence_context(data, (a for pool in workspace['pools'].values() for a in pool))
    reader = _SearchProjectionReader(_trade_projection_service(data))
    broader = []
    selected_partners = {t['partner_id'] for t in result['discovery']['theses']}
    omitted = result['discovery']['omitted_theses']
    # At most six theses: first cover counterparties absent from the normal
    # budget, then alternate supported theses. Never a league Cartesian search.
    recall_theses = sorted(omitted, key=lambda t: (t['partner_id'] in selected_partners,
                                                  omitted.index(t)))[:6]
    for thesis in recall_theses:
        for proposal in construct(workspace, thesis, set(), set()):
            row = evaluate_trade_request(data, _proposal_payload(proposal, 'recommended'), workspace=workspace,
                                         evidence_context=evidence, projection_reader=reader)
            broader.append({'family_id': thesis['family_id'], 'partner_id': thesis['partner_id'],
                            'result': row, 'qualifies': _trade_for_eligible(row['evaluation'])})
    assert hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest() == before
    entries = [{'file': filename.rsplit('\\', 1)[-1].rsplit('/', 1)[-1], 'function': function,
                'calls': calls, 'self_seconds': own, 'cumulative_seconds': cumulative}
               for (filename, _, function), (_, calls, own, cumulative, _) in pstats.Stats(profiler).stats.items()]
    entries.sort(key=lambda row: -row['cumulative_seconds'])
    return {'league_id': data['league']['league_id'], 'result': result, 'assessments': assessments,
            'broader_recall': broader, 'recall_theses': len(recall_theses),
            'recall_budget': 'six omitted supported theses, at most three packages each',
            'canonical_state_unchanged': True, 'profile': entries[:35],
            'serialization_seconds': serialization,
            'timing_scope': 'Local cProfile-instrumented search, not production latency; no cached assessments.',
            'scope': 'read-only public-source candidate, not authenticated production'}
