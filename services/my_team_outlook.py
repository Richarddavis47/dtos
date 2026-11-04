"""A small explanation over prepared evidence, with no acquisition or calculation.

This is not a team grade or a forecast. Scope and coverage remain part of every
claim; selecting a goal changes the next action, never the underlying evidence.
"""
from math import isfinite
from collections import Counter

from src.ui.intelligence_presentation import manager_points


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) else None


def _slot_description(slots):
    labels = {'SUPER_FLEX': 'Superflex', 'SF': 'Superflex', 'REC_FLEX': 'WR/TE FLEX', 'WRRB_FLEX': 'RB/WR FLEX'}
    return ', '.join(f"{count} {labels.get(slot, slot)} slot" + ('s' if count != 1 else '')
                     for slot, count in Counter(slots or []).items())


def _future(data, assessment, players):
    capital = assessment.team.future_capital_evidence or {}
    same = (capital.get('league_id') == assessment.league_id
            and capital.get('roster_id') == assessment.roster_id
            and capital.get('generation') == assessment.generation)
    picks = [row['identity'] for row in capital.get('picks', ())] if same else []
    if same:
        firsts = [p for p in picks if p.get('round') == 1]
        years = sorted({str(p.get('year', p.get('season'))) for p in firsts})
        text = f"{len(picks)} owned picks, including {len(firsts)} first-round " + ('pick' if len(firsts) == 1 else 'picks')
        text += (' (' + ', '.join(years) + ')' if years else '') + '.'
        note = (f"{capital.get('priced_pick_count', 0)}/{len(picks)} picks have compatible Market prices. "
                'Original-franchise identities and current ownership are listed in Draft capital; unknown pick ranges remain unknown.')
    else:
        text = 'Compatible draft-capital ownership evidence is unavailable.'
        note = 'Refresh the league before relying on the capital inventory.'
    # Use supplied ages only. A known birth-date conflict cannot be repaired by
    # the presence of a single convenient numeric age in a presentation object.
    from src.core.data_platform.normalization.birth_dates import birth_date_metadata
    starters = set(assessment.roster_evidence.optimal_starter_ids)
    ages = []
    for player in players:
        if str(player.get('id')) not in starters:
            continue
        status = (player.get('metadata') or {}).get('birth_date_status') or player.get('birth_date_status')
        source = (data.get('players') or {}).get(str(player.get('id'))) or {}
        evidence = birth_date_metadata(player, source)
        age = _number(player.get('age'))
        source_status = (source.get('metadata') or {}).get('birth_date_status') or source.get('birth_date_status')
        if age is not None and age > 0 and not {status, source_status}.intersection({'conflicting', 'invalid', 'identity_mismatch'}) and evidence['birth_date_status'] not in {'conflicting', 'invalid'}:
            ages.append(age)
    age_note = (f"Reported ages cover {len(ages)}/{len(starters)} optimal starters ({manager_points(min(ages))}–{manager_points(max(ages))})."
                if ages else 'Supported starter-age context is unavailable.')
    note += ' ' + age_note + ' Ages and current projections do not establish years remaining or a multi-season forecast.'
    brief = f"{len(picks)} picks/{len(firsts)} " + ('first' if len(firsts) == 1 else 'firsts') if same else 'Capital unconfirmed'
    return text + ' Multi-season sustainability is not established.', note, brief


def goal_options(roster_id):
    """Action choices over the same facts; no inferred direction or new work."""
    options = {
        'WIN NOW': ('WIN NOW: prioritize a supported starter upgrade while checking its replacement-depth and future-capital cost.',
                    'Explore starter upgrades', f'/trades/trade-for?front_office={roster_id}'),
        'REBUILD': ('REBUILD: review exact future capital before exchanging it for short-term production.',
                    'Review your draft capital', '#draft-capital'),
        'RETOOL': ('RETOOL: review useful replacement depth before deciding which assets to move.',
                   'Review replacement depth', '#positional-depth'),
        '': (
        'Select a goal to adjust strategic guidance. Neutral Market values and objective legal-lineup calculations stay unchanged.',
        'Choose your goal', '#my-team-strategy'),
    }
    return {key: dict(guidance=g, action=a, href=h) for key, (g, a, h) in options.items()}


def prepared_outlook(data, assessment, overview, players, *, strategy=''):
    """Format only the assessment already prepared for this My Team request."""
    league = data.get('league') or {}
    evidence = assessment.roster_evidence
    same = (evidence is not None and assessment.league_id == str(league.get('league_id') or '')
            and evidence.league_id == assessment.league_id and evidence.roster_id == assessment.roster_id
            and evidence.generation == assessment.generation and assessment.team.generation == assessment.generation
            and assessment.team.league_id == assessment.league_id and assessment.team.roster_id == assessment.roster_id
            and overview.get('generation') == assessment.generation)
    goal = strategy if strategy in {'WIN NOW', 'RETOOL', 'REBUILD'} else ''
    selected = goal_options(assessment.roster_id)[goal]
    guidance, action, href = selected['guidance'], selected['action'], selected['href']
    if not same:
        return dict(position='Current lineup comparison unavailable: compatible league evidence must be refreshed.',
                    strength='A roster advantage cannot be confirmed from incompatible evidence.',
                    concern='Replacement quality is unconfirmed; unavailable evidence is not poor depth.',
                    future='Compatible future-capital evidence is unavailable.', guidance=guidance,
                    action=action, href=href, brief='Refresh this league to compare lineup, depth and picks. Missing evidence is not a weakness.',
                    details=['Refresh this league before relying on its assessment.'])
    rows = [(pos, facts, facts.get('diagnostic') or {}) for pos, facts in evidence.positions.items()]
    diagnostics = [d for _, _, d in rows if d]
    supported = bool(diagnostics) and all(d.get('evidence', {}).get('calculation_supported') for d in diagnostics)
    fresh = supported and all(d.get('conclusion_state') == 'current' for d in diagnostics)
    week = evidence.projection_week
    same_week = week is not None and week == assessment.projection_week and week == (data.get('week') or 1)
    compatible = (supported and same_week and bool(evidence.projection_generation)
                  and evidence.projection_generation == assessment.projection_snapshot_id)
    rank = assessment.team.starting_lineup
    position = f"Standing {overview['standing']} by Sleeper record/PF. "
    league_name = league.get('name') or 'Selected league'
    if compatible and evidence.optimal_lineup_projection is not None:
        comparison = (f"#{rank.rank} among {rank.league_size} supported franchises ({len(data.get('teams') or [])} total)" if rank.rank is not None else 'comparison rank unavailable')
        qualifier = '' if fresh else 'Provisional: '
        population = 'supported-player optimal lineup' if evidence.projection_covered < evidence.roster_count else 'optimal projected lineup'
        position += (f"{qualifier}Week {week} {population} {comparison}, "
                     f"{manager_points(evidence.optimal_lineup_projection)} points under {league_name} scoring.")
    elif compatible and getattr(evidence, 'unsupported_slots', ()):
        position += (f"Current optimal-lineup comparison unavailable for Week {week}: "
                     f"{_slot_description(evidence.unsupported_slots)} lack supported eligible projections. "
                     'This does not change the official standing.')
    else:
        position += 'Current optimal-lineup comparison unavailable; compatible week, scoring and projections are required.'
    strengths = [pos for pos, _, d in rows if compatible and d.get('strength')]
    if strengths:
        strength = ('Supported' if fresh else 'Provisional') + ' positional strength: ' + ', '.join(strengths) + '. Strength is not automatically expendable depth.'
    else:
        contributions = [(pos, f) for pos, f, _ in rows if compatible and f.get('starting_points') is not None]
        best = max(contributions, key=lambda item: item[1]['starting_points'], default=None)
        strength = (f"{best[0]} supplies the largest supported lineup contribution ({manager_points(best[1]['starting_points'])} points); this is not a positional advantage grade."
                    if best else 'A starting-strength advantage cannot be confirmed from available projections.')
    uncertain = [pos for pos, f, _ in rows if f.get('reserve_covered', 0) < f.get('reserve_expected', 0)]
    needs = sorted(((pos, d) for pos, _, d in rows if d.get('resilience_need') or d.get('quality_depth_need') or d.get('starter_need')),
                   key=lambda item: (not item[1].get('quality_depth_need'), not item[1].get('resilience_need')))
    if not compatible:
        concern = 'Replacement quality is unconfirmed; missing or incompatible projections are not zero production.'
    elif uncertain:
        concern = ', '.join(uncertain) + ' replacement projections are incomplete. Useful depth cannot be fully confirmed.'
    elif needs:
        pos, diagnostic = needs[0]
        # Describe objective flags, not an old goal-specific interpretation.
        # A browser-session goal change must not leave contradictory advice.
        if diagnostic.get('quality_depth_need'):
            concern = f'{pos} legal replacements project below the supported league reserve reference. Review the production cost before moving that cover.'
        elif diagnostic.get('resilience_need'):
            concern = f'{pos} has a legal replacement-coverage gap. Review exact starter-removal scenarios in Depth.'
        else:
            concern = f'A supported {pos} addition improves the legal lineup. Review its Market and future-capital cost under your selected goal.'
        if not fresh:
            concern = 'Provisional: ' + concern
    elif not fresh:
        concern = 'Replacement cover is provisional: availability or projection freshness is not fully verified. Review Depth before moving reserves.'
    else:
        concern = 'No supported replacement shortfall is established. Review exact removal costs before treating depth as expendable.'
    future, capital_note, brief_capital = _future(data, assessment, players)
    brief_position = (f"Week {week} projected lineup #{rank.rank}/{rank.league_size} supported ({len(data.get('teams') or [])} total)"
                      if compatible and rank.rank is not None else 'Lineup comparison needs compatible projections')
    if compatible and not fresh:
        brief_position = 'Provisional ' + brief_position
    brief_strength = (('Supported' if fresh else 'Provisional') + ' strength: ' + '/'.join(strengths)
                      if strengths else '')
    if not compatible or uncertain:
        brief_risk = 'Depth evidence is incomplete; not proof of weak reserves'
    elif needs:
        pos, diagnostic = needs[0]
        brief_risk = pos + (' replacement quality needs attention' if diagnostic.get('quality_depth_need') else
                           ' legal cover needs attention' if diagnostic.get('resilience_need') else ' has a supported starter-upgrade opportunity')
    elif not fresh:
        brief_risk = 'Depth is provisional; review before moving cover'
    else:
        brief_risk = 'No depth gap established; review before selling cover'
    brief = '. '.join(part for part in (brief_position, brief_strength, brief_risk, brief_capital) if part) + '.'
    limits = list(evidence.limitations)
    if not fresh:
        limits.insert(0, 'Some current-week evidence is not fully verified; findings are provisional, not a fresh team verdict. Source and availability limitations follow.')
    details = [overview.get('standing_reason') or 'Standing basis unavailable.', capital_note,
               'Statistical record/PF standing is separate from official playoff qualification and final seeding.',
               f"Projection coverage: {evidence.projection_covered}/{evidence.roster_count} rostered players. This counts player-week numbers, including reserve/taxi players; it is separate from playable starting-slot eligibility. Submitted starters remain separate from the optimal legal lineup.",
               'Current strength is not championship probability or future sustainability.', *limits]
    # TeamAssessment admits this prepared profile through compatible_profile;
    # consume its coverage without another preparation, solver or history read.
    horizon = ((assessment.multi_horizon_strength or {}).get('horizons') or {}).get('current_week') or {}
    comparison = (assessment.multi_horizon_strength or {}).get('current_week_comparison') or {}
    if (compatible and comparison.get('league_id') == assessment.league_id
            and comparison.get('week') == week
            and comparison.get('projection_generation') == (assessment.multi_horizon_strength or {}).get('projection_generation')):
        details.append(f"Lineup comparison: {comparison['supported_count']}/{comparison['league_size']} franchises can fill the configured starting slots with supported eligible projections. "
                       'Incomplete bench coverage alone does not exclude a franchise; this is separate from official standings and full replacement-depth support.')
        names = {str(t.get('roster_id')): t.get('team_name') or t.get('name') for t in data.get('teams') or []}
        for row in comparison.get('excluded') or []:
            label = names.get(str(row['roster_id'])) or f"Franchise {row['roster_id']}"
            slots = _slot_description(row.get('unsupported_slots')) or 'unverified lineup configuration'
            details.append(f"{label}: excluded from this modeled comparison; starting slots without supported eligible players: {slots}. Missing points are not zero.")
    if compatible and horizon.get('weeks_requested') == [week]:
        total = _number(horizon.get('total'))
        details.append(f"Prepared Team Strength covers {len(horizon.get('weeks_supported') or [])}/1 current weeks; "
                       f"complete-horizon points: {manager_points(total)}. Other prepared horizons are projections, not a multi-season sustainability forecast.")
    else:
        details.append('Compatible multi-week Team Strength is not available for this comparison; no missing horizon is filled with zero.')
    if compatible:
        details.extend(f"{pos} reserve projections: {facts['reserve_covered']}/{facts['reserve_expected']}; "
                       f"best supported eligible reserve {manager_points(facts.get('best_reserve_points'))} points. "
                       'See Depth for legal, separate replacement scenarios; one player cannot cover simultaneous absences.'
                       for pos, facts, _ in rows if facts.get('starting_count') or facts.get('reserve_expected'))
    return dict(position=position, strength=strength, concern=concern, future=future,
                guidance=guidance, action=action, href=href, brief=brief, details=list(dict.fromkeys(details)))
