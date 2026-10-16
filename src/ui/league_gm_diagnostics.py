"""Progressive, source-qualified league/franchise observations."""
from html import escape


CSS = '''<style>.gm-observations{overflow-wrap:anywhere}.gm-observations p{line-height:1.55}.gm-observations summary{cursor:pointer;min-height:44px;display:flex;align-items:center}.gm-observations .gm-row{border-top:1px solid var(--border);padding:10px 0}.gm-observations a{display:inline-flex;align-items:center;min-height:44px}.gm-observations ul{padding-left:20px}.gm-observations h3{margin-bottom:8px}</style>'''


def _text(value):
    return escape(str(value))


def _evidence(report, row=None):
    content = '<p>' + _text(report['coverage']['explanation']) + '</p>'
    if row:
        content += '<p>' + _text(row['attribution']) + '</p>'
        facts = row['franchise']
        content += '<p>Original consideration observed: ' + _text(
            f"received {facts['incoming'].get('player', 0)} players / {facts['incoming'].get('pick', 0)} exact picks; "
            f"moved {facts['outgoing'].get('player', 0)} players / {facts['outgoing'].get('pick', 0)} exact picks. "
            f"Directed FAAB received {facts['incoming'].get('faab', 0)}, moved {facts['outgoing'].get('faab', 0)} transfers; not Market-priced assets.") + '</p>'
        styles = ', '.join(f'{key}: {count} deals' for key, count in facts['package_style'].items())
        content += '<p>Package asset-count shape: ' + _text(styles or 'Unavailable') + '. Asset count alone does not establish quality or intent.</p>'
        partners = ', '.join(f"{report['teams'].get(rid, {}).get('name', 'Franchise ' + rid)}: {count}" for rid, count in facts['counterparties'].items())
        content += '<p>Observed counterparties: ' + _text(partners or 'None observed') + '.</p>'
        refs = facts['references']
        content += '<p>Sample original trades (up to 12; full retained history remains in Trade Tracker):</p><ul>' + ''.join(
            f'<li><a href="{_text(ref["url"])}">{_text(ref["season"])} · {_text(ref["transaction_id"])}</a></li>' for ref in refs) + '</ul>'
    else:
        for season in report.get('coverage', {}).get('seasons', []):
            content += '<p>' + _text(f"{season['season']}: {len(season['acquired'])} acquired transaction buckets; "
                f"{len(season['unacquired']) + len(season['unavailable']) + len(season['malformed'])} missing or unsupported.") + '</p>'
        content += '<p>Completed events with supported completion clocks: ' + _text(report.get('completed_with_supported_clock', 0)) + '. Creation-only time is not completion time.</p>'
    content += '<ul>' + ''.join('<li>' + _text(note) + '</li>' for note in report.get('limitations', [])) + '</ul>'
    return '<details><summary>Observed facts and coverage</summary>' + content + '</details>'


def team_observations(report, roster_id):
    row = (report or {}).get('teams', {}).get(str(roster_id))
    if not row:
        return '<p>Franchise observations unavailable; no manager tendency established.</p>'
    return CSS + '<section class="gm-observations" data-gm-franchise="' + _text(roster_id) + '"><h2>Franchise and manager context</h2><p>' + _text(row['summary']) + '</p><p class="muted">' + _text(report['coverage']['explanation']) + '</p>' + _evidence(report, row) + '</section>'


def league_observations(intelligence, data, active_id):
    report = intelligence.league.observed_behavior
    if not report or report.get('trade_count') is None:
        return '<section id="league-observations"><h2>League identity</h2><p>Completed-trade observations unavailable; no league tendency established.</p></section>'
    count = report['trade_count']
    observed = report['coverage']['state'].replace('_', ' ')
    body = CSS + f'<section id="league-observations" class="gm-observations"><h2>League identity</h2><p><b>Observed facts · {_text(observed)}</b></p>'
    body += '<p>' + _text(f"{count} completed trades observed; {report['pick_trades']} with supported exact-pick transfers and {report['faab_trades']} with supported FAAB transfers.") + '</p>'
    if report['composition_supported_trades'] < count:
        body += '<p class="muted">Original consideration is incomplete in ' + _text(count - report['composition_supported_trades']) + ' observed trades; asset counts cover supported transfers only.</p>'
    body += '<p class="muted">' + _text(report['coverage']['explanation']) + '</p>'
    seasons = ', '.join(f'{year}: {number} completed trades' for year, number in report['season_counts'].items())
    body += '<p>' + _text(seasons or 'No completed events observed in available evidence.') + '</p>'
    if count:
        ranked = sorted(report['teams'].values(), key=lambda row: (-row['franchise']['trades'], row['roster_id']))
        body += '<p>Most observed franchise participation: ' + _text(', '.join(f"{r['name']} ({r['franchise']['trades']} deals)" for r in ranked[:3] if r['franchise']['trades'])) + '. Multi-party participation is counted once per franchise and deal.</p>'
    body += _evidence(report)
    body += '<details><summary>Current roster environment · separate from trading history</summary>' + ''.join('<p><b>' + _text(position) + ':</b> ' + _text(row.explanation) + '</p>' for position, row in intelligence.league.economy.items()) + '</details>'
    body += '<h3>What this means for your team</h3><p>Current needs and observed history are separate signals. Neither establishes willingness to accept.</p>'
    active_needs = {row.position for row in intelligence.league.needs.get(active_id, ()) if row.priority in {'High', 'Medium'}}
    considerations = []
    for rid, rows in intelligence.league.surpluses.items():
        if rid == active_id:
            continue
        matched = sorted(active_needs & {r.category for r in rows})
        if matched:
            name = report['teams'].get(str(rid), {}).get('name', f'Franchise {rid}')
            considerations.append(f'<li><a href="/teams/{rid}">{_text(name)}</a> has conditional {_text(", ".join(matched))} depth matching your supported need. Removal cost, source limitations and the full offer still matter.</li>')
    body += '<ul>' + ''.join(considerations[:3]) + '</ul>' if considerations else '<p>No specific need/depth match is established in current supported diagnostics. You can still explore legal offers.</p>'
    body += f'<a href="/trades/recommended?front_office={int(active_id)}">Explore trades →</a><h3>GM / franchise insights</h3>'
    for rid, row in report['teams'].items():
        needs = [r.position for r in intelligence.league.needs.get(int(rid), ()) if r.priority in {'High', 'Medium'}]
        body += f'<details class="gm-row"><summary>{_text(row["name"])} · {_text(row["franchise"]["trades"])} observed trades</summary><p>{_text(row["summary"])}</p><p>Current supported needs: {_text(", ".join(needs) or "No reliable priority established")}. Current roster incentives can differ from historical actions.</p><a href="/teams/{int(rid)}">Open read-only Team HQ and exact assets →</a>{_evidence(report, row)}</details>'
    return body + '</section>'
