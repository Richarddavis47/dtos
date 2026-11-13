"""Compact factual franchise chronology over retained source evidence."""
from html import escape
from urllib.parse import quote


def _movement_details(row):
    parts = ['<h4>Players acquired and sent</h4><p>Gross transfers retain every supported event. Net below means acquired minus sent in these observed trades only; it is not a roster or capital inventory.</p>']
    assets = row.get('assets') or []
    def render_asset(asset):
        links = ''.join('<a href="' + escape(ref['url']) + '">' + escape(str(ref['season']))
                        + ' · ' + escape(ref['direction']) + ' · trade ' + escape(ref['transaction_id']) + '</a>'
                        for ref in asset['references'])
        label = escape(asset['label'])
        if asset['kind'] == 'pick':
            origin = asset['references'][0]['transaction_id'] if asset['references'] else None
            url = '/picks/' + quote(asset['id'], safe='')
            if origin:
                url += '?from_trade=' + quote(origin, safe='')
            label = '<a href="' + escape(url) + '">' + label + ' · ' + ('Own pick (original franchise)' if asset['own'] else 'Another franchise’s original pick') + '</a>'
        net = ('{:+d}'.format(asset['net']) if asset['net'] is not None else 'unknown; consideration is incomplete')
        def gross(direction):
            n = asset[direction]
            return str(n) if asset['complete_in_sample'] else 'at least ' + str(n) if n else 'unknown'
        return '<li><b>' + label + '</b><p>Acquired ' + gross('acquired') + ' · sent ' + gross('sent') + ' · observed net ' + net + '.</p><p>Exact identity: ' + escape(asset['id']) + '</p>' + links + '</li>'
    players = [a for a in assets if a['kind'] == 'player']
    parts.append('<ul>' + ''.join(render_asset(a) for a in players) + '</ul>' if players else '<p>No supported player identities are listed; see the sample coverage above.</p>')
    groups = {}
    for asset in assets:
        if asset['kind'] == 'pick':
            groups.setdefault((asset['season'], asset['round']), []).append(asset)
    parts.append('<h4>Exact draft picks acquired and sent</h4>')
    for (year, round_), picks in sorted(groups.items()):
        parts.append('<h5>' + str(year) + ' · round ' + str(round_) + '</h5><ul>' + ''.join(render_asset(a) for a in picks) + '</ul>')
    if not groups:
        parts.append('<p>No supported exact pick identities are listed; see the sample coverage above.</p>')
    if row.get('details_limited'):
        parts.append('<p>Exact identity detail is limited to 256 assets. The transfer counts cover the admitted sample; use the paginated timeline for further supporting events.</p>')
    parts.append('<p>At most four supporting deals per identity are linked. Pick links open existing subsequent-trade and observed conversion evidence. A draft conversion is not another trade acquisition. Package links do not imply one-to-one player lineage.</p>')
    return ''.join(parts)


def _completed_trade_observations(view):
    """A factual sample, independent of every manager/Trade/FOIS score."""
    row = view.get('completed_trade_observations') or {}
    count = row.get('completed_trades')
    heading = '<section class="card franchise-trades fh-trades" aria-labelledby="fh-trades-title"><h3 id="fh-trades-title">How this franchise changed</h3><p>Completed trade observations · ' + escape(str(view.get('selected_season') or 'all retained source seasons')) + '.</p>'
    if view.get('franchise_id') and view.get('available_seasons'):
        options = '<option value="0">All retained source seasons</option>'
        options += ''.join('<option value="' + str(year) + '"' + (' selected' if year == view.get('selected_season') else '') + '>' + str(year) + '</option>' for year in view['available_seasons'])
        if view.get('selected_season') and view['selected_season'] not in view['available_seasons']:
            options += '<option selected value="' + str(view['selected_season']) + '">' + str(view['selected_season']) + ' · not retained</option>'
        heading += '<form method="get" action="/history/team/' + quote(view['franchise_id'], safe=':') + '"><label for="fh-season">Source season</label><select id="fh-season" name="season">' + options + '</select><button type="submit">Show period</button></form>'
    if count is None:
        excluded = ('<p>' + str(row['unattributed_source_trades']) + ' source-season trades are excluded because franchise continuity or identity is unconfirmed.</p>') if row.get('unattributed_source_trades') else ''
        return heading + '<p>Completed trade counts and asset transfer totals are unknown from the available compatible history.</p><p>' + escape(row.get('reason') or 'Review the source-season coverage below; missing history is not no activity.') + '</p>' + excluded + '</section>'
    def metric(direction, deals, label):
        value = row.get(direction)
        if value is None:
            return '<p><b>' + label + ':</b> Unknown; exact pick consideration is incomplete.</p>'
        prefix = '' if row['pick_counts_complete_in_sample'] else 'At least '
        return '<p><b>' + label + ':</b> ' + prefix + str(value) + (' pick transfer' if value == 1 else ' pick transfers') + ' across ' + prefix.lower() + str(row[deals]) + (' completed trade' if row[deals] == 1 else ' completed trades') + '.</p>'
    body = heading + '<p><b>' + str(count) + ' completed trades observed from retained Sleeper records.</b></p>'
    for kind, label in (('player', 'Player'), ('pick', 'Draft-pick')):
        counts = (row.get('movements') or {}).get(kind)
        if counts is None:
            continue
        def number(key):
            value = counts[key]
            return 'unknown' if value is None else ('' if counts['complete_in_sample'] else 'at least ') + str(value)
        body += '<p><b>' + label + ' transfers:</b> ' + number('acquired') + ' acquired · ' + number('sent') + ' sent. Observed net: ' + ('{:+d}'.format(counts['net']) if counts['net'] is not None else 'unknown; consideration is incomplete') + '.</p>'
    body += '<p>Observed trades only; other roster activity is separate. Remaining holdings are unknown.</p>'
    first, last = row.get('first_completion_at'), row.get('last_completion_at')
    body += ('<p>Observed completion dates: <time datetime="' + escape(first) + '">' + escape(first[:10])
             + '</time> to <time datetime="' + escape(last) + '">' + escape(last[:10]) + '</time> UTC.</p>') if first and last else '<p>Completion date window unknown; no supported completion times are retained.</p>'
    body += '<p>Franchise history · Coverage: ' + escape(row['state']) + '. Missing periods remain unknown.</p>'
    body += '<details><summary>Exact movements, coverage and supporting trades</summary><p>Each transaction is counted once for this franchise; pick transfers count assets separately.</p><p>' + escape(row['attribution']) + '</p><p>' + escape(row['reason']) + '</p>'
    body += '<p>Trade movement only. Waivers, drafts, drops and other activity also change a franchise. Beginning/end roster and capital totals are not established by these observations.</p>'
    body += metric('firsts_received', 'receiving_trades', 'First-round picks acquired')
    body += metric('firsts_sent', 'sending_trades', 'First-round picks sent')
    body += _movement_details(row)
    body += '<p>' + str(row['dated_trades']) + ' of ' + str(count) + ' trades have supported completion times. Undated trades contribute only to the observed season sample.</p>'
    body += '<p>Source seasons: ' + escape(', '.join(map(str, row['source_seasons']))) + '.</p>'
    body += '<p>' + str(row['pick_covered_trades']) + ' of ' + str(count) + ' trades have complete exact-pick consideration. Counts apply to this observed sample; unacquired periods are not zero activity.</p>'
    body += '<p>First-round picks include every supported pick year. A same-season pick is not automatically described as future capital. A pick moved again in another trade counts as another transfer. These are descriptive records, not a recommendation or a judgment of past decisions.</p>'
    if row['unattributed_source_trades']:
        body += '<p>' + str(row['unattributed_source_trades']) + ' source-season trades are excluded because franchise continuity or identity is unconfirmed.</p>'
    links = []
    for ref in row['references']:
        details = ''.join('<p>First-round picks ' + direction + ': ' + escape(', '.join(ref[key])) + '.</p>'
                          for key, direction in (('firsts_received', 'acquired'), ('firsts_sent', 'sent')) if ref[key])
        links.append('<li><a href="' + escape(ref['url']) + '">' + escape(str(ref['season'])) + ' · completed trade ' + escape(ref['transaction_id']) + '</a>' + details + '</li>')
    if links:
        body += '<p>Sample evidence links; full retained events and pagination remain below. Up to four exact picks per direction are listed for each link.</p><ul>' + ''.join(links) + '</ul>'
    return body + '</details></section>'


def render_franchise_timeline(view):
    def text(value):
        return escape(str(value))
    cards = []
    for s in view['seasons']:
        labels = {'unacquired': 'Not retrieved', 'unavailable': 'Source unavailable', 'malformed': 'Source data could not be read', 'failed': 'Refresh failed'}
        gaps = '; '.join(labels[name] + ': weeks ' + ', '.join(map(str, weeks))
                         for name, weeks in s['gaps'].items() if weeks)
        activity = (f"{s['completed_transactions']} completed transactions retained." if s['completed_transactions'] else
                    'No completed transaction activity in the fully acquired supported source periods.' if s['no_activity_supported'] else
                    'No completed transactions retained for this franchise; missing coverage is not no activity.')
        observations = s.get('period_observations') or {}
        freshness = []
        for week in sorted(set(s['acquired']) | {int(w) for w in observations}):
            row = observations.get(str(week)) or {}
            freshness.append('Week ' + str(week) + (': retrieved ' + (row.get('retrieved_at') or 'at an unrecorded time') if week in s['acquired'] else ': no compatible retrieved bucket retained')
                + ('; showing last-valid evidence' if row.get('retained_last_valid') else '')
                + ('. Recorded attempt: ' + row['state'].replace('_',' ') + ' at ' + str(row.get('last_attempt_at') or 'an unrecorded time') if row else ''))
        retrieved = ', '.join(map(str,s['acquired'])) or 'none established'
        empty = ', '.join(map(str,s.get('observed_empty') or [])) or 'none established'
        timing = ('<details><summary>Period freshness</summary><ul>' + ''.join('<li>' + text(r) + '</li>' for r in freshness) + '</ul><p>Retrieval times are DTOS source observations, not transaction occurrence times. Missing periods do not imply no activity.</p></details>') if freshness else ''
        cards.append(f'''<article class="card fh-season"><h4>{s['season']} · {text(s['state'].title())} transaction coverage</h4>
<p>{text(activity)}</p><p>{len(s['acquired'])} source periods retrieved.</p>
{('<p class="cx-risk">Showing retained history after an incomplete refresh.</p>') if any(row.get('retained_last_valid') for row in observations.values()) else ''}
<details class="cx-evidence"><summary>Coverage and source details</summary><p>{text(s['reason'])}</p><p>{len(s['acquired'])} of 19 supported source weeks retrieved (0 is the offseason bucket; 1–18 are weekly buckets).</p>
<p>Retrieved weeks: {text(retrieved)}. Observed-empty retrieved weeks: {text(empty)}.</p>
{('<p>Selected source week: ' + text(s['source_week']) + '. Unretrieved periods remain unknown.</p>') if s.get('source_week') is not None else ''}{timing}
{('<p>' + text(gaps) + '.</p>') if gaps else ''}<p>{s['draft_selections']} draft selections retained. {text(s['draft_note'])}</p>
<p>{text(s['continuity'])}. {'Season-observed franchise identity available.' if s['identity_observed'] else 'Franchise identity for this season is not established.'}</p>
<details><summary>Source context</summary><p>Source league: {text(s['source_league_id'] or 'not recorded')} · retained source generation: {text(s['source_generation'] or 'not recorded')} · prepared-current fingerprint: {text(s['prepared_current_fingerprint'] or 'not used')}.</p></details></details></article>''')
    events = []
    for r in view['events']:
        assets = []
        for a in r['assets']:
            label = text(a['label'])
            if a['kind'] == 'pick' and a.get('id'):
                label = '<a href="/picks/' + quote(a['id'], safe='') + '">' + label + '</a>'
            assets.append('<li><b>' + label + '</b><p>' + text(a['from']) + ' → ' + text(a['to']) + '</p>'
                          + ('<small>Exact pick identity: ' + text(a['id']) + '</small>' if a['kind'] in {'pick', 'selection'} and a.get('id') else '') + '</li>')
        date = r['occurred_at'] or ('Week ' + str(r['week']) + '; exact time unavailable' if r['week'] is not None else 'Exact event time unavailable')
        detail = ('<a href="' + text(r['detail_url']) + '">View completed trade evidence</a>') if r['detail_url'] else ''
        source_only = 'Source roster observation · ' if r['attribution'] == 'franchise continuity unconfirmed' else ''
        events.append('<article class="card fh-event"><h4>' + source_only + str(r['season']) + ' · ' + text(r['kind'].replace('_', ' ').title()) + '</h4>'
            + '<p>' + text(date) + ' · ' + text(r['status']) + '</p><ul>' + ''.join(assets) + '</ul>'
            + ('<p>' + text(r['reason']) + '</p>' if r['reason'] else '')
            + '<p>' + text(r['attribution']) + '.</p>' + detail
            + '<details><summary>Event source</summary><p>Source league ' + text(r['source_league_id']) + ' · record ' + text(r['id']) + '</p></details></article>')
    if not events:
        events = ['<p class="fh-empty">No supported completed events are displayed. Review season coverage above; unavailable history is not an empty history.</p>']
    attempts = ''.join('<li>' + str(r['season']) + ' · ' + text(r['kind']) + ' · ' + text(r['status']) + ': '
                       + text(r['reason']) + ' Source record ' + text(r['id']) + '.</li>' for r in view['attempts'])
    attempts = ('<details class="card fh-attempts"><summary>Not completed or not attributable · ' + str(view['attempts_total'])
                + ' retained records</summary><p>These records do not establish completed asset movements. At most 50 are shown.</p><ul>' + attempts + '</ul></details>') if attempts else ''
    changes = ''.join('<p>Observed manager changed between seasons ' + ' and '.join(map(str, c['observed_season_interval']))
                      + '; exact takeover time is unavailable.</p>' for c in view['ownership'].get('ownership_changes') or [] if str(c['roster_id']) == view['franchise_id'].rsplit(':', 1)[-1])
    links = []
    for n, label in ((view['page'] - 1, 'Previous events'), (view['page'] + 1, 'Next events')):
        if 1 <= n <= view['pages']:
            links.append('<a class="ds-action" href="/history/team/' + quote(view['franchise_id'], safe=':') + '?events_page=' + str(n) + ('&amp;season=' + str(view['selected_season']) if view.get('selected_season') else '') + '">' + label + '</a>')
    return '''<style>.franchise-timeline{min-width:0;overflow-wrap:anywhere}.franchise-timeline .grid{grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr))}.franchise-timeline article{min-width:0}.franchise-timeline summary,.franchise-timeline a{min-height:44px;padding:10px 0;display:block}.franchise-timeline summary{cursor:pointer}.franchise-timeline :focus-visible{outline:2px solid #86efac;outline-offset:3px}.franchise-timeline ul{padding-left:20px}.franchise-trades{min-width:0;overflow-wrap:anywhere}.franchise-trades summary,.franchise-trades a{min-height:44px;padding:10px 0;display:block}.franchise-trades summary{cursor:pointer}.franchise-trades :focus-visible{outline:2px solid #86efac;outline-offset:3px}.franchise-trades ul{padding-left:20px}.franchise-trades form{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.franchise-trades select,.franchise-trades button{min-height:44px;max-width:100%;font:inherit}.franchise-trades select{min-width:0}</style>''' + _completed_trade_observations(view) + '<section class="franchise-timeline"><h3>Franchise transaction timeline</h3><p>' + text(view['qualification']) + '</p>' + changes + ('<p>Earlier linked source-season metadata is unavailable; earlier history remains unknown.</p>' if view['earlier_link_gap'] else '') + '<p>Historical grades: RETAINED / NOT REVALIDATED.</p><p>Coverage varies by season; missing periods remain unknown.</p><div class="grid fh-coverage">' + ''.join(cards) + '</div><h3>Completed movements and observed draft selections</h3><p>' + str(view['total']) + ' supported events · page ' + str(view['page']) + ' of ' + str(view['pages']) + '. Undated events are grouped by source identity, not a proven chronological sequence.</p><div class="fh-events">' + ''.join(events) + '</div>' + ''.join(links) + attempts + '</section>'
