"""Small prepared reads and pure Home composition. No discovery or factories.

The selected goal scopes the assessment cache; objective diagnostics can be reused
across goals. Each family admits its own evidence, independently of Market.
"""
from datetime import datetime, timedelta, timezone
from math import isfinite

from services.team_trade_need import prepared_need
from services.team_assessment_presentation import positional_display_rows
from src.core.intelligence import intelligence_orchestrator
from src.core.intelligence.roster_diagnostics import prepared_diagnostics
from src.core.intelligence.team_strength import compatible_profile
from src.ui.intelligence_presentation import manager_points


def first_action(team, week, review, byes, items, *, now=None):
    """Choose one action from evidence already admitted for this franchise."""
    from src.core.intelligence.lineup_review import timestamp
    now = now or datetime.now(timezone.utc)
    team_url = f'/teams/{team["roster_id"]}'
    lineup = []
    for plan, conditional in ((review.get('fallback') or {}, True), (review, False)):
        kickoff = timestamp(plan.get('kickoff_deadline'))
        expiry = timestamp(plan.get('valid_until'))
        if (kickoff is None or not now < kickoff <= now + timedelta(hours=48)
                or expiry is None or expiry <= now):
            continue
        if conditional and plan.get('starter'):
            title = 'Have a backup ready'
            reason = f'If {plan["starter"]} can’t play, a verified fallback is available before the first affected game.'
        elif not conditional and plan.get('actionable'):
            title = f'Check your Week {week} lineup'
            reason = ('A starting slot is empty and a legal replacement is available.'
                      if plan.get('empty_slots') else
                      'A legal lineup change could add projected points before the first affected game.')
        else:
            continue
        lineup.append((kickoff, dict(title=title, reason=reason, action='Review lineup',
                                     href=team_url + '#lineup-recheck', valid_until=expiry.isoformat(),
                                     verified_at=now.isoformat())))
    if lineup:
        return min(lineup, key=lambda candidate: candidate[0])[1]

    # Account for an earlier bye first. A confirmed vacancy takes precedence
    # over a cover plan in the same week.
    for row in sorted(byes or (), key=lambda row: (row['week'], row['state'] != 'shortfall')):
        if not row.get('bye_starters'):
            continue
        week = row['week']
        affected = {str(pid) for _, pid in row['bye_starters']}
        names = [p.get('name') or p.get('full_name') for p in team.get('players') or []
                 if str(p.get('id')) in affected]
        if len(affected) <= 2 and len(names) == len(affected) and all(names):
            situation = ' and '.join(names) + (' is on bye.' if len(names) == 1 else ' are on bye.')
        else:
            situation = f'{len(affected)} starters are on bye.' if len(affected) > 1 else 'A starter is on bye.'
        title = f'Plan for Week {week} byes'
        if row['state'] == 'shortfall' and row.get('unfilled'):
            reason = 'Your roster can’t fill every starting slot with the confirmed byes.'
        elif row['state'] == 'covered' and row.get('moves'):
            title = f'Set your Week {week} lineup'
            reason = situation + ' Your roster has a legal cover plan.'
        elif row['state'] == 'conditional' and row.get('moves'):
            reason = situation + ' Cover depends on player availability.'
        else:
            continue
        return dict(title=title, reason=reason,
                    action='Review bye plan', href=team_url + '#bye-week-details')

    for families in ({'need', 'offer'}, {'goal'}):
        chosen = next((item for item in items if item['family'] in families), None)
        if chosen:
            from src.ui.home_trade_opportunities import brief_text
            return dict(title=brief_text(chosen['title']), reason=brief_text(chosen['reason']),
                        action=chosen['action'], href=chosen['href'])
    return None


def prepared_first_action(data, roster_id, profile, reader, items):
    league = data.get('league') or {}
    team = next((t for t in data.get('teams') or [] if t.get('roster_id') == roster_id), None)
    if team is None:
        return None
    week = data.get('week')
    review, weeks = {}, None
    if profile and league.get('status') == 'in_season' and type(week) is int:
        from services.matchup_season import season_week_view
        from src.core.intelligence.upcoming_byes import read_upcoming_byes
        weeks = read_upcoming_byes(profile, league, team, players_fetched_at=data.get('players_fetched_at'))
        if profile.get('lineup_review_schedule'):
            view = season_week_view(data, week, reader, review_roster_id=roster_id)
            side = next((side for group in view['groups'].values() for side in group
                         if side['roster_id'] == roster_id), {})
            review = side.get('lineup_review') or {}
    return first_action(team, week, review, weeks, items)


def prepared_evidence(data, roster_id, strategy, *, market_compatible=False):
    context = intelligence_orchestrator.context(data, roster_id, {'strategy': strategy})
    prefix = f'snapshot:{context.snapshot_key}:'
    result = intelligence_orchestrator.cache.peek(prefix + 'result_without_trade_opportunities')
    if result is None:
        result = intelligence_orchestrator.cache.peek(prefix + 'result')
    assessment = result.team_assessment if result else None
    if assessment and (assessment.league_id != context.league_id
                       or assessment.roster_id != roster_id
                       or assessment.generation != context.evidence_generation):
        assessment = None
    diagnostics = prepared_diagnostics(data, context.projection_snapshot)
    trade_need = prepared_need(data, roster_id, diagnostics) if diagnostics else None
    from services.franchise_outlook import franchise_outlook
    outlook = franchise_outlook(data, result, strategy=strategy) if assessment is not None else None
    return {'league_id': context.league_id, 'roster_id': roster_id,
            'strategy': strategy if strategy in {'WIN NOW', 'REBUILD', 'RETOOL'} else '',
            'generation': context.evidence_generation, 'assessment': assessment, 'outlook': outlook,
            'market_compatible': market_compatible,
            'trade_need': trade_need,
            'diagnostics': diagnostics, 'strength': compatible_profile(data, context.projection_snapshot),
            'week': data.get('week'), 'league_name': context.league.get('name') or 'Selected league'}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _item(key, family, title, reason, drawback, action, href, *, issues=(), details=(), **extra):
    return dict(key=key, family=family, title=title, reason=reason, drawback=drawback,
                action=action, href=href, issues=list(issues), details=list(details), **extra)


def select_insights(facts, attention, offers):
    """Deterministic family precedence, never a new numerical team score.

    Offer order is unchanged. Related production concerns travel inside an
    eligible offer only when its evaluator reports the same supported need.
    """
    rid, goal = facts['roster_id'], facts['strategy']
    team_url = f'/teams/{rid}'
    candidates = []
    diagnostics = facts.get('diagnostics') or {}
    own = (diagnostics.get('teams') or {}).get(str(rid)) or {}
    positions = positional_display_rows(own)
    trade_need = facts.get('trade_need') or {}
    profile = facts.get('strength') or {}
    strength = (profile.get('teams') or {}).get(str(rid)) or {}
    weekly = (strength.get('weekly') or {}).get(str(facts['week'])) or (strength.get('weekly') or {}).get(facts['week']) or {}
    optimal = weekly.get('optimal') or {}
    context = (f"Week {facts['week']} best projected starting lineup: {manager_points(optimal['projected_points'])} points using {facts['league_name']} scoring and lineup rules. "
               if optimal.get('available') and _number(optimal.get('projected_points')) else '')
    for pos, d in positions.items():
        evidence = d.get('evidence') or own.get('evidence') or {}
        if not evidence.get('calculation_supported') or d.get('conclusion_state') == 'unavailable':
            continue
        provisional = d.get('conclusion_state') != 'current'
        qualifier = 'Provisional: ' if provisional else ''
        issue = f'position:{pos}'
        starter = d.get('starter_need')
        quality = d.get('quality_depth_need')
        if quality or d.get('resilience_need') or starter:
            title = (f'A supported {pos} addition could improve the lineup' if starter else
                     f'{pos} replacement production needs review' if quality else
                     f'{pos} backup cover needs review')
            reason = context + (d.get('base_reason') or 'Supported starting-lineup and backup comparisons show room to improve.')
            drawback = ('This is a current production gap, not evidence to buy an aging starter under REBUILD.'
                        if goal == 'REBUILD' else
                        'An upgrade has a Market and capital cost; this is not an endorsed trade.')
            handoff = not provisional and trade_need.get('position') == pos
            candidates.append(_item(issue, 'need', qualifier + title, reason, drawback,
                f'Explore {pos} trades' if handoff else 'Review replacement depth',
                trade_need['href'] if handoff else team_url + '#positional-depth', issues=[issue],
                priority=0 if handoff else 1 if starter and not provisional else 2 if not provisional else 3,
                details=[*own.get('limitations', []), *evidence.get('limitations', [])]))
        elif d.get('disjoint_reserve_ids') and any(_number(v) for v in d.get('observed_replacement_points') or []):
            # Useful reserve evidence is not permission to sell; use supported
            # removal scenarios, never headcount or an invented injury model.
            points = manager_points(min(v for v in d['observed_replacement_points'] if _number(v)))
            candidates.append(_item(issue, 'depth', qualifier + f'Keep {pos} replacement production in view',
                f'If a {pos} starter is unavailable, the supported backups offer at least {points} projected replacement points under {facts["league_name"]} scoring in week {facts["week"]}.',
                'Having useful backups does not mean they are safe to trade. These scenarios do not cover simultaneous absences.',
                'Review removal costs', team_url + '#positional-depth', issues=[issue],
                details=own.get('limitations', [])))
    assessment = facts.get('assessment')
    capital = assessment.team.future_capital_evidence if assessment else {}
    capital_action = (facts.get('outlook') or {}).get('capital_action')
    if capital_action:
        capital_action = dict(capital_action)
        # Refresh display names only for exact records already admitted by the
        # independent inventory formatter. Pricing rows cannot add ownership.
        if (capital and capital.get('league_id') == facts['league_id']
                and capital.get('roster_id') == rid and capital.get('generation') == facts['generation']):
            labels = []
            for row in capital.get('picks', ()):
                pick = row.get('identity') or {}
                year, rnd = pick.get('year', pick.get('season')), pick.get('round')
                original, owner = pick.get('original_roster_id'), pick.get('current_owner_id')
                identity = f'{year} round {rnd} · original {original} · owner {owner}'
                if identity in capital_action.get('details', ()):
                    round_label = 'first' if rnd == 1 else f'round {rnd}'
                    labels.append(f"Recorded {year} {round_label} · {pick.get('original_team') or f'original franchise {original}'} · owned by your team")
            capital_action['reason'] = facts['outlook']['future'] + (' ' + '; '.join(labels[:2]) + '.' if labels else '')
        if not facts.get('market_compatible'):
            capital_action['drawback'] = 'Current pick pricing is unconfirmed. ' + capital_action['drawback']
        candidates.append(_item('capital', 'capital', **capital_action, issues=['capital']))
    elif not facts.get('outlook'):
        if (capital and capital.get('league_id') == facts['league_id']
                and capital.get('roster_id') == rid and capital.get('generation') == facts['generation']):
            picks = [p['identity'] for p in capital.get('picks', ())]
            firsts = [p for p in picks if p.get('round') == 1]
            if firsts:
                identities = [f"{p.get('year', p.get('season'))} first · {p.get('original_team') or 'Original franchise ' + str(p.get('original_roster_id'))} (original {p.get('original_roster_id')}) · owner {p.get('current_owner_id')}" for p in firsts]
                labels = [f"{p.get('year', p.get('season'))} first · {p.get('original_team') or 'original team name unavailable (see exact identity below)'} · owned by your team" for p in firsts]
                pricing = (f"Prepared assessment pricing covers {capital.get('priced_pick_count', 0)}/{len(picks)} owned picks. "
                           if facts.get('market_compatible') else 'Current pick pricing is unconfirmed; ownership inventory remains usable. ')
                candidates.append(_item('capital', 'capital', f'{len(firsts)} owned future first-round ' + ('pick' if len(firsts) == 1 else 'picks'),
                    '; '.join(labels[:2]) + (f'; {len(labels)-2} more exact firsts in Supporting evidence.' if len(labels)>2 else ''),
                    pricing + 'Unknown ranges are not guaranteed early picks; capital does not establish future success.',
                    'Review exact draft capital', team_url + '#draft-capital', issues=['capital'], details=identities))
    for event in attention:
        if not event.get('qualifies'):
            continue
        capital_item = next((c for c in candidates if c['family'] == 'capital'), None)
        if event.get('kind') == 'change_event' and capital_item is not None:
            capital_item['reason'] += ' ' + event['why']
            capital_item['details'].append(str(event.get('reference') or ''))
            continue
        candidates.append(_item(event['identity'], 'attention', event['title'], event['why'],
            event.get('confidence') or 'Coverage is not an outcome forecast.', 'Review evidence', event['href'],
            issues=['lineup_coverage'] if event.get('family') == 'team_lineup' else ['capital'],
            details=[str(event.get('reference') or ''), *map(str, event.get('related_weeks') or [])]))
    trade_items = []
    for offer in offers:
        e = offer.get('evaluation') or {}
        if (offer.get('exploration') or not e.get('generated_trade_eligible')
                or e.get('recommendation') not in {'SMASH ACCEPT', 'WORTH PURSUING'}
                or (e.get('market_evidence') or {}).get('availability') != 'full'
                or not offer.get('home_offer')
                or offer.get('home_assessment_strategy') != goal):
            continue
        reason = e.get('why_you_would_do_it') or e.get('dominant_reason')
        drawback = e.get('major_drawback') or '; '.join(e.get('major_risks') or e.get('major_limitations') or [])
        if not reason or not drawback:
            continue
        item = _item('offer:' + offer['home_offer'], 'offer', 'Consider this prepared trade', reason, drawback,
            'Explore / Edit · preview', f'/trades/create?front_office={rid}&home_offer={offer["home_offer"]}',
            offer=offer, roster_id=rid)
        # Only merge an evaluated, explicit need, not a guessed asset position.
        package = ((e.get('dimensions') or {}).get('roster_diagnostics') or {}).get('sides', {}).get('active', {})
        improvements = set()
        for pos, change in (package.get('positions') or {}).items():
            pre, post = change.get('pre') or {}, change.get('post') or {}
            if not all((d.get('evidence') or {}).get('calculation_supported') for d in (pre, post)):
                continue
            if any(pre.get(flag) and not post.get(flag) for flag in ('starter_need','resilience_need','quality_depth_need')):
                improvements.add(pos)
        for need in list(candidates):
            if need['family'] == 'need' and need['key'].split(':')[-1] in improvements:
                item['reason'] += ' ' + need['reason']
                item['drawback'] += ' ' + need['drawback']
                item['issues'] += need['issues']
                candidates.remove(need)
        trade_items.append(item)
    if not goal:
        candidates.append(_item('goal', 'goal', 'Choose a goal for strategic guidance',
            'DTOS cannot determine whether to contend, retool or rebuild from the available evidence. Choose your goal to guide trade suggestions.',
            'Market prices and projected starting-lineup points remain unchanged when you choose a goal.',
            'Choose your goal', team_url + '#my-team-strategy'))
    if assessment is None and not diagnostics and not profile:
        candidates.append(_item('preparation', 'preparation', 'Your roster analysis is not ready',
            'This week’s lineup and depth analysis is not ready for your league and selected goal. Open My Team to review what is available.',
            'Missing preparation is not evidence of roster weakness or a lack of opportunities. Opening My Team does not start a trade search or change your goal.',
            'Open My Team', team_url))
    precedence = {'WIN NOW': ['need', 'offer', 'attention', 'depth', 'capital', 'preparation'],
                  'REBUILD': ['capital', 'offer', 'attention', 'need', 'depth', 'preparation'],
                  'RETOOL': ['need', 'offer', 'depth', 'capital', 'attention', 'preparation'],
                  '': ['attention', 'goal', 'need', 'capital', 'depth', 'offer', 'preparation']}[goal]
    ordered = sorted(candidates + trade_items, key=lambda i: (precedence.index(i['family']), i.get('priority', 0)))
    selected, seen, concerns = [], set(), set()
    for item in ordered:
        if item['key'] in seen or (item['issues'] and set(item['issues']).issubset(concerns)):
            continue
        seen.add(item['key'])
        concerns.update(item['issues'])
        selected.append(item)
        if len(selected) == 4:
            break
    return selected
