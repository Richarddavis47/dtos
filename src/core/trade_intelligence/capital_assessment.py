"""Observable capital and explicit strategy rules; never an asset-price modifier."""
from decimal import Decimal


def pick_identity_errors(asset):
    if asset.kind != 'pick':
        return []
    errors = []
    if asset.current_owner_id is not None and asset.current_owner_id != asset.source_roster_id:
        errors.append(f'pick_owner:{asset.asset_id}')
    if all(value is not None for value in (asset.season, asset.round, asset.original_roster_id)):
        expected = f'{asset.season}-R{asset.round}-{asset.original_roster_id}'
        if asset.asset_id != expected or asset.round < 1:
            errors.append(f'pick_identity:{asset.asset_id}')
    return errors


def resolve_strategy(explicit, window=None):
    value = str(explicit or '').strip().upper().replace('_', ' ').replace('-', ' ')
    if value in ('WIN NOW', 'RETOOL', 'REBUILD'):
        return {'strategy': value, 'source': 'explicit_manager'}
    classification = (window or {}).get('classification')
    defaults = {'Elite Contender': 'WIN NOW', 'Contender': 'WIN NOW', 'Playoff Team': 'WIN NOW',
                'Re-tooling': 'RETOOL', 'Rebuilding': 'REBUILD', 'Full Rebuild': 'REBUILD'}
    return {'strategy': defaults.get(classification),
            'source': 'canonical_competitive_window' if classification in defaults else 'unavailable'}


def production_evidence(impact):
    """A union of weekly observations, not a sum of overlapping horizon totals."""
    weekly = (impact or {}).get('weekly') or {}
    rows = {int(week): row for week, row in weekly.items() if row.get('delta') is not None}
    deltas = [Decimal(str(row['delta'])) for row in rows.values()]
    baseline = [((row.get('pre') or {}).get('optimal') or {}).get('projected_points') for row in rows.values()]
    average = float(sum(deltas, Decimal(0)) / len(deltas)) if deltas else None
    pre_average = sum(baseline) / len(baseline) if baseline and all(p is not None for p in baseline) else None
    threshold = max(1.0, (pre_average or 0) * .03)
    return {'weeks_counted_once': sorted(rows), 'mean_weekly_delta': average,
            'pre_mean_weekly_points': pre_average, 'material_weekly_threshold': threshold,
            'material_gain': average is not None and average >= threshold,
            'material_loss': average is not None and average <= -threshold,
            'meaning': 'unique supported optimal-lineup weeks; picks have no projected points'}


def assess_capital(strategy, package, market, *, outgoing_total, incoming_total):
    capital = strategy['future_capital']
    received, sent = capital['received'], capital['sent']
    picks = received + sent
    missing = [p['asset_id'] for p in picks if p['market_price'] is None
               or p['year'] is None or p['round'] is None or p['original_franchise'] is None
               or p['canonical_owner'] is None]
    full = not missing
    received_value = float(sum((Decimal(str(p['market_price'])) for p in received), Decimal(0))) if full else None
    sent_value = float(sum((Decimal(str(p['market_price'])) for p in sent), Decimal(0))) if full else None
    net = float(Decimal(str(received_value)) - Decimal(str(sent_value))) if full else None
    material = max(100.0, (outgoing_total or 0) * .10)
    assessment = {'availability': 'supported' if full else 'unavailable',
                  'received_market_value': received_value, 'sent_market_value': sent_value,
                  'net_market_value': net, 'material_capital_threshold': material,
                  'meaningful_gain': net is not None and net >= material,
                  'meaningful_cost': net is not None and net <= -material,
                  'missing_asset_ids': missing, 'utility_delta': None,
                  'meaning': 'canonical priced capital movement; no future points or class-quality forecast'}
    capital['assessment'] = assessment
    production = strategy['production_evidence']
    intent = strategy['manager_strategy']['strategy']
    ratio = (incoming_total / outgoing_total if outgoing_total else (1.0 if incoming_total == 0 else None)) if incoming_total is not None else None
    fit = {'recommendation': None, 'reason_code': 'FUTURE_CAPITAL_TRADEOFF_UNRESOLVED',
           'explanation': 'Required capital, Market, legal-lineup or strategy evidence is unavailable.',
           'market_return_ratio': ratio,
           'policy': {'rebuild_min_return_ratio': .80, 'win_now_min_return_ratio': .65,
                      'retool_min_return_ratio': .85, 'severe_market_loss_ratio': .50}}
    if (not full or market['availability'] != 'full' or not strategy['projection_coverage_complete']
            or production['mean_weekly_delta'] is None
            or (strategy.get('roster_capacity') or {}).get('additional_spots_to_resolve')):
        return fit
    def decision(label, code, explanation):
        fit.update(recommendation=label, reason_code=code, explanation=explanation)
        return fit
    if ratio is not None and ratio < .50:
        return decision('REJECT', 'SEVERE_MARKET_LOSS', 'The return loses more than half the canonical Market value; a weak positive signal does not compensate for this cost.')
    if package['assessment'] == 'POOR':
        return decision('NOT WORTH IT', 'POOR_STRATEGIC_PACKAGE', 'Supported package quality is poor; draft capital does not erase the lineup and roster costs.')
    mean = production['mean_weekly_delta']
    horizon_losses = any(h.get('delta') is not None and h['delta'] < 0 for h in strategy['horizons'].values())
    horizon_gains = any(h.get('delta') is not None and h['delta'] > 0 for h in strategy['horizons'].values())
    depth_loss = any(d < 0 for d in strategy['reserve_slot_changes'].values())
    if mean == 0 and not horizon_losses and not horizon_gains and net == 0 and incoming_total == outgoing_total and not depth_loss:
        return decision('FAIR / OPTIONAL', 'CAPITAL_AND_LINEUP_PARITY', 'Supported Market, production and draft capital are balanced.')
    if intent is None:
        return fit
    if intent == 'REBUILD' and assessment['meaningful_gain'] and ratio is not None and ratio >= .80:
        weekly_losses = any(row.get('delta') is not None and row['delta'] < 0
                            for row in strategy['horizons'].values())
        cost = ('You give up current production' if mean < 0 else
                'Production has supported losses in some horizons' if weekly_losses else 'Current production is preserved')
        label = 'SMASH ACCEPT' if mean >= 0 and not horizon_losses and not depth_loss and incoming_total >= outgoing_total else 'WORTH PURSUING'
        return decision(label, 'REBUILD_CAPITAL_FIT', f'Rebuild fit: {cost.lower()} while gaining meaningful priced future capital. Reserve coverage and pick-range uncertainty remain explicit.')
    if intent in ('WIN NOW', 'RETOOL') and production['material_gain'] and not horizon_losses and ratio is not None and ratio >= (.65 if intent == 'WIN NOW' else .85):
        cost = 'This costs future flexibility' if net < 0 else 'Future capital is preserved or increased'
        label = 'SMASH ACCEPT' if net >= 0 and incoming_total >= outgoing_total and not depth_loss else 'WORTH PURSUING'
        return decision(label, 'WIN_NOW_PRODUCTION_FIT' if intent == 'WIN NOW' else 'RETOOL_PRODUCTION_FIT',
                        f'{"Win-now" if intent == "WIN NOW" else "Retool"} fit: {cost.lower()}, and materially improves the optimal legal lineup. Any reserve loss remains a disclosed cost.')
    if intent == 'RETOOL' and assessment['meaningful_gain'] and mean >= 0 and not horizon_losses and ratio is not None and ratio >= .85:
        return decision('WORTH PURSUING', 'RETOOL_CAPITAL_FIT', 'Retool fit: meaningful future capital is gained while preserving supported current production.')
    if (intent == 'RETOOL' and ratio is not None and .85 <= ratio <= 1.15
            and assessment['meaningful_gain'] and not production['material_loss'] and not horizon_gains and not depth_loss):
        return decision('FAIR / OPTIONAL', 'RETOOL_BALANCED_EXCHANGE', 'Retool fit: a modest current-production cost buys meaningful future capital at broadly balanced Market terms.')
    return decision('NOT WORTH IT', 'STRATEGY_COST_WITHOUT_MATERIAL_BENEFIT',
                    f'{intent.title()} fit is weak: the supported benefit does not justify the production, capital or Market cost under this strategy.')
