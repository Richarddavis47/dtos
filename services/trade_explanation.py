"""Thin presentation adapter for an already completed bilateral evaluation."""
from src.core.explanations import (
    Availability as A, EvidenceContext, EvidenceItem, EvidenceKind as K,
    Explanation, Statement,
)
from src.ui.intelligence_presentation import manager_points
from src.ui.customer_experience import plain_reason
from src.core.player_value_projection.sleeper_actuals import actual_display
from html import escape
from services.trade_decision import final_decision, lineup_comparisons
from services.trade_lineup_evidence import completed_lineup_admissions, weekly_total_display, diagnostic_summary_display


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
    'SEVERE_MARKET_LOSS': 'The return loses more than half the supported Market value, exceeding the existing severe-loss policy.',
    'NEUTRAL_SEVERE_MARKET_LOSS': 'Severe neutral Market loss prevents endorsement; personal interest does not erase the actual Market cost.',
    'MARKET_COST_WITHOUT_MATERIAL_BENEFIT': 'The Market cost is not justified by a material supported lineup or qualifying depth benefit.',
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
    'RESERVE_PRODUCTION_LOSS': 'Projected points from eligible backups fall, even if the same number of backup slots is covered.',
    'RESERVE_PRODUCTION_GAIN': 'Projected points from eligible backups improve; this helps depth, not the starting lineup.',
    'MIXED_WEEKLY_RESERVE_PRODUCTION': 'Replacement production improves in some supported weeks and declines in others; the changes do not establish a uniform gain.',
    'RESERVE_PRODUCTION_COST_WITHOUT_SUPPORTED_COMPENSATION': 'Useful replacement production declines without a material supported starter gain or Market compensation.',
    'RESERVE_QUALITY_UNAVAILABLE': 'Complete reserve-production evidence is unavailable; missing projections are not zero.',
    'LOW_COUNTERPARTY_PLAUSIBILITY': 'The accepted evidence gives the counterparty limited reason to consider this proposal; it does not predict their response.',
    'MATERIAL_PRODUCTION_GAIN_WITH_DISCLOSED_ROSTER_COST': 'The supported production gain is material; the recorded roster and depth costs still matter.',
    'SUPPORTED_DEPTH_GAIN_WITH_DISCLOSED_MARKET_COST': 'Supported replacement depth improves, with the recorded Market cost still part of the trade-off.',
}


def _reason_display(code, personal):
    text = REASONS[code]
    if personal and code not in {'NEUTRAL_SEVERE_MARKET_LOSS', 'LOW_COUNTERPARTY_PLAUSIBILITY'}:
        text = text.replace('canonical Market', 'personal valuation').replace('Market', 'personal valuation')
    return text


def decision_lead(result, final, admissions):
    """Describe the recorded verdict and rule, without deciding eligibility again."""
    state = final['classification']
    personal = bool(result.get('personal_value_evidence'))
    if any(row['identity_state'] != 'compatible' or row['invalid_comparison']
           for row in admissions.values()):
        reason = 'The full source-compatible lineup comparison cannot be verified. Independently supported Market and cost evidence remains separate.'
    elif state == 'HARD INVALID':
        reason = (REASONS['OWNERSHIP_OR_IDENTITY_INVALID'] if result.get('legal') is False
                  else REASONS['CUT_COST_UNRESOLVED'])
    elif state == 'COUNTERPARTY LIMITED':
        partner = (result.get('dimensions') or {}).get('counterparty_plausibility') or {}
        blockers = {'COUNTERPARTY_PROJECTION_UNAVAILABLE', 'COUNTERPARTY_TRADEOFF_UNRESOLVED',
                    'COUNTERPARTY_CAPACITY_UNRESOLVED', 'POOR_COUNTERPARTY_PACKAGE',
                    'COUNTERPARTY_LINEUP_LOSS_WITHOUT_SUPPORTED_COMPENSATION', 'LOW_COUNTERPARTY_PLAUSIBILITY'}
        reason = next((REASONS[c] for c in partner.get('reason_codes') or [] if c in blockers),
                      partner.get('explanation') or 'A supported benefit or adequate compensation for the other team is not established.')
    else:
        trace = result.get('recommendation_trace') or {}
        capital = ((result.get('dimensions') or {}).get('strategic_fit') or {}).get('active') or {}
        capital_reason = (capital.get('capital_strategy_fit') or {}).get('explanation')
        if capital_reason and personal:
            capital_reason = capital_reason.replace('canonical Market', 'personal valuation').replace('Market', 'personal valuation')
        reason = next((_reason_display(c, personal) for c in trace.get('rule_reasons') or [] if c in REASONS),
                      capital_reason
                      or final.get('qualification') or result.get('dominant_reason')
                      or 'Review the supported trade-offs and evidence limitations below.')
    if final['qualified']:
        action = 'Preview the exact offer, review both teams’ costs and confirm the other manager’s motivation.'
    elif state == 'HARD INVALID':
        action = 'Resolve the recorded ownership or roster-space blocker before pursuing this package.'
    elif state == 'COUNTERPARTY LIMITED':
        action = 'Review their sacrifice and compensation; confirm their direction before pursuing this offer.'
    elif state == 'MISSING REQUIRED EVIDENCE':
        action = 'Review the named evidence gaps below. Changing a pick cannot supply missing projections.'
    elif result.get('recommendation') in ('REJECT', 'NOT WORTH IT'):
        action = 'Do not pursue this package on the recorded evidence. Review its costs before editing.'
    else:
        action = 'Compare the supported trade-offs. This is optional, not a qualified recommendation.'
    return {'decisive_reason': reason, 'decision_next_step': action}


def trade_explanation(result: dict, *, league_id: str, _admissions=None) -> Explanation:
    admissions = _admissions or completed_lineup_admissions(result)
    provenance = result.get('provenance') or {}
    inputs = provenance.get('inputs') or {}
    if str(inputs.get('league_id')) != league_id:
        raise ValueError('Trade explanation league does not match completed evaluation')
    ctx = EvidenceContext('trade', f"{inputs.get('active_roster_id')}→{inputs.get('partner_roster_id')}",
                          provenance.get('evaluation_id'), provenance.get('strategy_methodology') or provenance.get('evaluator'), league_id)
    evidence, why, risks, limits, advanced = [], [], [], [], []
    personal = bool(result.get('personal_value_evidence'))

    def reason_text(code):
        return _reason_display(code, personal)

    def add(key, label, value, *, unit='classification', state=None, kind=K.DERIVED):
        evidence.append(EvidenceItem(key, label, kind, ctx, key, unit,
            A.UNAVAILABLE if value is None else (state or A.AVAILABLE),
            None if value is None else weekly_total_display(value)
            if unit == 'fantasy points' and key.startswith('weekly.') and not key.endswith('.delta') else manager_points(value)
            if unit == 'fantasy points' else str(value)))
        return key

    def reason(code, key):
        return Statement(code, reason_text(code), (key,)) if code in REASONS else None

    final = final_decision(result, _admissions=admissions)
    add('recommendation', 'Your-side Custom assessment' if personal else 'Your-side assessment', result.get('recommendation'), kind=K.INTERPRETATION)
    final_key = add('bilateral_decision', 'Final bilateral qualification', final['headline'], kind=K.INTERPRETATION)
    conclusion = Statement('FINAL_BILATERAL_RECOMMENDATION', final['headline'], (final_key,))
    active_admission = admissions['active']
    production_verified = active_admission['identity_state'] == 'compatible' and not active_admission['invalid_comparison']
    for code in (result.get('recommendation_trace') or {}).get('rule_reasons') or []:
        if code in REASONS and production_verified:
            key = add(f'recommendation.{code}', 'Accepted recommendation reason', reason_text(code), kind=K.INTERPRETATION)
            why.append(reason(code, key))
    dims = result.get('dimensions') or {}
    history = dims.get('historical_counterparty_evidence') or {}
    for index, signal in enumerate((history.get('trend_signals') or [])[:2]):
        if signal.get('explanation'):
            add(f'market_timing.{index}', 'Observed neutral Market movement', signal['explanation'])
    diagnostic = dims.get('roster_diagnostics') or {}
    for side, row in diagnostic.get('sides', {}).items():
        if (admissions.get(side) or {}).get('identity_state') != 'compatible':
            continue
        summary = diagnostic_summary_display(row)
        key = add('diagnostics.' + side, ('Your' if side == 'active' else 'Their') + ' package roster context', summary)
        advanced.append(Statement('ROSTER_DIAGNOSTICS', summary + ' ' + diagnostic['meaning'], (key,)))
        for position, facts in row['positions'].items():
            text = facts['pre']['interpretation'] + ' Availability-qualified post-package starter/reserve counts: ' + str(len(facts['post_starters'])) + '/' + str(len(facts['post_disjoint_reserves'])) + '.'
            item_key = add('diagnostics.' + side + '.' + position, position + ' replacement context', text)
            advanced.append(Statement('POSITION_CONTEXT', text, (item_key,)))
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
        if quality.get('explanation') and admissions[side]['identity_state'] == 'compatible' and not admissions[side]['invalid_comparison']:
            advanced.append(Statement('PACKAGE_QUALITY', quality['explanation'], (key,)))
        strategy = (dims.get('strategic_fit') or {}).get(side) or {}
        fit = strategy.get('capital_strategy_fit') or {}
        side_admission = admissions[side]
        side_verified = side_admission['identity_state'] == 'compatible' and not side_admission['invalid_comparison']
        if fit.get('explanation') and side_verified:
            key = add(f'{side}.strategy_fit', f'{label} strategy and capital assessment', fit['explanation'], kind=K.INTERPRETATION)
            statement = Statement('CAPITAL_STRATEGY_FIT', f'{label}: {fit["explanation"]}', (key,))
            if side == 'active':
                why.insert(0, statement)
            else:
                advanced.append(statement)
        capital = (strategy.get('future_capital') or {}).get('assessment') or {}
        for field, title in (('received_market_value', 'Capital received'), ('sent_market_value', 'Capital spent'), ('net_market_value', 'Net capital')):
            if capital:
                add(f'{side}.capital.{field}', f'{label} · {title}', capital.get(field),
                    unit='personal rank-slot value' if personal and side == 'active' else 'canonical Market price')
        for horizon, title in HORIZONS.items():
            row = (strategy.get('horizons') or {}).get(horizon) or {}
            admitted = lineup_comparisons(result, side, _admissions=admissions).get(horizon) or {}
            value = admitted.get('delta')
            weeks = ', '.join(map(str, admitted.get('weeks') or []))
            title += (' · Season ' + str(admitted['season']) if admitted.get('season') else '') + (' · weeks ' + weeks if weeks else '')
            key = add(f'{side}.{horizon}', f'{label} · {title} optimal-lineup change', value, unit='fantasy points', state=A.PARTIAL if admitted.get('state') == 'provisional' else None)
            if side == 'active':
                active_impact_keys.append(key)
                active_impacts.append(f"{title}: {manager_points(value)}" + (" (conditional availability)" if admitted.get("state") == "provisional" else ""))
            if row.get('weeks_requested') is not None:
                add(f'{key}.coverage', f'{label} · {title} requested / supported before / supported after weeks',
                    ' / '.join(', '.join(map(str, row.get(field) or [])) or 'none' for field in
                               ('weeks_requested', 'pre_supported_weeks', 'post_supported_weeks')), unit='week identities')
            if row.get('availability') in ('partial', 'partial_or_unavailable'):
                limits.append(Statement('PARTIAL_PROJECTION_EVIDENCE', f'{label} · {title} has incomplete week coverage.', (key,)))
            if admitted.get('subtotal') is not None and admitted.get('delta') is None:
                add(f'{key}.subtotal', f'{label} · {title} comparable-week subtotal only',
                    admitted['subtotal'], unit='fantasy points', state=A.PARTIAL)
        admitted_weekly = admissions[side]['weekly']
        for week, row in sorted(admitted_weekly.items()):
            context = ('Season ' + str(row['season']) + ' · ' if row.get('season') else '') + 'selected league scoring · '
            for phase, title in (('pre', 'Before trade'), ('post', 'After trade')):
                add(f'weekly.{side}.{week}.{phase}', f'{label} · {context}Week {week} · {title} optimal total',
                    row.get(phase), unit='fantasy points', state=A.PARTIAL if row['state'] != 'supported' else None)
            add(f'weekly.{side}.{week}.delta', f'{label} · {context}Week {week} · Optimal-lineup change',
                row['delta'], unit='fantasy points', state=A.PARTIAL if row['state'] == 'provisional' else None)
        for week, change in (strategy.get('reserve_slot_changes') or {}).items():
            add(f'{side}.depth.{week}', f'{label} · week {week} reserve coverage change', change if (admitted_weekly.get(int(week)) or {}).get('delta') is not None else None, unit='supported reserve slots')
        for week, row in (strategy.get('reserve_quality_by_week') or {}).items():
            for field, title in (('pre_points', 'before trade'), ('post_points', 'after trade'), ('delta', 'change')):
                add(f'{side}.reserve_quality.{week}.{field}', f'{label} · Week {week} · Legal reserve production {title}',
                    row.get(field) if (admitted_weekly.get(int(week)) or {}).get({'pre_points': 'pre', 'post_points': 'post', 'delta': 'delta'}[field]) is not None else None, unit='fantasy points',
                    state=A.PARTIAL if row.get('conclusion_state') == 'provisional' else None)
            for limitation in row.get('limitations') or []:
                statement = Statement('RESERVE_PRODUCTION_QUALIFIED', f'{label} · Week {week}: {limitation}',
                                      (f'{side}.reserve_quality.{week}.delta',))
                if statement not in limits:
                    limits.append(statement)
        for direction in ('received', 'sent'):
            for index, pick in enumerate((strategy.get('future_capital') or {}).get(direction) or []):
                add(f'{side}.capital.{direction}.{index}', f'{label} future capital {direction}', pick.get('asset_id'), unit='pick identity')
        for code in strategy.get('reason_codes') or [] if side_verified else []:
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
    partner_verified = admissions['partner']['identity_state'] == 'compatible' and not admissions['partner']['invalid_comparison']
    for code in partner.get('reason_codes') or [] if partner_verified else []:
        row = reason(code, key)
        if row:
            partner_reasons.append(row)
    if partner_reasons:
        advanced.extend(partner_reasons)
        why = why[:2] + [Statement('COUNTERPARTY_RATIONALE', 'Why they may consider it: ' + partner_reasons[0].text, (key,))]
    elif partner.get('explanation') and partner_verified:
        why = why[:2] + [Statement('COUNTERPARTY_RATIONALE', 'Why they may consider it: ' + partner['explanation'], (key,))]
    if partner.get('explanation') and partner_verified:
        advanced.append(Statement('COUNTERPARTY_CONTEXT', partner['explanation'], (key,)))
    confidence = dims.get('confidence') or {}
    add('confidence', 'Evidence support, not acceptance probability', confidence.get('assessment'))
    confidence_rows = (Statement('EVIDENCE_SUPPORT', confidence['explanation'], ('confidence',)),) if confidence.get('explanation') else ()
    for code in result.get('major_risks') or []:
        if code not in REASONS:
            continue
        key = add(f'risk.{code}', 'Accepted risk', reason_text(code), kind=K.INTERPRETATION)
        row = reason(code, key)
        if row:
            risks.append(row)
    drawback = result.get('major_drawback')
    if market_state != 'full' or not production_verified:
        from services.trade_decision import decision_context
        drawback = decision_context(result, _admissions=admissions)['main_cost']
    if drawback:
        key = add('major_drawback', 'Personal decision drawback' if personal else 'Qualified main drawback' if market_state != 'full' else 'Canonical major drawback', drawback, kind=K.INTERPRETATION)
        risks.insert(0, Statement('CANONICAL_MAJOR_DRAWBACK', drawback, (key,)))
    return Explanation('Custom DTOS personal assessment' if personal else 'DTOS trade assessment', league_id, (ctx,), tuple(evidence), conclusion,
                       tuple(why[:3]), tuple(risks[:3]), confidence_rows, tuple(limits), tuple(advanced))


def render_trade_explanation(result: dict, *, league_id: str, _slot_details=True) -> str:
    """Use the shared renderer; weekly rows are optional presentation detail."""
    from src.ui.explanations import explanation_panel
    admissions = completed_lineup_admissions(result)
    from services.trade_lineup_detail import lineup_detail_view, render_lineup_details, render_lineup_risks
    slot_view = lineup_detail_view(result, admissions=admissions) if _slot_details else None
    slot_detail = render_lineup_details(result, admissions=admissions, view=slot_view) if _slot_details else ''
    slot_risks = render_lineup_risks(result, slot_view) if _slot_details else ''
    view = trade_explanation(result, league_id=league_id, _admissions=admissions)
    weekly = tuple(item.key for item in view.evidence if item.key.startswith('weekly.'))
    rendered = explanation_panel(view, evidence_groups=(('Weekly optimal-lineup detail', weekly),) if weekly else ())
    from services.trade_decision import decision_context
    presentation = decision_context(result, _admissions=admissions, _lineup_view=slot_view)
    admission = admissions['active']
    # The completed DTO may include supported asset-age and incoming status
    # context supplied by the producer. Keep it when production still verifies;
    # never restore stale source-dependent rationale after an admission failure.
    if admission['identity_state'] == 'compatible' and not admission['invalid_comparison']:
        for key in ('main_cost', 'limitation'):
            saved = (result.get('decision_context') or {}).get(key)
            if saved:
                presentation[key] = saved
    decision = presentation if result.get('decision_context') else None
    multiweek = any(
        name != 'current_week' and row.get('delta') is not None and len(row.get('weeks') or []) > 1
        for side in admissions.values() for name, row in side['horizons'].items()
    )
    period_units = ('<p class="tw-horizon-units">Expanded weekly totals retain up to four decimals; decision summaries use two. '
                    'Next-N and longer-period changes are totals across the listed weeks, not per-week averages. '
                    'Team summaries labeled Average are per-week averages.</p>') if multiweek else ''
    if presentation and presentation.get('qualification'):
        qualifier = '<span class="tw-verdict-qualification">' + escape(presentation['qualification']) + '</span>'
        rendered = rendered.replace('</p>', qualifier + '</p>', 1)
    # Reuse completed canonical conclusions; no new bilateral scoring or inferred benefit.
    teams = []
    dims = result.get('dimensions') or {}
    for side, title, reason in (('active', 'Your team · gains and sacrifices', 'why_you_would_do_it'),
                                ('partner', 'Their team · benefits and costs', 'why_they_would_do_it')):
        quality = (dims.get('package_quality') or {}).get(side) or {}
        admitted = admissions[side]
        verified = admitted['identity_state'] == 'compatible' and not admitted['invalid_comparison']
        context = (result.get(reason) or 'No supported team-specific rationale is established.') if verified else 'The recorded roster-production rationale cannot be verified; inspect independently supported periods.'
        tradeoff = (quality.get('explanation') or 'Package trade-offs are unavailable.') if verified else 'Package-production trade-offs cannot be verified in this source context; supported Market and capital facts remain separate.'
        weekly = manager_points(admitted['mean_weekly_delta'])
        weeks = ', '.join(map(str, admitted['weeks_counted_once'])) or 'none'
        teams.append('<section><h4>' + title + '</h4><p>' + escape(context) + '</p><p>Average optimal-lineup change across supported weeks ' + escape(weeks) + ': ' + escape(weekly) + '</p><details><summary>Package trade-offs</summary><p>' + escape(tradeoff) + '</p></details></section>')
    summary = '<section class="tw-team-summary" aria-label="Both teams assessment">' + ''.join(teams) + '</section>'
    risk_start = rendered.find('<h4>Trade-off / risk</h4>')
    risk = ''
    if risk_start >= 0:
        risk_end = rendered.index('</ul>', risk_start) + len('</ul>')
        risk = rendered[risk_start:risk_end]
        rendered = rendered[:risk_start] + rendered[risk_end:]
    legacy = rendered.replace('</p>', '</p>' + risk + summary, 1)
    if not decision:
        return legacy.replace('<p>', '<p class="tw-final-verdict">', 1).replace(
            '</section>', slot_risks + slot_detail + '</section>', 1)
    # Preserve the complete established explanation behind depth-on-demand.
    # The verdict and all material costs/qualifications stay in the primary flow.
    split = legacy.index('</p>') + len('</p>')
    primary = _decision_primary(result, decision, admissions)
    return (legacy[:split].replace('<p>', '<p class="tw-final-verdict">', 1) + primary
            + slot_risks + slot_detail
            + '<details class="tw-evaluation-detail"><summary>Full team, weekly and evaluator evidence</summary>'
            + period_units + legacy[split:-len('</section>')] + '</details></section>')


def _decision_primary(result, decision, admissions=None):
    admissions = admissions or completed_lineup_admissions(result)
    def paragraph(text, css=''):
        return '<p' + (f' class="{css}"' if css else '') + '>' + escape(plain_reason(text)) + '</p>' if text else ''
    market = result.get('market_evidence') or {}
    sent, received = (market.get('sent') or {}).get('total'), (market.get('received') or {}).get('total')
    full = market.get('availability') == 'full' and sent is not None and received is not None
    market_html = '<section class="tw-decision-market" aria-label="Current Market comparison"><h4>Current Market</h4>'
    def shown_side(name):
        side = market.get(name) or {}
        if full:
            return manager_points(side['total'])
        subtotal = side.get('known_subtotal')
        return 'Incomplete · known ' + manager_points(subtotal) if subtotal is not None else 'Unavailable'
    market_html += '<div class="tw-market-caption"><span>You send <b>' + escape(shown_side('sent')) + '</b></span><span>You receive <b>' + escape(shown_side('received')) + '</b></span></div>'
    if full:
        gap = market.get('difference')
        sentence = ('Current Market totals are equal.' if gap == 0 else
                    f'You receive {manager_points(abs(gap))} more current Market value.' if gap is not None and gap > 0 else
                    f'Your counterparty receives {manager_points(abs(gap))} more current Market value.' if gap is not None else 'Current Market difference unavailable.')
        share = sent / (sent+received) * 100 if sent+received > 0 else 50
        left, right = ('advantage', 'disadvantage') if sent > received else ('neutral','neutral') if sent == received else ('disadvantage','advantage')
        market_html += ('<div class="tw-market-bar" role="img" aria-label="' + escape(sentence, quote=True) + '">'
                        f'<span class="{left}" style="flex-basis:{share:.3f}%"></span><span class="{right}" style="flex-basis:{100-share:.3f}%"></span></div>'
                        + paragraph(sentence))
    else:
        market_html += paragraph('Known individual prices remain available; no complete comparable package total or advantage is established.')
    market_html += '<small>Current values, not trade-date grades. Market advantage is separate from strategy and lineup impact.</small></section>'
    # Partial/retained callers can have supported Market evidence without the
    # new lead. Omit missing prose instead of inventing it or dropping prices.
    lead = ''
    if decision.get('decisive_reason') or decision.get('decision_next_step'):
        lead = '<section class="tw-decision-lead" aria-label="Decision and next step">'
        if decision.get('decisive_reason'):
            lead += paragraph('Why this decision: ' + decision['decisive_reason'])
        if decision.get('decision_next_step'):
            lead += paragraph('Next step: ' + decision['decision_next_step'])
        lead += '</section>'
    brief = '<section class="tw-decision" aria-label="Trade decision summary">' + lead + market_html
    final = final_decision(result, _admissions=admissions)
    if not final['qualified'] and final['side_assessment'] in ('SMASH ACCEPT', 'WORTH PURSUING'):
        brief += paragraph('Your-side assessment only: ' + final['side_assessment'] + '. Both teams have not passed the trade checks.', 'tw-side-assessment')
    # One principal cost and the admitted current-week effect lead. Longer
    # periods, reserve qualifications and manager-fit conditions remain below.
    for value in dict.fromkeys(filter(None, (decision.get('blocker'), decision.get('main_cost'), decision.get('limitation')))):
        brief += paragraph(value, 'tw-drawback')
    brief += '<section class="tw-team-summary" aria-label="Current projected lineup effects">'
    for key, title in [('your_side_summary', 'Your team'), ('their_side_summary', 'Their team')]:
        lines = (decision.get(key) or '').splitlines()
        brief += '<section><h4>' + title + '</h4>' + paragraph(lines[0] if lines else 'The projected lineup effect is not established.') + '</section>'
    brief += '</section>' + paragraph(decision.get('next_action'))
    brief += '<details class="tw-team-impact-details"><summary>Both teams · depth, costs and conditions</summary>'
    for key, title in [('your_side_summary', 'Your team'), ('their_side_summary', 'Their team')]:
        brief += '<h4>' + title + '</h4>'
        for line in dict.fromkeys((decision.get(key) or '').splitlines()[1:]):
            brief += paragraph(line)
    for key in ('decision_conditions', 'evidence_next_action'):
        for line in dict.fromkeys((decision.get(key) or '').splitlines()):
            brief += paragraph(line, 'tw-drawback' if key == 'decision_conditions' else '')
    partner = (result.get('dimensions') or {}).get('league_partner_context') or {}
    partner_admission = admissions['partner']
    partner_supported = partner_admission['identity_state'] == 'compatible' and not partner_admission['invalid_comparison']
    brief += paragraph('Their principal cost: ' + partner['current_cost'] if partner.get('current_cost') and partner_supported else None)
    if decision.get('conditional'):
        brief += '<h4>Other supported considerations</h4>' + ''.join(paragraph(t) for t in decision['conditional'])
    brief += '</details>'
    facts = result.get('player_facts') or {}
    if facts:
        brief += '<details class="tw-player-facts"><summary>Player production, projections and rank definitions</summary>'
        for row in facts.values():
            projection, production = row['projection'], row['production']
            brief += '<section><h4>' + escape(row['name']) + '</h4>'
            brief += paragraph(f"{row['position']} · {row.get('nfl_team') or 'NFL team unavailable'} · Age {row['age'] if row['age'] is not None else 'unavailable'} · {row['status']}")
            brief += paragraph('Listed position eligibility: ' + ', '.join(row['eligible_positions']) + '. Availability and roster rules are assessed separately in the legal lineup.')
            brief += paragraph(f"Market positional rank: {row['market_rank']['rank'] or 'Unavailable'} · {row['market_rank']['cohort']}.")
            brief += paragraph(f"Current Market: {row['current_market'] if row['current_market'] is not None else 'Unavailable'}.")
            brief += paragraph(f"Sleeper projection: {projection.get('display') or 'Unavailable'} · Season {projection['season']} · Week {projection['week']} · {projection['freshness']}.")
            if projection.get('retained_qualification') not in (None, 'Fresh', projection['freshness']):
                brief += paragraph('Publication qualification: ' + projection['retained_qualification'])
            if (projection.get('refresh_evidence') or {}).get('retained_publication'):
                brief += paragraph('Using retained projection evidence; latest refresh did not complete.')
            brief += paragraph(projection.get('reason') or projection.get('display_reason'))
            brief += paragraph(f"Sleeper actual production: {actual_display(production.get('points_per_observation'))} points per completed-week score observation · {production.get('sample_observations') if production.get('sample_observations') is not None else 'Unknown'} observations · Season {production['season']} · Selected league. This is not a games-played average.")
            brief += paragraph('Season fantasy-points rank / points-per-game rank: unavailable; no complete compatible cohort is prepared.')
            brief += '<details><summary>Player fact sources and coverage</summary>'
            brief += paragraph(f"Projection source observation: {projection.get('source_observed_at') or 'Unknown'}; source generation: {projection.get('generation') or 'Unavailable'}.")
            brief += paragraph(projection.get('retained_qualification'))
            brief += paragraph(f"Actual production source: {production.get('source') or 'Unavailable'}; league {production['league_id']}; generation {production.get('generation') or 'Unavailable'}; observation {production.get('observed_at') or 'Unknown'}.")
            brief += ''.join(paragraph(t) for t in production['limitations']) + '</details></section>'
        brief += '</details>'
    return brief + '</section>'
