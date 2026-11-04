"""Bounded public-source Shop acceptance; diagnostic reuse never changes product gates."""
from copy import deepcopy
import hashlib
import json
from unittest.mock import patch

from services.trade_intelligence import generate_trade_workflow, evaluate_trade_request, _trade_for_eligible


def shop_samples(data, workspace, *, performance_only=False):
    active = workspace['active_roster_id']
    pool = workspace['pools'][active]
    players = sorted((a for a in pool if a.kind == 'player' and a.trade_value is not None), key=lambda a: (-a.trade_value, a.asset_id))
    picks = [a for a in pool if a.kind == 'pick']
    targets = [('high_market', players[0]), ('middle_market', players[len(players)//2])]
    if picks:
        targets.append(('pick', picks[0]))
    if performance_only:
        targets = [('middle_market', players[len(players)//2])]
    before = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    memo = {}
    physical_calls = []
    def capture(source, payload, **kwargs):
        key = (payload['active_roster_id'], payload['partner_roster_id'],
               tuple(sorted(payload['assets_sent'])), tuple(sorted(payload['assets_received'])))
        if key not in memo:
            memo[key] = deepcopy(evaluate_trade_request(source, payload, **kwargs))
            physical_calls.append(key)
        return deepcopy(memo[key])
    rows = []
    with patch('services.trade_intelligence.evaluate_trade_request', side_effect=capture):
        for label, target in targets:
            start = len(physical_calls)
            payload = {'workflow': 'shop', 'active_roster_id': active, 'asset_id': target.asset_id}
            performance = None
            if performance_only:
                from tools.validation.batch5_shop_timing import measure, semantic, differences
                result, optimized_metrics = measure(lambda: generate_trade_workflow(data, payload))
                optimized_assessments = deepcopy(memo)
                normal_calls = len(physical_calls) - start
                memo.clear()
                reference_result, reference_metrics = measure(lambda: generate_trade_workflow(data, payload), reference=True)
                result_differences = differences(semantic(result), semantic(reference_result))
                assessment_differences = differences(semantic(list(optimized_assessments.values())), semantic(list(memo.values())))
                performance = {'optimized': optimized_metrics, 'pre_correction_reference': reference_metrics,
                               'same_evidence_result_equal': not result_differences, 'all_shared_assessments_equal': not assessment_differences,
                               'result_differences': result_differences, 'assessment_differences': assessment_differences,
                               'compared_assessments': len(memo), 'concurrent_searches': 1}
                memo.clear()
                memo.update(optimized_assessments)
            else:
                result = generate_trade_workflow(data, payload)
                normal_calls = len(physical_calls) - start
            comparisons = []
            # One representative preference panel, not five expensive searches
            # for every asset. Shared evaluations memoize exact identities only.
            if label == 'middle_market' and not performance_only:
                for pref in ('win_now', 'youth_rebuild', 'draft_capital', 'position_need'):
                    prior = len(physical_calls)
                    selected = {**payload, 'shop_preference': pref}
                    if pref == 'position_need':
                        selected['shop_position'] = 'WR'
                    alternative = generate_trade_workflow(data, selected)
                    comparisons.append({'preference': pref, 'additional_shared_evaluations': len(physical_calls)-prior,
                                        'result': alternative})
            broader = []
            if label == 'middle_market' and not performance_only:
                # Two counterparties, one omitted package per shape. No safety
                # relaxation; all identities come from constrained diagnostics.
                for stage in result['search_evidence']['stages'][:2]:
                    for boundary in stage.get('package_boundaries', []):
                        omitted = boundary['nearest_constructions'][1:2]
                        for candidate in omitted:
                            candidate_payload = {**payload, 'partner_roster_id': stage['partner_id'],
                                'assets_sent': candidate['assets_sent'], 'assets_received': candidate['assets_received']}
                            evaluated = capture(data, candidate_payload, workspace=workspace)
                            broader.append({'result': evaluated, 'qualifies': _trade_for_eligible(evaluated['evaluation'])})
            assert hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest() == before
            rows.append({'asset_id': target.asset_id, 'asset_type': target.kind, 'class': label,
                         'normal_physical_evaluations': normal_calls, 'result': result,
                         'preferences': comparisons, 'broader_recall': broader,
                         'performance_replay': performance,
                         'canonical_state_unchanged': True})
            print(json.dumps({'shop_target': target.asset_id, 'markets': result['count'],
                              'evaluated': result['search_evidence']['full_evaluations'],
                              'additional_recall_qualified': sum(r['qualifies'] for r in broader)}), flush=True)
    return {'league_id': data['league']['league_id'], 'searches': rows,
            'unique_shared_evaluations': len(memo), 'canonical_state_unchanged': True,
            'candidate_assessments': list(memo.values()),
            'scope': 'read-only public-source candidate; not authenticated production',
            'timing_note': 'Preference reruns reuse identical assessments diagnostically; only normal uncached search timings are end-to-end.'}
