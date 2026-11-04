"""Bounded real-owned proposals through manual application evaluation, not search."""
import hashlib
import json
import cProfile
import pstats
from time import perf_counter
from unittest.mock import patch

from services.trade_intelligence import build_trade_workspace, evaluate_trade_request, generate_trade_workflow, _trade_for_eligible
from src.core.history_context.metadata import MinimalMetadataStore
from src.core.intelligence.pick_context import prepare_pick_context


def samples(data, service, market, transfers, directory, *, searches=False, profile_search=False, shop=False, recommended=False, adjust=False, shop_performance=False):
    data['market_data'] = market
    league = data['league']
    season = int(league['season'])
    roster_ids = sorted(int(t['roster_id']) for t in data['teams'])
    owners = {(int(p['season']), int(p['round']), int(p['roster_id'])): int(p['owner_id']) for p in transfers}
    data['pick_ledger'] = [dict(year=year, round=round_, original_roster_id=original,
                                current_owner_id=owners.get((year, round_, original), original))
                           for year in range(season + 1, season + 4)
                           for round_ in range(1, int(league['settings']['draft_rounds']) + 1)
                           for original in roster_ids]
    prepare_pick_context(data, MinimalMetadataStore(directory/'trade-panel-metadata.sqlite3'), observed_at='diagnostic')
    active, partner = roster_ids[:2]
    results = []
    with patch('src.core.projection_intelligence.projection_service.snapshot', side_effect=service.snapshot), patch(
            'src.core.projection_intelligence.projection_service.week_snapshot', side_effect=service.week_snapshot):
        workspace = build_trade_workspace(data, active)
        pools = workspace['pools']
        if adjust:
            from tools.validation.batch5_adjust_samples import adjust_samples
            return adjust_samples(data, workspace)
        if recommended:
            from tools.validation.batch5_recommended_samples import recommended_samples
            return recommended_samples(data, workspace)
        if shop or shop_performance:
            from tools.validation.batch5_shop_samples import shop_samples
            return shop_samples(data, workspace, performance_only=shop_performance)
        def players(roster):
            return sorted((a for a in pools[roster] if a.kind == 'player' and a.trade_value is not None),
                          key=lambda a: (-a.trade_value, a.asset_id))
        left, right = players(active), players(partner)
        if searches:
            if profile_search:
                # Diagnostic instrumentation only. Normal product code has no
                # profiler, timer callbacks, or expanded search dependency.
                from src.core.trade_intelligence.horizon_impact import prepare_team_strength
                post_timings = []
                def timed_post(*args, **kwargs):
                    timing = {}
                    result = prepare_team_strength(*args, **kwargs, timings=timing)
                    post_timings.append(timing)
                    return result
                before = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
                target = right[len(right)//2]
                payload = {'workflow': 'trade_for', 'active_roster_id': active,
                           'asset_id': target.asset_id, 'partner_roster_id': partner}
                profiler = cProfile.Profile()
                assessments = []
                def capture_profile(*args, **kwargs):
                    row = evaluate_trade_request(*args, **kwargs)
                    assessments.append(row['evaluation'])
                    return row
                with patch('src.core.trade_intelligence.horizon_impact.prepare_team_strength', side_effect=timed_post), \
                        patch('services.trade_intelligence.evaluate_trade_request', side_effect=capture_profile):
                    profiler.enable()
                    result = generate_trade_workflow(data, payload)
                    serialization_started = perf_counter()
                    json.dumps(result, default=str)
                    serialization_seconds = perf_counter() - serialization_started
                    profiler.disable()
                cached_assessments = assessments[:]
                assessments.clear()
                from services.trade_intelligence import _SearchProjectionReader
                def uncached(reader, week, *, generation_snapshot):
                    return reader.service.week_snapshot(week, generation_snapshot=generation_snapshot)
                with patch.object(_SearchProjectionReader, 'week_snapshot', uncached), \
                        patch('services.trade_intelligence.evaluate_trade_request', side_effect=capture_profile):
                    baseline = generate_trade_workflow(data, payload)
                assert assessments == cached_assessments, 'Projection read reuse changed shared evaluation'
                assert baseline['results'] == result['results']
                entries = []
                for (filename, line, function), (primitive, calls, own, cumulative, _) in pstats.Stats(profiler).stats.items():
                    if 'dtos' in filename.casefold() and '.venv' not in filename.casefold():
                        entries.append({'module': filename.replace('\\', '/').split('/dtos/')[-1],
                                        'function': function, 'calls': calls, 'own_seconds': own,
                                        'inclusive_seconds': cumulative})
                assert hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest() == before
                assert len(post_timings) == result['search_evidence']['full_evaluations']
                return {'target': target.asset_id, 'result': result, 'post_trade_timings': post_timings,
                        'serialization_seconds': serialization_seconds,
                        'profile': sorted(entries, key=lambda r: -r['inclusive_seconds']),
                        'uncached_unprofiled_seconds': baseline['search_evidence']['timings_seconds'],
                        'all_shared_assessments_exactly_equal': True,
                        'canonical_state_unchanged': True,
                        'scope': 'single bounded expensive representative; inclusive timings overlap; profiler adds overhead'}
            targets = [('highest_market_player', right[0]), ('middle_market_player', right[len(right)//2])]
            pick_targets = [a for a in pools[partner] if a.kind == 'pick']
            if pick_targets:
                targets.append(('pick', pick_targets[0]))
            before = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
            search_rows = []
            for label, target in targets:
                evaluations = []
                def capture(*args, **kwargs):
                    result = evaluate_trade_request(*args, **kwargs)
                    evaluations.append(result)
                    return result
                with patch('services.trade_intelligence.evaluate_trade_request', side_effect=capture):
                    result = generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': active,
                        'asset_id': target.asset_id, 'partner_roster_id': partner})
                assert hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest() == before
                assert all(target.asset_id in r['proposal']['assets_received'] for r in evaluations)
                # Diagnostic only: the two nearest omitted constructions in each
                # shape plus two outgoing shortlist-boundary players. Keep the
                # target, exact ownership, and normal package size bounds intact.
                identities = {(tuple(sorted(r['proposal']['assets_sent'])), tuple(sorted(r['proposal']['assets_received']))) for r in evaluations}
                additional = []
                stages = result['search_evidence']['stages'][0]
                broader = [row for boundary in stages.get('package_boundaries', [])
                           for row in boundary['nearest_constructions'][1:]]
                excluded_ids = set(stages.get('shortlist_excluded_asset_ids', {}).get('sent', []))
                outside = sorted((a for a in pools[active] if a.asset_id in excluded_ids
                                  and a.kind == 'player' and a.trade_value is not None),
                                 key=lambda a: (abs(a.trade_value - target.trade_value), a.asset_id))
                if target.kind == 'player':
                    broader.extend({'assets_sent': [a.asset_id], 'assets_received': [target.asset_id],
                                    'selection': 'outside_shortlist_boundary'} for a in outside[:2])
                for row in broader:
                    identity = (tuple(sorted(row['assets_sent'])), tuple(sorted(row['assets_received'])))
                    if identity in identities:
                        continue
                    identities.add(identity)
                    assessment = evaluate_trade_request(data, {'workflow': 'trade_for', 'active_roster_id': active,
                        'partner_roster_id': partner, 'assets_sent': row['assets_sent'],
                        'assets_received': row['assets_received']}, workspace=workspace)
                    additional.append({'boundary': row['selection'], 'qualifies': _trade_for_eligible(assessment['evaluation']),
                                       'result': assessment})
                assert hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest() == before
                search_rows.append({'target_class': label, 'target_id': target.asset_id,
                    'current_owner': partner, 'canonical_state_unchanged': True,
                    'target_pick_evidence': target.pick_market_evidence if target.kind == 'pick' else None,
                    'result': result, 'evaluated_candidates': evaluations,
                    'recall_comparison': {'additional_evaluations': len(additional),
                        'additional_qualifying': sum(row['qualifies'] for row in additional),
                        'bounded_not_exhaustive': True, 'candidates': additional}})
            constrained = generate_trade_workflow(data, {'workflow': 'trade_for', 'active_roster_id': active,
                'asset_id': right[0].asset_id, 'protected_assets': [a.asset_id for a in pools[active]]})
            assert constrained['count'] == 0 and constrained['search_evidence']['full_evaluations'] == 0
            assert hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest() == before
            return {'league_id': league['league_id'], 'scope': 'real owned-target search through active service, read-only public evidence',
                    'searches': search_rows, 'all_protected': constrained,
                    'canonical_state_unchanged': True, 'constraints_not_persisted': True}
        proposals = []
        if left and right:
            proposals.append(('one_for_one', [left[0]], [right[0]]))
        if len(left) >= 3 and right:
            proposals.append(('three_for_one', left[:3], right[:1]))
        if left and len(right) >= 3:
            proposals.append(('one_for_three', left[:1], right[:3]))
        picks = [a for a in pools[partner] if a.kind == 'pick']
        if left and picks:
            proposals.append(('player_for_pick', left[:1], picks[:1]))
        missing = [a for a in pools[partner] if a.trade_value is None]
        if left and missing:
            proposals.append(('source_missing_price', left[:1], missing[:1]))
        coverage = []
        for roster_id, pool in pools.items():
            missing_assets = [a for a in pool if a.trade_value is None]
            coverage.append({'roster_id': roster_id, 'asset_count': len(pool),
                             'unpriced': [{'asset_id': a.asset_id, 'kind': a.kind,
                                          'source_roster_id': a.source_roster_id,
                                          'calibration_status': a.calibration_status,
                                          'pick_market_evidence': a.pick_market_evidence}
                                         for a in missing_assets]})
        before = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
        for shape, sent, received in proposals:
            result = evaluate_trade_request(data, {'workflow': 'create', 'active_roster_id': active,
                'partner_roster_id': partner, 'assets_sent': [a.asset_id for a in sent],
                'assets_received': [a.asset_id for a in received]}, workspace=workspace)
            after = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
            assert after == before, 'Manual evaluation mutated canonical input data'
            results.append({'shape': shape, 'canonical_state_unchanged': True, 'result': result})
        # Search all current ownership pools, not just the first two managers.
        # Preserve provider evidence unchanged: no price deletion or substitution.
        if not any(row['shape'] == 'source_missing_price' for row in results):
            candidates = [(rid, a) for rid, pool in pools.items() for a in pool if a.trade_value is None]
            for target_id, missing_asset in candidates[:1]:
                sending_id = next((rid for rid in roster_ids if rid != target_id and players(rid)), None)
                if sending_id is None:
                    break
                scoped_workspace = build_trade_workspace(data, sending_id)
                result = evaluate_trade_request(data, {'workflow': 'create', 'active_roster_id': sending_id,
                    'partner_roster_id': target_id, 'assets_sent': [players(sending_id)[0].asset_id],
                    'assets_received': [missing_asset.asset_id]}, workspace=scoped_workspace)
                assert hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest() == before
                results.append({'shape': 'source_missing_price', 'canonical_state_unchanged': True, 'result': result})
    return {'scope': 'public retained source through actual manual service; not authenticated production acceptance',
            'league_id': league['league_id'], 'proposals': results,
            'current_owned_market_coverage': coverage,
            'limitations': ['No production FOIS history transferred; historical behavior may be unavailable.',
                            'Proposal shapes are not predetermined quality classifications.']}
