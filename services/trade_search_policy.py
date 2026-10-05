"""Request-local discovery classification, funnel and transparent ordering.

These policies never price assets, change a recommendation or infer acceptance.
"""
from collections import Counter


def classify(evaluation):
    dimensions = evaluation.get('dimensions') or {}
    legality = evaluation.get('legality') or {}
    if evaluation.get('legal') is False or legality.get('execution_status') in (
            'NOT EXECUTABLE', 'REQUIRES ROSTER RESOLUTION'):
        return 'HARD INVALID'
    if evaluation.get('generated_trade_eligible'):
        return 'CREDIBLE RECOMMENDATION'
    label = evaluation.get('recommendation')
    if label is None:
        missing = (evaluation.get('market_evidence') or {}).get('availability') != 'full'
        strategies = (dimensions.get('strategic_fit') or {})
        missing |= any(s.get('projection_coverage_complete') is False or s.get('production_evidence', {}).get('mean_weekly_delta') is None
                       for s in strategies.values() if isinstance(s, dict))
        missing |= 'FUTURE_CAPITAL_TRADEOFF_UNRESOLVED' in (evaluation.get('recommendation_trace') or {}).get('rule_reasons', [])
        return 'MISSING REQUIRED EVIDENCE' if missing else 'STRATEGICALLY POOR'
    if label in ('REJECT', 'NOT WORTH IT'):
        return 'STRATEGICALLY POOR'
    counterparty = (dimensions.get('counterparty_plausibility') or {}).get('assessment')
    if counterparty not in ('STRONG', 'PLAUSIBLE'):
        return 'COUNTERPARTY LIMITED'
    confidence = dimensions.get('confidence') or {}
    if confidence.get('assessment') not in ('MEDIUM', 'HIGH'):
        return 'MISSING REQUIRED EVIDENCE'
    if label == 'FAIR / OPTIONAL':
        return 'OPTIONAL / LOWER-RANKED TRADE'
    if label in ('SMASH ACCEPT', 'WORTH PURSUING'):
        return 'CREDIBLE RECOMMENDATION'
    return 'STRATEGICALLY POOR'


ELIGIBLE = {'CREDIBLE RECOMMENDATION', 'OPTIONAL / LOWER-RANKED TRADE'}


class SearchFunnel:
    def __init__(self, budget, partners=(), pools=None):
        self.budget = budget
        self.counts = Counter()
        self.reasons = Counter()
        self.partners = set(partners)
        self.teams = set()
        self.stages = []
        self.pools = {str(rid): len(pool) for rid, pool in (pools or {}).items()}
        self.near_misses = []

    def construction(self, partner, proposals, diagnostics=None):
        self.teams.add(partner)
        generated = (diagnostics or {}).get('cheap_package_pairs_inspected', len(proposals))
        self.counts['constructions_generated'] += generated
        self.counts['constructions_pruned'] += max(0, generated - len(proposals))
        self.stages.append({'partner_id': partner, **(diagnostics or {})})

    def assessed(self, row, *, filtered=False):
        state = classify(row['evaluation'])
        row['search_result_type'] = state
        self.counts['evaluated'] += 1
        field = {'HARD INVALID': 'hard_invalid', 'MISSING REQUIRED EVIDENCE': 'missing_evidence',
                 'COUNTERPARTY LIMITED': 'counterparty_limited',
                 'STRATEGICALLY POOR': 'strategically_rejected'}.get(state, 'eligible')
        if filtered and state in ELIGIBLE:
            field = 'filtered'
        self.counts[field] += 1
        e = row['evaluation']
        reasons = list(e.get('recommendation_trace', {}).get('rule_reasons') or [])
        if state == 'COUNTERPARTY LIMITED':
            reasons += (e.get('dimensions', {}).get('counterparty_plausibility') or {}).get('reason_codes') or []
        if state not in ELIGIBLE:
            reasons = reasons or [state.replace(' ', '_')]
            self.reasons.update(reasons)
            # A real assessed package, never target context dressed as an offer.
            self.near_misses.append({'search_result_type': 'NEAR MISS', 'blocker_type': state,
                'proposal': row['proposal'], 'proposal_presentation': row.get('proposal_presentation'),
                'evaluation': e, 'blockers': reasons, 'eligible': False,
                'smallest_optional_relaxation': (
                    'Provide the missing named evidence; the trade is not established.' if state == 'MISSING REQUIRED EVIDENCE'
                    else 'Resolve the identified ownership or roster constraint before reconsidering.' if state == 'HARD INVALID'
                    else 'Change the package to address the other roster’s stated cost.' if state == 'COUNTERPARTY LIMITED'
                    else 'Reduce the stated Market, production or package cost; strategy alone is not compensation.')})
        return state in ELIGIBLE and not filtered

    def result(self, displayed):
        fields = ('constructions_generated', 'constructions_pruned', 'evaluated', 'hard_invalid',
                  'missing_evidence', 'counterparty_limited', 'strategically_rejected', 'filtered', 'eligible')
        return {**{k: self.counts[k] for k in fields}, 'eligible_partners': len(self.partners),
                'teams_searched': len(self.teams), 'asset_pool_sizes': self.pools,
                'ranked': self.counts['eligible'], 'displayed': displayed,
                'evaluation_budget': self.budget, 'budget_reached': self.counts['evaluated'] >= self.budget,
                'rejection_reason_counts': dict(self.reasons), 'bounded': True}

    def near(self):
        # Prefer a supported strategic near miss over absent evidence or invalidity.
        order = {'COUNTERPARTY LIMITED': 0, 'STRATEGICALLY POOR': 1,
                 'MISSING REQUIRED EVIDENCE': 2, 'HARD INVALID': 3}
        return sorted(self.near_misses, key=lambda r: (order[r['blocker_type']],
            abs(1 - ((r['evaluation'].get('values') or {}).get('ratio', 1) or 1)),
            str(r['proposal'])))[:3]


def result_state(funnel, results):
    if results:
        return 'CREDIBLE RECOMMENDATION' if any(r.get('search_result_type') == 'CREDIBLE RECOMMENDATION'
                                              for r in results) else 'OPTIONAL / LOWER-RANKED TRADE'
    if funnel.counts['evaluated'] and funnel.counts['missing_evidence'] == funnel.counts['evaluated']:
        return 'MISSING REQUIRED EVIDENCE'
    return 'NO CREDIBLE RESULT WITHIN SEARCH BUDGET'


def rank_key(row):
    """Lexicographic evidence, not one blended score or overlapping horizon sum."""
    e = row['evaluation']
    dimensions = e.get('dimensions') or {}
    active = (dimensions.get('strategic_fit') or {}).get('active') or {}
    production = active.get('production_evidence') or {}
    capital = (active.get('future_capital') or {}).get('assessment') or {}
    intent = (active.get('manager_strategy') or {}).get('strategy')
    def descending(value):
        return (value is None, -(value or 0))
    benefit = (descending(capital.get('net_market_value')), descending(production.get('mean_weekly_delta')))
    if intent != 'REBUILD':
        benefit = benefit[::-1]
    package = (dimensions.get('package_quality') or {}).get('active') or {}
    ratio = (e.get('values') or {}).get('ratio')
    return ({'SMASH ACCEPT': 0, 'WORTH PURSUING': 1, 'FAIR / OPTIONAL': 2}.get(e.get('recommendation'), 3),
            *benefit,
            {'STRONG': 0, 'PLAUSIBLE': 1}.get((dimensions.get('counterparty_plausibility') or {}).get('assessment'), 2),
            {'HIGH': 0, 'MEDIUM': 1}.get((dimensions.get('confidence') or {}).get('assessment'), 2),
            package.get('assessment') == 'POOR', ratio is None, abs(1 - ratio) if ratio is not None else 0,
            (e.get('provenance') or {}).get('evaluation_id', str(row.get('proposal'))))


def diverse_rows(rows, assets, *, limit=5):
    """Primary identities define families; variants live inside their detail."""
    from hashlib import sha256
    import json
    families = {}
    for row in sorted(rows, key=rank_key):
        p = row['proposal']
        def primary(ids):
            players = [assets[i] for i in ids if assets[i].kind == 'player']
            return max(players or [assets[i] for i in ids],
                       key=lambda a: (a.trade_value or 0, a.asset_id)).asset_id
        sent, received = primary(p['assets_sent']), primary(p['assets_received'])
        key = (p['partner_roster_id'], sent, received)
        row.setdefault('family_id', sha256(json.dumps(key).encode()).hexdigest())
        row['ranking_evidence'] = {'method': 'lexicographic_separate_dimensions',
            'production': 'unique supported weeks only', 'strategy_changes_prices': False,
            'primary_outgoing': sent, 'primary_target': received, 'family': list(key)}
        if key not in families:
            families[key] = row
            row['variants'] = []
        elif len(families[key]['variants']) < 3:
            families[key]['variants'].append(row)
    pending = list(families.values())
    chosen, targets, outgoing, partners = [], set(), set(), set()
    while pending and len(chosen) < limit:
        # Prefer distinct targets/outgoing/partners before a second related idea.
        pending.sort(key=lambda r: (r['ranking_evidence']['primary_target'] in targets,
            r['ranking_evidence']['primary_outgoing'] in outgoing,
            r['proposal']['partner_roster_id'] in partners, rank_key(r)))
        row = pending.pop(0)
        chosen.append(row)
        targets.add(row['ranking_evidence']['primary_target'])
        outgoing.add(row['ranking_evidence']['primary_outgoing'])
        partners.add(row['proposal']['partner_roster_id'])
    return chosen
