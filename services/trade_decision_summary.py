"""Two-sided presentation of already-admitted evidence. No policy or source work."""
from services.trade_lineup_evidence import number


def decision_summary(result, admissions):
    dims = result.get('dimensions') or {}
    fit = dims.get('strategic_fit') or {}
    partner = dims.get('counterparty_plausibility') or {}
    market = result.get('market_evidence') or {}
    missing = []
    summaries = {}
    for side, title in [('active', 'Your team'), ('partner', 'Their team')]:
        view = admissions[side]
        current = view['horizons'].get('current_week') or {}
        season = current.get('season')
        weeks = current.get('weeks') or []
        prefix = f'Season {season}, ' if season else ''
        delta = current.get('delta')
        lines = [f'{title}: ' + (
            f"{'Conditional ' if current.get('state') != 'supported' else ''}{prefix}week {', '.join(map(str, weeks))} optimal-lineup change {delta:+.2f} projected points."
            if number(delta) else f"{prefix}current-week legal-lineup change cannot be verified."
        )]
        average = view['mean_weekly_delta']
        if number(average):
            counted = ', '.join(map(str, view['weeks_counted_once']))
            conditional = any(view['weekly'][w].get('state') != 'supported' for w in view['weeks_counted_once'])
            lines.append(f"{'Conditional average' if conditional else 'Average'} across supported weeks {counted}: {average:+.2f} projected points per week; not a season forecast.")
        else:
            requested = sorted({w for h in view['horizons'].values() for w in h.get('weeks') or []})
            missing_weeks = [w for w in requested if (view['weekly'].get(w) or {}).get('delta') is None]
            label = ', '.join(map(str, missing_weeks)) or 'the requested period'
            lines.append(f'Comparable before/after lineup evidence is incomplete for {label}; a production benefit or sacrifice cannot be established for the full request.')
            missing.append(f"{title}'s compatible player-week projections and legal pre/post lineups")
        requested = sorted({w for h in view['horizons'].values() for w in h.get('weeks') or []})
        uncovered = [w for w in requested if (view['weekly'].get(w) or {}).get('delta') is None]
        if uncovered and number(average):
            lines.append('Before/after lineup evidence remains missing for weeks ' + ', '.join(map(str, uncovered)) + '; the supported-week average does not fill that gap.')
            missing.append(f"{title}'s compatible player-week projections and legal pre/post lineups")
        sent = (market.get('sent') or {}).get('total')
        received = (market.get('received') or {}).get('total')
        if market.get('availability') == 'full' and number(sent) and number(received):
            give, take = (sent, received) if side == 'active' else (received, sent)
            lines.append(f'Neutral Market: {give:g} sent / {take:g} received; this is value compensation, not acceptance evidence.')
        profile = fit.get(side) or {}
        reserve = profile.get('reserve_quality') or {}
        if reserve.get('complete') and number(reserve.get('mean_weekly_delta')):
            lines.append(f"Useful replacement production changes {reserve['mean_weekly_delta']:+.2f} points per supported week.")
        elif reserve.get('material_loss'):
            lines.append('Supported replacement depth is lost; review the weekly reserve evidence.')
        if reserve.get('complete') is not True:
            lines.append('Useful replacement-depth coverage is incomplete; a missing reserve effect is not zero.')
            missing.append(f"{title}'s compatible reserve-depth evidence")
        capital = profile.get('future_capital') or {}
        assessment = capital.get('assessment') or {}
        if capital.get('sent') or capital.get('received'):
            if assessment.get('availability') == 'supported' and number(assessment.get('sent_market_value')) and number(assessment.get('received_market_value')):
                basis = 'Personal Custom future-capital value' if side == 'active' and result.get('personal_value_evidence') else 'Future capital Market value'
                lines.append(f"{basis}: {assessment['sent_market_value']:g} sent / {assessment['received_market_value']:g} received. Picks do not supply projected points; future outcomes are uncertain.")
            else:
                lines.append('Future-capital qualification is incomplete; a balanced Market total does not establish the long-term trade-off.')
                missing.append(f"{title}'s exact pick ownership, compatible price and future-capital qualification")
        summaries[side] = ' '.join(lines)
    strategy = partner.get('manager_strategy') or (fit.get('partner') or {}).get('manager_strategy') or {}
    if strategy.get('source') == 'explicit_manager' and strategy.get('strategy'):
        condition = f"Their saved direction is {strategy['strategy']}; it does not prove willingness to accept this offer."
    elif strategy.get('source') == 'canonical_competitive_window' and strategy.get('strategy'):
        condition = f"Their roster-based direction is {strategy['strategy']}; this is not a confirmed manager intention."
    else:
        condition = 'Their manager strategy is unconfirmed; rebuilding or contending intent is not established.'
    mean = admissions['partner']['mean_weekly_delta']
    if number(mean) and mean < 0:
        condition += ' They give up supported projected production. The offer makes sense only if they prefer the supported asset or capital compensation to that loss; confirm that motivation before treating it as actionable.'
    condition += ' Market fairness and receiving a pick do not establish rebuilding intent or predict acceptance.'
    next_action = ('Review ' + '; '.join(dict.fromkeys(missing)) + '. Wait for compatible evidence or inspect a counterparty with supported coverage; adding a pick cannot fix missing projections.' if missing else
                   'Review both teams’ sacrifices and discuss the stated compensation and direction with the other manager; this is not a prediction of acceptance.')
    if not missing and result.get('generated_trade_eligible') is not True:
        next_action = 'This is not a qualified recommendation. Inspect the stated Market, roster and counterparty blockers before considering a package change.'
    if market.get('availability') != 'full':
        next_action = 'Review the assets missing compatible current Market prices; Neutral and Custom values must remain separate. ' + next_action
    return {'your_side_summary': summaries['active'], 'their_side_summary': summaries['partner'],
            'decision_conditions': condition, 'evidence_next_action': next_action}
