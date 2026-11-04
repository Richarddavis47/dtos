"""Escaped, semantic weekly report presentation; no intelligence computations."""
from html import escape


def render_report(report, league_name, season, week):
    state = (report or {}).get('state', 'unavailable')
    label = {'completed': 'Completed', 'preview': 'Preview',
             'in_progress': 'In progress', 'unavailable': 'Unavailable'}[state]
    header = f'''<section class="weekly-report" aria-label="Weekly league report">
<header><h2>{escape(str(league_name))} · {season} · Week {week}</h2><p>{label}</p></header>
<form action="/reports/weekly" method="get" aria-label="Choose report period">
<label>Season <input name="season" type="number" min="2000" max="2100" value="{season}" required></label>
<label>Week <input name="week" type="number" min="1" max="18" value="{week}" required></label>
<button type="submit">Open report</button></form>'''
    style = '''<style>.weekly-report{max-width:72rem;margin:auto;overflow-wrap:anywhere}
.weekly-report form{display:flex;flex-wrap:wrap;gap:1rem;margin:1rem 0}
.weekly-report input{max-width:8rem}.weekly-report input,.weekly-report button,.weekly-report summary{min-height:44px}
.weekly-report article{padding:1rem;border:1px solid var(--border,#334);border-radius:12px;margin:.75rem 0}
.weekly-report p{max-width:72ch;line-height:1.6}.weekly-report a{display:inline-block;padding:.65rem 0}
.weekly-report :focus-visible{outline:2px solid #8cdc49;outline-offset:3px}
@media(min-width:900px){.weekly-report .report-around{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}
</style>'''
    if not report or state == 'unavailable':
        return style + header + '<p>Prepared evidence for this league and week is unavailable. No result has been inferred.</p></section>'
    body = ''
    if report['stories']:
        body += '<section aria-labelledby="report-leads"><h3 id="report-leads">Top stories</h3>'
        for story in report['stories']:
            body += f'<article><p>{escape(story["text"])}</p><a href="{escape(story["destination"], quote=True)}">Explore source matchup or season</a></article>'
        body += '</section>'
    if report['around_the_league']:
        body += '<section aria-labelledby="report-around"><h3 id="report-around">Around the league</h3><div class="report-around">'
        body += ''.join(f'<article><p>{escape(row["text"])}</p></article>' for row in report['around_the_league'])
        body += '</div></section>'
    moves = report.get('transaction_facts') or {}
    if moves.get('facts'):
        counts = {kind: sum(row['type'] == kind for row in moves['facts']) for kind in ('trade', 'waiver', 'free_agent')}
        body += '<section aria-labelledby="report-moves"><h3 id="report-moves">Completed moves</h3>'
        body += '<p>' + ' · '.join(f'{n} {name}' for key, name in (('trade', 'trades'), ('waiver', 'waiver actions'), ('free_agent', 'free-agent actions')) if (n := counts[key])) + '</p>'
        body += '<p>Recorded in this source week’s transaction bucket. These counts describe activity, not decision quality.</p></section>'
    body += '<details><summary>Report evidence and limitations</summary><p>Results use recorded scores and submitted lineups. No current projections or later player outcomes are used to judge historical decisions. Historical franchise labels do not attribute decisions to today’s manager. Missing historical comparisons do not imply no change.</p></details>'
    return style + header + body + '</section>'
