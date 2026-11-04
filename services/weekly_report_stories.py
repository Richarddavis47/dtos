"""Deterministic editorial selection over admitted weekly facts, not intelligence.

Priority is an explicit lexicographic ordering: final playoff result, completed
weekly result, then closeness. It is not a team/player quality score. One matchup
is one story, including its component-week and round-result context.
"""
from decimal import Decimal

METHOD = 'weekly-report-stories-v1'


def candidates(packet):
    result = []
    for match in packet['matchups']:
        if not match['weekly_result_available']:
            continue
        result.append({
            'identity': match['identity'], 'family': 'matchup_result',
            'fact_references': [match['identity']], 'franchises': match['roster_ids'],
            'priority': {'locked_round_result': bool(match['round_result_available']),
                         'championship_bracket': match['bracket'] == 'Championship bracket',
                         'completed_weekly_result': True, 'margin': match['margin']},
            'destination': f"/matchups/{match['matchup_id']}?week={packet['week']}",
        })
    return result


def select_stories(items, limit=4):
    """No minimum story count; repeated identity never creates extra coverage."""
    unique = {}
    for item in items:
        unique.setdefault(item['identity'], item)
    return sorted(unique.values(), key=lambda item: (
        -int(item['priority'].get('championship_bracket', False)),
        -int(item['priority']['locked_round_result']),
        -int(item['priority']['completed_weekly_result']),
        item['priority']['margin'], item['identity']))[:max(0, limit)]


def _score(value):
    # Display preserves source precision; no fabricated zeros or float noise.
    return format(Decimal(str(value)), 'f')


def compose_report(packet, *, lead_limit=4):
    teams = {row['roster_id']: row for row in packet['franchises']}
    matches = {row['identity']: row for row in packet['matchups']}
    stories = []
    covered = set()
    for story in select_stories(candidates(packet), lead_limit):
        match = matches[story['identity']]
        a, b = match['roster_ids']
        names = {rid: teams[rid]['display_name'] for rid in (a, b)}
        scores = match['scores']
        if match['weekly_tie']:
            text = f"{names[a]} and {names[b]} tied at {_score(scores[a])} this week."
        else:
            winner = match['weekly_winner']
            loser = b if winner == a else a
            text = (f"{names[winner]} outscored {names[loser]} "
                    f"{_score(scores[winner])}–{_score(scores[loser])} in Week {packet['week']}.")
        if packet['round_weeks']:
            text += f" {match['bracket']}." if match['bracket'] else ''
            if not match['round_result_available']:
                text += ' This is a component-week result; the playoff round is not complete.'
            elif match['round_winner'] is not None and len(packet['round_weeks']) > 1:
                winner = match['round_winner']
                loser = b if winner == a else a
                text += (f" {names[winner]} won the completed round "
                         f"{_score(match['round_scores'][winner])}–{_score(match['round_scores'][loser])}.")
            elif match['round_winner'] is None:
                text += ' The completed round has tied scores; no tiebreak winner is established here.'
        stories.append({**story, 'text': text})
        covered.update(story['franchises'])
    around = []
    for rid, team in teams.items():
        if rid in covered:
            continue
        status = team['status']
        name = team['display_name']
        references = [team['identity']]
        if status == 'qualified_on_bye':
            text = f'{name} qualified for the playoffs and has a first-round bye.'
        elif status in {'weekly_win', 'weekly_loss', 'weekly_tie'}:
            word = {'weekly_win': 'a weekly win', 'weekly_loss': 'a weekly loss', 'weekly_tie': 'a weekly tie'}[status]
            text = f"{name} recorded {word} with {_score(team['actual'])} points."
            references.append(team['matchup_reference'])
        elif status == 'pregame':
            text = f'{name} has not played this matchup yet.'
        elif status in {'live', 'in-game', 'in_progress'}:
            text = f'{name} has a matchup in progress; the result is not final.'
        else:
            text = f'{name}: completed weekly result evidence is unavailable.'
        around.append({'roster_id': rid, 'text': text, 'fact_references': references})
    return {'league_id': packet['league_id'], 'season': packet['season'], 'week': packet['week'],
            'state': packet['state'], 'methodology': METHOD,
            'fact_identity': packet['semantic_identity'], 'stories': stories,
            'around_the_league': around, 'limitations': packet['limitations']}
