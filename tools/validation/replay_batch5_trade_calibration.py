"""Recheck only decision calibration from retained real impact magnitudes."""
import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from src.core.trade_intelligence.strategy_dimensions import reconcile_result


def replay(path):
    body = path.read_bytes()
    source = json.loads(body)
    rows = []
    for league in source['leagues']:
        for case in league['trade_panel']['proposals']:
            result = case['result']
            prior = result['evaluation']
            capital = {}
            for side in prior['dimensions']['strategic_fit'].values():
                if isinstance(side, dict):
                    for picks in side.get('future_capital', {}).values():
                        if isinstance(picks, list):
                            capital.update({pick['asset_id']: pick for pick in picks})
            def assets(direction):
                return tuple(SimpleNamespace(asset_id=a['asset_id'], kind=a['kind'], trade_value=a['market_value'],
                    season=capital.get(a['asset_id'], {}).get('year'), round=capital.get(a['asset_id'], {}).get('round'),
                    original_roster_id=capital.get(a['asset_id'], {}).get('original_franchise'),
                    current_owner_id=capital.get(a['asset_id'], {}).get('canonical_owner'),
                    pick_market_evidence=capital.get(a['asset_id'], {}).get('market_evidence'),
                    projected_range=a.get('projected_range'), projected_range_confidence=a.get('range_confidence'),
                    exact_slot=capital.get(a['asset_id'], {}).get('exact_slot'))
                    for a in result['proposal_presentation'][direction])
            proposal = SimpleNamespace(**result['proposal'])
            proposal.assets_sent, proposal.assets_received = assets('send'), assets('receive')
            windows = {str(proposal.active_roster_id if side == 'active' else proposal.partner_roster_id): profile['competitive_window']
                       for side, profile in prior['dimensions']['strategic_fit'].items()
                       if isinstance(profile, dict) and profile.get('competitive_window')}
            updated = reconcile_result(deepcopy(prior), proposal, prior['multi_horizon_impact'],
                prior['dimensions']['counterparty_plausibility'].get('historical_context'), team_windows=windows)
            rows.append({'league': league['league_id'], 'shape': case['shape'],
                         'before': prior['recommendation'], 'after': updated['recommendation'],
                         'plausibility': updated['dimensions']['counterparty_plausibility']['assessment'],
                         'recommendation_trace': updated.get('recommendation_trace'),
                         'reason_codes': updated['reason_codes']})
    return {'source_sha256': hashlib.sha256(body).hexdigest(),
            'scope': 'calibration-only replay; original live-source/manual-path proof preserved, no new source observations',
            'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = replay(args.source)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
