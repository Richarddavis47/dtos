"""Presentation of pinned, already-solved reserve evidence; never a valuation guard."""
from services.trade_lineup_evidence import number


def reserve_phase_evidence(reserve, *, valid, complete_starters, source, identities):
    """Keep a verified subtotal separate from an exact replacement comparison."""
    qualification = reserve.get('qualification') or {}
    state = qualification.get('conclusion_state')
    missing = reserve.get('missing_player_ids') or []
    reasons = []
    if not valid:
        reasons.append('Reserve rows cannot be verified against the owned roster and this week’s scoring publication.')
    else:
        for pid in missing:
            row = (source.get('players') or {}).get(pid) or {}
            name = identities.get(pid) or 'Player identity not resolved'
            if not row:
                reason = 'no compatible player-week record in the prepared publication'
            elif row.get('compatible') is not True:
                reason = 'player-week/scoring evidence is incompatible'
            elif not number(row.get('canonical_projection')):
                reason = 'no numerical projection in the compatible prepared publication'
            elif not (row.get('fantasy_positions') or row.get('position')):
                reason = 'fantasy-position eligibility is missing'
            else:
                reason = 'recorded reserve eligibility or projection coverage is incomplete'
            reasons.append(name + ': ' + reason + '; not a zero-point replacement.')
        if not complete_starters:
            reasons.append('The starting lineup is incomplete; the full disjoint replacement effect cannot be established.')
        if qualification.get('calculation_supported') is not True and not reasons:
            reasons.append('The prepared reserve calculation is not supported; inspect its availability and eligibility qualifications.')
        reasons.extend(qualification.get('limitations') or [])
        # Reuse the same freshness rule as canonical reserve-quality evidence
        # rather than retaining a once-current label after a warm DTO ages.
        from src.core.projection_intelligence.sleeper_provider import freshness_state
        clocks = qualification.get('source_timestamps') or []
        if isinstance(clocks, dict):
            clocks = list(clocks.values())
        if clocks and any(freshness_state(clock) != 'Fresh' for clock in clocks):
            reasons.append('Original projection observations are not confirmed Fresh; replacement production remains conditional.')
            state = 'provisional' if state != 'unavailable' else state
    supported = bool(valid and complete_starters and not missing
                     and qualification.get('calculation_supported') is True
                     and number(reserve.get('known_subtotal')))
    return {'state': 'supported' if supported else 'partial' if valid else 'unavailable',
            'known_subtotal': reserve.get('known_subtotal') if valid else None,
            'points': reserve.get('known_subtotal') if supported else None,
            'supported_slots': reserve.get('supported_slots') if valid else None,
            'candidate_count': reserve.get('candidate_count') if valid else None,
            'missing_player_count': len(missing) if valid else None,
            'unfilled_cover_slots': (reserve.get('unsupported_slots') or []) if valid else [],
            'qualification': state if valid else 'unavailable',
            'reasons': list(dict.fromkeys(reasons))}


def reserve_summary_lines(view, side):
    """Visible decision facts, independently qualified for each side/week/phase."""
    lines = []
    weeks = sorted(view['sides'][side].items())
    # Keep the primary phone card short. Every retained week/phase remains in
    # the existing expanded evidence; no horizon is filled from another week.
    for week, row in weeks[:1]:
        phases = row['phases']
        pre, post = (phases[p]['reserve_evidence'] for p in ('pre', 'post'))
        prefix = f"Season {view['season']}, week {week} reserve cover: "
        def describe(evidence):
            value = evidence['known_subtotal']
            if not number(value):
                return 'unknown'
            label = 'supported' if evidence['state'] == 'supported' else 'known subtotal only'
            return f"{value:.2f} points ({label}, {evidence['supported_slots']} covered reserve slots)"
        lines.append(prefix + 'before ' + describe(pre) + '; after ' + describe(post) + '.')
        # A partial subtotal must never become a full reserve delta or bound.
        if pre['state'] == post['state'] == 'supported':
            from services.trade_lineup_evidence import total
            delta = total([post['points'], -pre['points']])
            conditional = pre['qualification'] != 'current' or post['qualification'] != 'current' or row.get('state') != 'supported'
            lines.append(f"{'Conditional ' if conditional else ''}week {week} reserve-production change: {delta:+.2f} points; not an injury forecast or a second starting lineup.")
        else:
            lines.append(f'Week {week} full reserve change is unknown; partial subtotals are not a before/after replacement comparison.')
        reasons = dict.fromkeys(pre['reasons'] + post['reasons'])
        for reason in reasons:
            phase = 'Before and after' if reason in pre['reasons'] and reason in post['reasons'] else 'Before trade' if reason in pre['reasons'] else 'After trade'
            lines.append(f'Week {week} · {phase}: {reason}')
    if len(weeks) > 1:
        lines.append('Other weekly reserve effects and coverage gaps are listed separately in Before and after · both optimal lineups.')
    return lines
