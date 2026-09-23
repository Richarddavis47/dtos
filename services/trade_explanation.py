"""Thin presentation adapter for an already completed bilateral evaluation."""
from src.core.explanations import (
    Availability as A, EvidenceContext, EvidenceItem, EvidenceKind as K,
    Explanation, Statement,
)


HORIZONS = {'current_week': 'Current week', 'next_n': 'Next-N',
            'rest_of_regular_season': 'Rest of regular season', 'playoff_window': 'Playoff window'}
REASONS = {
    'OWNERSHIP_OR_IDENTITY_INVALID': 'The proposal has an ownership or identity problem.',
    'SUPPORTED_TEAM_IMPACT_UNAVAILABLE': 'Supported team impact is unavailable; no recommendation is inferred.',
    'CUT_COST_UNRESOLVED': 'Roster cuts still need resolution before this proposal is actionable.',
    'FUTURE_CAPITAL_TRADEOFF_UNRESOLVED': 'The future-capital trade-off cannot yet be resolved from supported evidence.',
    'LINEUP_AND_PACKAGE_COST_WITHOUT_DEPTH_BENEFIT': 'The accepted assessment finds lineup and package costs without a depth benefit.',
    'SUPPORTED_LINEUP_COST_WITHOUT_MARKET_OR_DEPTH_COMPENSATION': 'The supported lineup cost is not compensated by Market or depth evidence.',
    'SUPPORTED_HORIZON_BENEFIT_WITHOUT_DEPTH_OR_CAPACITY_LOSS': 'Supported horizons improve without an identified depth or capacity loss.',
    'PURSUIT_ONLY_MARKET_TERMS_UNRESOLVED': 'This is a pursuit recommendation; acquisition-price terms remain unresolved.',
    'MARKET_PREMIUM_FOR_SUPPORTED_LINEUP_BENEFIT': 'The supported lineup benefit requires paying a Market premium.',
    'SUPPORTED_MARKET_LINEUP_AND_DEPTH_PARITY': 'Supported Market, lineup and depth evidence is broadly balanced.',
    'MATERIAL_TRADEOFF_UNRESOLVED': 'A material trade-off remains unresolved.',
    'PARTIAL_MARKET_EVIDENCE': 'Some assets lack supported acquisition prices; Market comparison is partial.',
    'MARKET_EVIDENCE_UNAVAILABLE': 'Acquisition-price evidence is unavailable.',
    'PARTIAL_PROJECTION_EVIDENCE': 'Some requested weeks lack complete projected lineups.',
    'MIXED_WEEKLY_DEPTH_EFFECTS': 'Reserve coverage improves in some weeks and declines in others.',
    'ROSTER_SPOT_COST': 'Additional roster spots need resolution; no cut cost is assumed.',
    'FUTURE_CAPITAL_RECEIVED': 'Future draft capital is received; this does not establish future player production.',
    'FUTURE_CAPITAL_SENT': 'Future draft capital is sent away.',
    'COUNTERPARTY_PROJECTION_UNAVAILABLE': 'Their projected-lineup evidence is unavailable.',
    'COUNTERPARTY_TRADEOFF_UNRESOLVED': 'Their supported trade-offs do not establish a clear rationale.',
    'COUNTERPARTY_CAPACITY_UNRESOLVED': 'Their roster capacity still needs resolution.',
    'SUPPORTED_COUNTERPARTY_BENEFIT': 'The evaluation identifies a supported benefit for their team.',
    'COUNTERPARTY_LINEUP_AND_MARKET_GAIN': 'Their supported lineup and acquisition-price evidence both improve.',
    'POOR_COUNTERPARTY_PACKAGE': 'The accepted evaluation identifies poor package quality for their team.',
    'COUNTERPARTY_LINEUP_LOSS_WITHOUT_SUPPORTED_COMPENSATION': 'Their lineup declines without supported compensation.',
    'CURRENT_LINEUP_DOWNGRADE': 'The supported current-week optimal lineup loses projected points.',
    'NEXT_N_DOWNGRADE': 'The supported Next-N optimal lineups lose projected points.',
    'ROS_DOWNGRADE': 'The supported rest-of-regular-season optimal lineups lose projected points.',
    'PLAYOFF_WINDOW_DOWNGRADE': 'The supported playoff-window optimal lineups lose projected points; this is not a qualification forecast.',
    'DEPTH_LOSS': 'Supported reserve coverage declines.',
    'LOW_COUNTERPARTY_PLAUSIBILITY': 'The accepted evidence gives the counterparty limited reason to consider this proposal; it does not predict their response.',
}


def trade_explanation(result: dict, *, league_id: str) -> Explanation:
    provenance = result.get('provenance') or {}
    inputs = provenance.get('inputs') or {}
    if str(inputs.get('league_id')) != league_id:
        raise ValueError('Trade explanation league does not match completed evaluation')
    ctx = EvidenceContext('trade', f"{inputs.get('active_roster_id')}→{inputs.get('partner_roster_id')}",
                          provenance.get('evaluation_id'), provenance.get('strategy_methodology') or provenance.get('evaluator'), league_id)
    evidence, why, risks, limits, advanced = [], [], [], [], []

    def add(key, label, value, *, unit='classification', state=None, kind=K.DERIVED):
        evidence.append(EvidenceItem(key, label, kind, ctx, key, unit,
            state or (A.UNAVAILABLE if value is None else A.AVAILABLE),
            None if value is None else str(value)))
        return key

    def reason(code, key):
        return Statement(code, REASONS[code], (key,)) if code in REASONS else None

    rec = add('recommendation', 'Canonical recommendation', result.get('recommendation'), kind=K.INTERPRETATION)
    conclusion = Statement('CANONICAL_RECOMMENDATION', result.get('recommendation') or 'Recommendation unavailable', (rec,))
    for code in (result.get('recommendation_trace') or {}).get('rule_reasons') or []:
        if code in REASONS:
            key = add(f'recommendation.{code}', 'Accepted recommendation reason', REASONS[code], kind=K.INTERPRETATION)
            why.append(reason(code, key))
    dims = result.get('dimensions') or {}
    fairness = dims.get('value_fairness') or {}
    add('market', 'Market fairness · acquisition prices, not intrinsic worth', fairness.get('assessment'))
    if fairness.get('explanation'):
        advanced.append(Statement('MARKET_FAIRNESS', fairness['explanation'], ('market',)))
    market_state = (result.get('market_evidence') or {}).get('availability')
    if market_state in ('partial', 'unavailable'):
        code = 'PARTIAL_MARKET_EVIDENCE' if market_state == 'partial' else 'MARKET_EVIDENCE_UNAVAILABLE'
        limits.append(reason(code, 'market'))
    active_impacts, active_impact_keys = [], []
    for side, label in (('active', 'Your team'), ('partner', 'Their team')):
        quality = (dims.get('package_quality') or {}).get(side) or {}
        key = add(f'package.{side}', f'{label} package quality', quality.get('assessment'))
        if quality.get('explanation'):
            advanced.append(Statement('PACKAGE_QUALITY', quality['explanation'], (key,)))
        strategy = (dims.get('strategic_fit') or {}).get(side) or {}
        for horizon, title in HORIZONS.items():
            row = (strategy.get('horizons') or {}).get(horizon) or {}
            key = add(f'{side}.{horizon}', f'{label} · {title} optimal-lineup change', row.get('delta'), unit='fantasy points')
            if side == 'active':
                active_impact_keys.append(key)
                active_impacts.append(f"{title}: {row['delta']}" if row.get('delta') is not None else f'{title}: Unavailable')
            if row.get('weeks_requested') is not None:
                add(f'{key}.coverage', f'{label} · {title} requested / supported before / supported after weeks',
                    ' / '.join(', '.join(map(str, row.get(field) or [])) or 'none' for field in
                               ('weeks_requested', 'pre_supported_weeks', 'post_supported_weeks')), unit='week identities')
            if row.get('availability') in ('partial', 'partial_or_unavailable'):
                limits.append(Statement('PARTIAL_PROJECTION_EVIDENCE', f'{label} · {title} has incomplete week coverage.', (key,)))
            if row.get('supported_week_delta_subtotal') is not None and row.get('delta') is None:
                add(f'{key}.subtotal', f'{label} · {title} comparable-week subtotal only',
                    row['supported_week_delta_subtotal'], unit='fantasy points', state=A.PARTIAL)
        weekly = (((result.get('multi_horizon_impact') or {}).get('sides') or {}).get(side) or {}).get('weekly') or {}
        for week, row in sorted(weekly.items(), key=lambda item: int(item[0])):
            # Accepted before/after OPTIMAL totals and delta only. Never solve
            # another lineup, derive a missing delta, or use submitted starters.
            for phase, title in (('pre', 'Before trade'), ('post', 'After trade')):
                points = ((row.get(phase) or {}).get('optimal') or {}).get('projected_points')
                add(f'weekly.{side}.{week}.{phase}', f'{label} · Week {week} · {title} optimal total', points, unit='fantasy points')
            add(f'weekly.{side}.{week}.delta', f'{label} · Week {week} · Optimal-lineup change', row.get('delta'), unit='fantasy points')
        for week, change in (strategy.get('reserve_slot_changes') or {}).items():
            add(f'{side}.depth.{week}', f'{label} · week {week} reserve coverage change', change, unit='supported reserve slots')
        for direction in ('received', 'sent'):
            for index, pick in enumerate((strategy.get('future_capital') or {}).get(direction) or []):
                add(f'{side}.capital.{direction}.{index}', f'{label} future capital {direction}', pick.get('asset_id'), unit='pick identity')
        for code in strategy.get('reason_codes') or []:
            if code not in REASONS:
                continue  # Unknown reasons are not guessed from their spelling.
            key = add(f'{side}.reason.{code}', f'{label} accepted context', REASONS[code], kind=K.INTERPRETATION)
            row = reason(code, key)
            if row:
                advanced.append(Statement(row.code, f'{label}: {row.text}', row.evidence_keys))
    if active_impact_keys:
        why = why[:1] + [Statement('ACCEPTED_HORIZON_CHANGES',
            'Your optimal-lineup changes (fantasy points): ' + '; '.join(active_impacts)
            + '. Separate horizons; not one combined upgrade/downgrade.', tuple(active_impact_keys))]
    partner = dims.get('counterparty_plausibility') or {}
    key = add('counterparty', 'Why they may consider it · plausibility', partner.get('assessment'), kind=K.INTERPRETATION)
    partner_reasons = []
    for code in partner.get('reason_codes') or []:
        row = reason(code, key)
        if row:
            partner_reasons.append(row)
    if partner_reasons:
        advanced.extend(partner_reasons)
        why = why[:2] + [Statement('COUNTERPARTY_RATIONALE', 'Why they may consider it: ' + partner_reasons[0].text, (key,))]
    if partner.get('explanation'):
        advanced.append(Statement('COUNTERPARTY_CONTEXT', partner['explanation'], (key,)))
    confidence = dims.get('confidence') or {}
    add('confidence', 'Evidence support, not acceptance probability', confidence.get('assessment'))
    confidence_rows = (Statement('EVIDENCE_SUPPORT', confidence['explanation'], ('confidence',)),) if confidence.get('explanation') else ()
    for code in result.get('major_risks') or []:
        if code not in REASONS:
            continue
        key = add(f'risk.{code}', 'Accepted risk', REASONS[code], kind=K.INTERPRETATION)
        row = reason(code, key)
        if row:
            risks.append(row)
    return Explanation('Why DTOS recommends this', league_id, (ctx,), tuple(evidence), conclusion,
                       tuple(why[:3]), tuple(risks[:3]), confidence_rows, tuple(limits), tuple(advanced))


def render_trade_explanation(result: dict, *, league_id: str) -> str:
    """Use the shared renderer; weekly rows are optional presentation detail."""
    from src.ui.explanations import explanation_panel
    view = trade_explanation(result, league_id=league_id)
    weekly = tuple(item.key for item in view.evidence if item.key.startswith('weekly.'))
    return explanation_panel(view, evidence_groups=(('Weekly optimal-lineup detail', weekly),) if weekly else ())
