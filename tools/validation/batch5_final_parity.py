"""In-memory A/B/A active-consumer replay; no extra source ingestion or writes."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
from time import perf_counter

from services.trade_intelligence import build_trade_workspace, evaluate_trade_request, _trade_search_boundary
from src.core.intelligence.team_strength import compatible_profile
from src.platform.league_context import _CURRENT_CONTEXT


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class RetainedRead:
    def __init__(self, service, weeks):
        self.pinned = deepcopy(service.snapshot())
        self.weeks = {week: deepcopy(service.week_snapshot(week, generation_snapshot=self.pinned)) for week in weeks}

    def snapshot(self):
        return self.pinned

    def week_snapshot(self, week, *, generation_snapshot):
        assert generation_snapshot == self.pinned
        return self.weeks.get(week)


def round_trip(inputs):
    assert len(inputs) == 2
    rows = []
    evaluation_seconds = []
    original = [digest(data) for data, _ in inputs]
    for index in (0, 1, 0):
        data, reader = inputs[index]
        league_id = data['league']['league_id']
        token = _CURRENT_CONTEXT.set(SimpleNamespace(league_id=league_id, projection=reader,
                                                     runtime=SimpleNamespace(source_generations={})))
        try:
            profile = compatible_profile(data, reader.snapshot())
            assert profile is not None
            active, partner = sorted(int(t['roster_id']) for t in data['teams'])[:2]
            workspace = build_trade_workspace(data, active)
            def priced(roster):
                return sorted(a.asset_id for a in workspace['pools'][roster] if a.kind == 'player' and a.trade_value is not None)[0]
            payload = {'workflow': 'create', 'active_roster_id': active, 'partner_roster_id': partner,
                       'assets_sent': [priced(active)], 'assets_received': [priced(partner)]}
            started = perf_counter()
            evaluated = evaluate_trade_request(data, payload, workspace=workspace, projection_reader=reader)
            evaluation_seconds.append(perf_counter() - started)
            for workflow in ('trade_for', 'shop', 'recommended', 'adjust', 'create_alternative'):
                alternate = evaluate_trade_request(data, dict(payload, workflow=workflow),
                                                   workspace=workspace, projection_reader=reader)
                assert alternate['evaluation'] == evaluated['evaluation'], workflow
            rows.append({'league_id': league_id, 'canonical_input_hash': digest(data),
                         'projection_hash': digest(reader.pinned), 'strength_hash': digest(profile),
                         'boundary': _trade_search_boundary(data),
                         'evaluation_hash': digest(evaluated['evaluation']),
                         'pick_count': len(data.get('pick_ledger') or []),
                         'draft_rounds': data['league']['settings']['draft_rounds']})
            wrong = inputs[1-index][1]
            assert compatible_profile(data, wrong.snapshot()) is None
        finally:
            _CURRENT_CONTEXT.reset(token)
    assert rows[0] == rows[2]
    assert rows[0]['boundary'] != rows[1]['boundary']
    assert [digest(data) for data, _ in inputs] == original
    return {'sequence': rows, 'manual_evaluation_seconds': evaluation_seconds,
            'exact_restoration': True, 'wrong_league_artifact_rejected': True,
            'six_origins_same_evaluation': True,
            'canonical_inputs_unchanged': True,
            'scope': 'Real-source implementation replay, not authenticated production navigation; existing account/session and FOIS isolation proofs remain separate.'}
