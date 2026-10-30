"""Request-local construction admission; never a trade recommendation.

Filter ownership already rejected by the evaluator and use its exact configured
capacity arithmetic only when the same prepared lineup scope is admitted.
Incoming players are active; no implicit cuts, IR/taxi moves or exceptions.
"""
from collections import Counter

from src.core.intelligence.team_strength import canonical_rosters, compatible_profile
from src.core.trade_intelligence.capital_assessment import pick_identity_errors
from src.core.trade_intelligence.roster_space import active_player_ids, configured_active_slots


class CandidateAdmission:
    def __init__(self, data, workspace, snapshot):
        from src.core.intelligence.roster_diagnostics import _bounded, _qualification

        positions = tuple(str(slot).upper() for slot in (data.get('league') or {}).get('roster_positions') or ())
        pools = {str(team['roster_id']): team.get('players') or [] for team in data.get('teams') or []}
        self.capacity_supported = bool(compatible_profile(data, snapshot) is not None
                                       and _bounded(positions, pools)
                                       and _qualification(data, snapshot, positions)['calculation_supported'])
        self.capacity = configured_active_slots(positions)
        self.active = ({int(row['roster_id']): active_player_ids(row) for row in canonical_rosters(data)}
                       if self.capacity_supported else {})
        self.ownership = workspace['player_ownership']
        self.identities = Counter(a.asset_id for pool in workspace['pools'].values() for a in pool)
        self.asset_rejections = Counter()
        self.capacity_checks = 0
        self.capacity_rejections = 0

    def owned(self, asset, owner):
        reason = None
        if self.identities[asset.asset_id] != 1 or asset.source_roster_id != owner:
            reason = 'conflicting_owner_or_identity'
        elif asset.kind == 'player':
            resolved = self.ownership.resolve(asset.asset_id, owner)
            if resolved['state'] != 'OWNED_BY_ME':
                reason = 'player_ownership_unavailable'
        elif asset.kind == 'pick':
            if (any(value is None for value in (asset.season, asset.round, asset.original_roster_id, asset.current_owner_id))
                    or asset.current_owner_id != owner or pick_identity_errors(asset)):
                reason = 'pick_owner_or_identity_mismatch'
        else:
            reason = 'unsupported_asset_identity'
        if reason:
            self.asset_rejections[reason] += 1
        return reason is None

    def signature(self, assets, owner):
        players = {a.asset_id.removeprefix('player:') for a in assets if a.kind == 'player'}
        return len(players), len(players & self.active.get(owner, set()))

    def allows_signatures(self, active, partner, sent, received):
        if not self.capacity_supported:
            return True  # Unavailable evidence is left to the full evaluator.
        self.capacity_checks += 1
        valid = (len(self.active[active]) - sent[1] + received[0] <= self.capacity
                 and len(self.active[partner]) - received[1] + sent[0] <= self.capacity)
        self.capacity_rejections += not valid
        return valid

    def allows(self, active, partner, sent, received):
        if not self.capacity_supported:
            return True
        return self.allows_signatures(active, partner, self.signature(sent, active), self.signature(received, partner))

    def summary(self):
        return {'ownership_rejected_assets': sum(self.asset_rejections.values()),
                'ownership_rejection_reasons': dict(self.asset_rejections),
                'capacity_evidence_supported': self.capacity_supported,
                'roster_capacity_checks': self.capacity_checks,
                'roster_capacity_rejected_checks': self.capacity_rejections,
                'counting': 'construction checks including repeated phase/shape candidates; not distinct evaluated offers',
                'implicit_drops': 0, 'provider_calls': 0, 'solver_calls': 0}


def admit_workspace(data, workspace, snapshot):
    admission = CandidateAdmission(data, workspace, snapshot)
    return {**workspace, 'candidate_admission': admission,
            'pools': {owner: tuple(asset for asset in pool if admission.owned(asset, owner))
                      for owner, pool in workspace['pools'].items()}}
