"""Session-local Shop search policy. No prices, grades or trade assessments."""
PREFERENCES = ('best_overall', 'win_now', 'youth_rebuild', 'draft_capital', 'position_need', 'custom')


def preference(payload):
    value = payload.get('shop_preference', 'best_overall')
    if value not in PREFERENCES:
        raise ValueError('Unsupported Shop preference; choose one supported session preference.')
    position = str(payload.get('shop_position') or '').upper()
    if value == 'position_need' and position not in ('QB', 'RB', 'WR', 'TE'):
        raise ValueError('Position Need requires QB, RB, WR or TE.')
    if value != 'position_need' and position:
        raise ValueError('A position constraint requires the Position Need preference.')
    return {'name': value, 'position': position or None,
            'persistence': 'request_only',
            'limitations': ['Longevity and liquidity forecasts remain unavailable; age is descriptive, not future utility.']
            if value == 'youth_rebuild' else []}


def discover(workspace, partner_ids, target, pref, excluded):
    """Conservative structural discovery, not a prediction of buyer willingness.

    Unknown strategic evidence does not eliminate a roster. Final credible
    markets exist only after proposal-level bilateral evaluation.
    """
    rows = []
    for rid in partner_ids:
        pool = [a for a in workspace['pools'][rid] if a.asset_id not in excluded and a.trade_value is not None]
        reasons = []
        if not pool:
            reasons.append('NO_SUPPORTED_RETURN_MARKET_EVIDENCE')
        if pref['name'] == 'draft_capital' and not any(a.kind == 'pick' for a in pool):
            reasons.append('NO_OWNED_PRICED_PICK_RETURN')
        if pref['name'] == 'position_need' and not any(a.position == pref['position'] for a in pool):
            reasons.append('NO_OWNED_POSITION_RETURN')
        rows.append({'roster_id': rid, 'discovered': not reasons, 'reasons': reasons,
                     'shopped_asset_id': target.asset_id, 'shopped_position': target.position,
                     'priced_return_assets': len(pool),
                     'competitive_window': workspace.get('competitive_windows', {}).get(str(rid)),
                     'buyer_plausibility': 'not_assessed_until_shared_evaluation'})
    return rows


def ranking_evidence(row, assets):
    evaluation = row['evaluation']
    dimensions = evaluation.get('dimensions') or {}
    strategy = (dimensions.get('strategic_fit') or {}).get('active') or {}
    package = (dimensions.get('package_quality') or {}).get('active') or {}
    ids = set(package.get('incoming_lineup_contributors') or [])
    incoming = [assets[pid] for pid in row['proposal']['assets_received']]
    contributors = [a for a in incoming if a.kind == 'player' and a.asset_id.removeprefix('player:') in ids]
    ages = [a.age for a in contributors if getattr(a, 'age', None) is not None and a.age > 0]
    return {'recommendation': evaluation.get('recommendation'),
            'plausibility': (dimensions.get('counterparty_plausibility') or {}).get('assessment'),
            'confidence': (dimensions.get('confidence') or {}).get('assessment'),
            'package_quality': package.get('assessment'),
            'horizons': {name: h.get('delta') for name, h in strategy.get('horizons', {}).items()},
            'depth_by_week': strategy.get('reserve_slot_changes') or {},
            'package_reason_codes': package.get('reason_codes') or [],
            'lineup_loss_weeks': package.get('loss_weeks') or [],
            'contributing_positions': sorted({a.position for a in contributors if a.position}),
            'contributor_mean_age': sum(ages) / len(ages) if ages and len(ages) == len(contributors) else None,
            'future_capital': (strategy.get('future_capital') or {}).get('received') or [],
            'longevity': strategy.get('longevity'), 'liquidity': strategy.get('liquidity')}


def rank_returns(rows, assets, pref):
    """Explicit lexicographic preference ordering; shared assessment unchanged."""
    decorated = []
    def descending(value):
        return (value is None, -value if value is not None else 0)
    for row in rows:
        evidence = ranking_evidence(row, assets)
        horizons = evidence['horizons']
        quality = {'SMASH ACCEPT': 0, 'WORTH PURSUING': 1, 'FAIR / OPTIONAL': 2}.get(evidence['recommendation'], 3)
        plausibility = {'STRONG': 0, 'PLAUSIBLE': 1}.get(evidence['plausibility'], 2)
        confidence = {'HIGH': 0, 'MEDIUM': 1}.get(evidence['confidence'], 2)
        impact = tuple(descending(horizons.get(name)) for name in ('current_week', 'next_n', 'rest_of_regular_season', 'playoff_window'))
        depth = evidence['depth_by_week']
        # Slot-weeks are coverage evidence, not a monetary or dynasty score.
        depth_order = descending(sum(depth.values()) if depth else None)
        base = (quality, plausibility, confidence, len(evidence['lineup_loss_weeks']))
        name = pref['name']
        if name == 'position_need' and pref['position'] not in evidence['contributing_positions']:
            continue  # A position label alone is not supported lineup utility.
        if name == 'draft_capital' and not evidence['future_capital']:
            continue
        if name == 'win_now' or name == 'position_need':
            key = (impact, depth_order, base)
        elif name == 'draft_capital':
            key = (base, -len(evidence['future_capital']), impact)
        elif name == 'youth_rebuild':
            age = evidence['contributor_mean_age']
            key = (base, age is None, age if age is not None else 0, -len(evidence['future_capital']), impact)
        else:
            key = (base, impact, depth_order)
        decorated.append((key, row['evaluation']['provenance']['evaluation_id'], row, evidence))
    decorated.sort(key=lambda item: (item[0], item[1]))
    return [(row, evidence) for _, _, row, evidence in decorated]
