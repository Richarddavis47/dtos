"""Bounded real-source adjustment evidence; no publication or source writes."""
import hashlib
import json
from unittest.mock import patch

from services.trade_intelligence import assist_trade_request, evaluate_trade_request


def adjust_samples(data, workspace):
    before = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    active = workspace['active_roster_id']
    partner = next(r for r in sorted(workspace['pools']) if r != active)
    def subset(roster):
        pool = workspace['pools'][roster]
        players = sorted((a for a in pool if a.kind == 'player' and a.trade_value is not None),
                         key=lambda a: (-a.trade_value, a.asset_id))[:3]
        picks = sorted((a for a in pool if a.kind == 'pick' and a.trade_value is not None),
                       key=lambda a: (a.season, a.round, a.asset_id))[:1]
        return players, picks
    own, own_picks = subset(active)
    other, other_picks = subset(partner)
    if len(own) < 2 or not other:
        return {'availability': 'insufficient', 'reason': 'No bounded owned priced-player fixture.'}
    allowed = {a.asset_id for a in (*own, *own_picks, *other, *other_picks)}
    excluded = [a.asset_id for pool in workspace['pools'].values() for a in pool if a.asset_id not in allowed]
    original = {'active_roster_id': active, 'partner_roster_id': partner,
                'assets_sent': [a.asset_id for a in own[:2]], 'assets_received': [other[0].asset_id],
                'excluded_assets': excluded, 'origin_workflow': 'create'}
    rows = []
    for instruction in ('cheaper', 'get another player back', 'alternative construction'):
        evaluated = []
        def capture(*args, **kwargs):
            row = evaluate_trade_request(*args, **kwargs)
            evaluated.append(row)
            return row
        payload = dict(original, instruction=instruction)
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=capture):
            result = assist_trade_request(data, payload)
        rows.append({'original': original, 'instruction': instruction, 'result': result,
                     'assessments': evaluated})
    assert before == hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    return {'league_id': data['league']['league_id'], 'cases': rows, 'canonical_state_unchanged': True,
            'scope': 'Three constrained candidate subsets; read-only real source, not production acceptance.',
            'limitations': ['Three priced players and one priced pick per side; not exhaustive repair recall.']}
