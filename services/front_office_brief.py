"""Small prepared reads and pure Home composition. No discovery or factories.

The selected goal scopes the assessment cache; objective diagnostics can be reused
across goals. Each family admits its own evidence, independently of Market.
"""
from math import isfinite

from src.core.intelligence import intelligence_orchestrator
from src.core.intelligence.roster_diagnostics import prepared_diagnostics
from src.core.intelligence.team_strength import compatible_profile
from src.ui.intelligence_presentation import manager_points


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
    return {'league_id': context.league_id, 'roster_id': roster_id,
            'strategy': strategy if strategy in {'WIN NOW', 'REBUILD', 'RETOOL'} else '',
            'generation': context.evidence_generation, 'assessment': assessment,
            'market_compatible': market_compatible,
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
    positions = own.get('positions') or {}
    profile = facts.get('strength') or {}
    strength = (profile.get('teams') or {}).get(str(rid)) or {}
    weekly = (strength.get('weekly') or {}).get(str(facts['week'])) or (strength.get('weekly') or {}).get(facts['week']) or {}
    optimal = weekly.get('optimal') or {}
    context = (f"Week {facts['week']} optimal legal lineup: {manager_points(optimal['projected_points'])} points under {facts['league_name']} scoring. "
               if optimal.get('available') and _number(optimal.get('projected_points')) else '')
    for pos, d in positions.items():
        evidence = d.get('evidence') or own.get('evidence') or {}
        if not evidence.get('calculation_supported') or d.get('conclusion_state') == 'unavailable':
            continue
        provisional = d.get('conclusion_state') != 'current'
        qualifier = 'Provisional: ' if provisional else ''
        issue = f'position:{pos}'
        quality = d.get('quality_depth_need')
        if quality or d.get('resilience_need') or d.get('starter_need'):
            title = (f'{pos} replacement production needs review' if quality else
                     f'{pos} legal cover needs review' if d.get('resilience_need') else
                     f'A supported {pos} addition could improve the lineup')
            reason = context + (d.get('base_reason') or 'Prepared legal-lineup scenarios identify a production gap.')
            drawback = ('This is a current production gap, not evidence to buy an aging starter under REBUILD.'
                        if goal == 'REBUILD' else
                        'An upgrade has a Market and capital cost; this is not an endorsed trade.')
            candidates.append(_item(issue, 'need', qualifier + title, reason, drawback,
                'Review replacement depth', team_url + '#positional-depth', issues=[issue],
                details=[*own.get('limitations', []), *evidence.get('limitations', [])]))
        elif d.get('disjoint_reserve_ids') and any(_number(v) for v in d.get('observed_replacement_points') or []):
            # Useful reserve evidence is not permission to sell; use supported
            # removal scenarios, never headcount or an invented injury model.
            points = manager_points(min(v for v in d['observed_replacement_points'] if _number(v)))
            candidates.append(_item(issue, 'depth', qualifier + f'Keep {pos} replacement production in view',
                f'Prepared {pos} starter-removal scenarios have at least {points} projected replacement points under {facts["league_name"]} scoring in week {facts["week"]}.',
                'Useful cover is not automatically surplus. Separate removal scenarios cannot cover simultaneous absences.',
                'Review removal costs', team_url + '#positional-depth', issues=[issue],
                details=own.get('limitations', [])))
    assessment = facts.get('assessment')
    capital = assessment.team.future_capital_evidence if assessment else {}
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
            'Your goal changes which tradeoffs deserve attention; no competitive direction is inferred.',
            'Neutral Market values and objective legal-lineup calculations stay unchanged.',
            'Choose your goal', team_url + '#my-team-strategy'))
    precedence = {'WIN NOW': ['need', 'offer', 'attention', 'depth', 'capital'],
                  'REBUILD': ['capital', 'offer', 'attention', 'need', 'depth'],
                  'RETOOL': ['need', 'offer', 'depth', 'capital', 'attention'],
                  '': ['attention', 'goal', 'need', 'capital', 'depth', 'offer']}[goal]
    ordered = sorted(candidates + trade_items, key=lambda i: precedence.index(i['family']))
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
