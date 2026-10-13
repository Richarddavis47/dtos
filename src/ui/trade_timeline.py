"""Phone-first historical trade summary and bounded evidence disclosures."""

from html import escape
from urllib.parse import quote
import json
from datetime import datetime

CSS = """<style>.trade-timeline{min-width:0;overflow-wrap:anywhere}.trade-timeline .timeline-sides{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr));gap:12px}.trade-timeline summary{cursor:pointer;padding:12px 0;min-height:44px}.trade-timeline summary:focus-visible,.trade-timeline a:focus-visible{outline:2px solid #86efac;outline-offset:3px}.trade-timeline .timeline-events{padding-left:20px}.trade-timeline li{margin:12px 0}.trade-timeline .timeline-asset{margin:12px 0}.trade-timeline .timeline-evidence{font-size:.88rem}.trade-timeline .timeline-evidence pre{white-space:pre-wrap;overflow-wrap:anywhere}.trade-timeline .timeline-link{display:inline-block;padding:8px 0}.trade-timeline .timeline-state{border-left:3px solid #86efac;padding-left:12px}</style>"""


def render_source_coverage(coverage):
    rows = []
    for season in coverage.get('seasons', []):
        parts = []
        for key in ('transactions', 'matchups'):
            family = season.get(key)
            if not isinstance(family, dict):
                parts.append(f'{key.title()}: acquisition periods unavailable in compact evidence')
                continue
            parts.append(f'{key.title()}: ' + '; '.join(
                f"{state.replace('_', ' ')}: {', '.join(map(str, family.get(state, []))) or 'none'}"
                for state in ('observed', 'observed_empty', 'unavailable', 'unacquired', 'malformed')))
        families = season.get('families')
        if isinstance(families, dict):
            parts.append('; '.join(f"{key.replace('_', ' ')}: {value.replace('_', ' ')}" for key, value in families.items()))
        parts.extend(season.get('optional_field_limitations', []))
        rows.append('<li><b>' + escape(str(season['season'])) + '</b>' + ''.join('<p>' + escape(part) + '</p>' for part in parts) + '</li>')
    return ('<details class="card timeline-evidence" style="overflow-wrap:anywhere"><summary style="min-height:44px">Source coverage · '
            + str(len(rows)) + ' retained season(s)</summary><p>Acquired periods are source observations; observed-empty periods were retrieved and contained no rows. Unavailable, malformed and unacquired periods are not empty history. Structural cache validity does not establish complete source acquisition.</p><p>Season roster snapshots are not weekly rosters. Branch gaps and absent weekly scores remain unavailable.</p><ul>'
            + ''.join(rows) + '</ul></details>')


def render_production(rows, league, generation):
    def points(value):
        return 'Unavailable' if value is None else f'{value:.2f}'
    cards = []
    for row in rows:
        observations = ''.join(f"<li>{r['season']} Week {r['week']} · {escape(r['role'])} · {points(r['points'])}{' · score conflict' if r['conflict'] else ''}</li>" for r in row['observed_weeks'])
        intervals = ''.join('<li>' + escape(str(i.get('acquired_at') or 'Acquisition time unavailable')) + ' → '
                            + escape(str(i.get('disposed_at') or 'No verified exit time')) + ' · '
                            + escape(i['reconciliation_status'].replace('_', ' ')) + '</li>' for i in row['ownership_intervals'])
        cards.append(f'''<article class="card"><h4>{escape(row['name'])} · {escape(row['recipient'])}</h4>
<p><b>Known observed roster subtotal: {points(row['observed_roster_points'])}</b></p><p>Started: {points(row['started_points'])} · Explicit bench: {points(row['bench_points'])} · Unknown role: {points(row['unknown_role_points'])}</p>
<p>{row['scored_observations']} scored / {row['membership_observations']} observed franchise-week memberships · {row['supported_starts']} supported starts · {row['unknown_role_observations']} unknown roles · {row['missing_score_observations']} missing/conflicted scores.</p>
<p>{escape(row['scope'])}</p><p><b>Complete holding-period benefit: Unavailable.</b> {escape(row['limitation'])}</p>
<details><summary>Observed weeks and independent ownership intervals</summary><ul>{observations or '<li>No scored roster weeks admitted.</li>'}</ul><h5>Intervals · not a continuous ownership guarantee</h5><ul>{intervals or '<li>Ownership interval evidence unavailable.</li>'}</ul></details></article>''')
    return f'<section data-production-result data-league="{escape(league, quote=True)}" data-generation="{escape(generation, quote=True)}">' + ''.join(cards) + '<p>Scores are Sleeper actual observations. Season totals, projections, current value and championships are separate; no causal trade credit is calculated.</p></section>'


def readable_trade_reference(reference, graph):
    reference = str(reference)
    resolved = graph.trade_reference(reference)
    action = ('<a class="ds-action" href="' + escape(resolved['url'], quote=True) + '">' + escape(resolved['label']) + '</a>') if resolved else '<p>Source reference · supported trade destination unavailable.</p>'
    return action + '<details><summary>Source reference details</summary><code style="overflow-wrap:anywhere">' + escape(reference) + '</code></details>'


def _quote_card(row, label):
    def safe(value):
        return escape(str(value))
    identity = row.get('comparison_identity')
    units = f"{identity[0].replace('_', ' ')} · {identity[1]}" if identity else 'Comparable units unavailable'
    contexts = []
    if identity:
        try:
            formats = json.loads(identity[2])
            for source in formats:
                details = ', '.join(f"{key.replace('_', ' ')} {value}" for key, value in (source.get('details') or {}).items())
                contexts.append(f"{source.get('provider')}: {source.get('format')} · {details}")
        except (ValueError, TypeError, KeyError):
            contexts.append('Source format unavailable')
    providers = row.get('provider_evidence') or (row.get('retained_observation') or {}).get('provider_evidence') or []
    names = ', '.join(dict.fromkeys(str(p.get('provider') or 'Provider unavailable') for p in providers)) or 'No provider observation admitted'
    raw = ''.join('<li>' + safe(p.get('provider')) + ' · raw source value: ' + safe(p.get('raw_value') if p.get('raw_value') is not None else 'Unavailable')
                  + ' · quote observed: ' + safe(p.get('observed_at') or 'Unavailable') + '<pre>'
                  + safe(json.dumps((p.get('metadata') or {}).get('comparison_semantics') or {}, sort_keys=True)) + '</pre></li>' for p in providers)
    value = 'No comparable value' if row.get('value') is None else str(row['value'])
    version = row.get('normalization_version') or (row.get('retained_observation') or {}).get('normalization_version') or 'Unavailable'
    confidence = row.get('source_quote_confidence')
    if confidence is None:
        confidence = (row.get('retained_observation') or {}).get('source_confidence')
    attachment = '<p>Original retained attachment: ' + safe(row['retained_attachment_at']) + ' · separate from quote observation.</p>' if row.get('retained_attachment_at') else ''
    return f'''<li><h4>{safe(row.get('asset_name') or label)}</h4><p>{safe(row.get('match_state'))} · {safe(value)}</p>
<p>{safe(row.get('admission_reason') or 'No admitted quote; original trade time or source evidence is unavailable.')}</p>
<p>Provider: {safe(names)} · {safe(units)}</p><p>Source format: {safe('; '.join(contexts) or 'Unavailable')}. Provider format is not proof of exact historical league-format parity.</p>
<p>Quote observed: {safe(row.get('observed_at') or 'Unavailable')} · Source knowledge: {safe(row.get('source_knowledge_at') or 'Unavailable')}</p>{attachment}
<p>Normalization version: {safe(version)} · Comparison version: {safe(identity[3] if identity else 'Unavailable')}.</p><p>Temporal confidence: {safe(row.get('temporal_confidence', 0))} · Source observation confidence: {safe(confidence if confidence is not None else 'Unavailable')}. Confidence is not a trade outcome probability.</p>
<p>{safe(row.get('limitation') or '')}</p><details><summary>Retained raw observations · excluded unless admitted above</summary><ul>{raw or '<li>No raw quote in available exact asset/context evidence.</li>'}</ul></details></li>'''


def render_timeline(model, dossier, *, return_url="/transactions", origin_id=None):
    origin_id = origin_id or dossier['transaction_id']
    def safe(v):
        return escape(str(v))

    def href(v):
        return escape(str(v), quote=True)

    def people(rows):
        return ", ".join(safe(r["name"]) for r in rows) or "Unresolved franchise"

    groups = {p['id']: {'party': p, 'sent': [], 'received': []} for p in model['participants']}
    summary = []
    branches = []
    for branch in model["branches"]:
        link = f"<a class='timeline-link' href='{href(branch['url'])}?from_trade={quote(origin_id, safe='')}'>{safe(branch['label'])}</a>"
        summary.append(
            f"<li>{link}<div>{people(branch['sent_by'])} → {people(branch['received_by'])}</div></li>"
        )
        for direction, field in (('sent', 'sent_by'), ('received', 'received_by')):
            for party in branch[field]:
                if party['id'] in groups:
                    groups[party['id']][direction].append(f'<li>{link}</li>')
        moves = []
        for m in branch["events"]:
            owners = f"{safe(', '.join(m['from_names']) or 'Source')} → {safe(', '.join(m['to_names']) or 'Left roster')}"
            action = (
                f"<a class='timeline-link' href='{href(m['trade_url'])}?from_trade={quote(origin_id, safe='')}'>Open subsequent trade</a>"
                if m["trade_url"]
                else ""
            )
            selected = (
                f"<a href='{href(m['selected_player_url'])}?from_trade={quote(origin_id, safe='')}'>{safe(m['selected_player_label'])}</a>"
                if m.get("selected_player_url")
                else ""
            )
            when = (
                m["occurred_at"]
                or f"Between {m['time_bounds'][0]} and {m['time_bounds'][1]} · exact selection time unavailable"
            )
            moves.append(
                f"<li><b>{safe(m['type'].replace('_', ' ').title())}</b> · {safe(when)}<p>{safe(m['asset_label'])} {selected}</p><p>{owners}</p>{action}<p class='muted'>{safe(m['package_note'] or m['evidence'])}</p><details><summary>Event source</summary><p>{safe(m['source_league_id'])} · {safe(m['source_record_id'])}</p></details></li>"
            )
        warnings = "".join(
            f'<p class="muted">{safe(x)}</p>' for x in branch["limitations"]
        )
        endpoint = branch.get('converted_asset') or {}
        current_state = ''
        if endpoint:
            current_state = f"<p class='timeline-state'>Pick consumed → <a class='timeline-link' href='{href(endpoint['url'])}?from_trade={quote(origin_id, safe='')}'>{safe(endpoint['name'])}</a> · Current observed owner: {safe(endpoint.get('current_observed_owner_name') or 'Unavailable')} · as of {safe(endpoint.get('as_of') or 'date unavailable')}.</p>"
        elif branch.get('current_observed_owner'):
            current_state = f"<p>Current observed owner: {safe(branch.get('current_observed_owner_name') or 'Unavailable')} · as of {safe((branch.get('current_owner_observation') or {}).get('as_of') or 'date unavailable')}.</p>"
        last = branch.get('last_verified_event')
        last_note = f"<p>Last admitted event: {safe(last['type'].replace('_', ' '))} · {safe(last.get('occurred_at') or 'bounded draft time')} · {safe(', '.join(last.get('to_names') or []) or 'Ownership exit')}.</p>" if last else ''
        branches.append(
            f"<section class='card'><b>{safe(branch['label'])}</b>{current_state}{last_note}<details class='timeline-asset'><summary>{len(moves)} supported subsequent events · {safe(branch['state'])}</summary><ol class='timeline-events'>{''.join(moves) or '<li>No later event admitted from prepared evidence; this is not proof of no movement.</li>'}</ol>{warnings}</details></section>"
        )
    evidence = dossier["trade_time_intelligence"]
    for movement in model.get("faab_movements") or ():
        amount = format(movement["amount"], "g")
        summary.append(
            f"<li class='timeline-faab'><b>{safe(amount)} FAAB</b><div>{safe(movement['sent_by']['name'])} → {safe(movement['received_by']['name'])}</div><details><summary>FAAB source</summary><p>{safe(movement['provenance'])}</p><p>Source league: {safe(movement['source_league_id'])} · Transaction: {safe(movement['transaction_id'])}</p></details></li>"
        )
    if evidence.get("fairness_state") == "comparable_exact_evidence":
        price_text = "Complete comparable decision-time Market evidence is available. No automatic trade winner is declared."
    elif evidence.get("fairness_state") == "estimated_comparison":
        price_text = "Compatible dated estimates are available; they are not exact trade-time quotes. Process quality requires additional evidence."
    else:
        price_text = "Decision-time Market fairness unavailable: complete compatible dated prices are required, including exact picks."
    if dossier.get("faab"):
        price_text += " FAAB is shown as original trade consideration; player/pick Market totals do not value FAAB or establish fairness of the whole trade."
    labels = {b['asset_id']: b['label'] for b in model['branches']}
    quotes = [_quote_card(row, labels.get(row['asset_id'], 'Asset identity unavailable')) for row in evidence['assets']]
    participants = ''.join(f"<article class='card'><h3>{safe(g['party']['name'])}</h3><p>Season-observed manager: {safe(g['party']['manager'] or 'Unavailable')}</p><h4>Sent</h4><ul>{''.join(g['sent']) or '<li>No supported player/pick transfer displayed.</li>'}</ul><h4>Received</h4><ul>{''.join(g['received']) or '<li>No supported player/pick transfer displayed.</li>'}</ul></article>" for g in groups.values())
    cash = [item for item in summary if "class='timeline-faab'" in item]
    unresolved = ''.join('<li>' + safe(item['label']) + ' · '
                         + safe((item.get('sender') or {}).get('name') or 'Sender unavailable') + ' → '
                         + safe((item.get('receiver') or {}).get('name') or 'Receiver unavailable')
                         + '. Exact lineage and price unavailable; no asset destination is invented.</li>'
                         for item in model.get('unresolved_consideration', []))
    if unresolved:
        participants += '<article class="card"><h4>Unresolved original consideration</h4><ul>' + unresolved + '</ul></article>'
    production_url = f"/trades/history/{quote(dossier['transaction_id'], safe='')}/production?generation={quote(model.get('generation') or '', safe='')}"
    production = f'''<details class="card" data-production-endpoint="{href(production_url)}" data-league="{href(model['league_id'])}" data-generation="{href(model.get('generation') or '')}"><summary>Supported production · recipient roster weeks and interval limits</summary><div data-production-content aria-live="polite">Open to retrieve existing scoring evidence. Complete holding-period benefit may remain unavailable.</div></details><script defer src="/static/js/history-production.js"></script>'''
    back_label = 'Back to original trade timeline' if return_url.startswith('/trades/history/') else 'Back to transaction history'
    try:
        trade_date = datetime.fromisoformat(model['occurred_at'].replace('Z', '+00:00')).strftime('%b %d, %Y · %H:%M UTC')
    except (ValueError, TypeError, AttributeError):
        trade_date = 'Date unavailable'
    technical = [f"{k}: {v}" for k, v in dossier["source"].items()]
    return (
        CSS
        + f'''<section class="trade-timeline"><a class="back" href="{href(return_url)}">← {back_label}</a><h2>Original completed trade</h2><p><b>{safe(model["league_name"])} · {safe(model["season"])} · {safe(trade_date)}</b></p><section><h3>Assets sent and received</h3><p>{safe(' ↔ '.join(p['name'] for p in model['participants']))}</p><div class="timeline-sides">{participants}</div>{'<h4>FAAB consideration</h4><ul>' + ''.join(cash) + '</ul>' if cash else ''}<details><summary>Historical manager context</summary><p>Managers are season observations; exact trade-time takeover timing is not established.</p></details></section><h3>Subsequent events & confirmed current state</h3><p>Current roster observations and last transfers are separate. An as-of date is not an acquisition timestamp; missing intervals do not establish uninterrupted ownership.</p>{"".join(branches)}{production}<section class="card"><h3>At the time: Market evidence</h3><p>{price_text}</p><p>{evidence.get('valued_assets', 0)} / {evidence.get('total_assets', 0)} assets have admitted compatible pre-trade quotes. Retained raw observations do not establish comparable package coverage.</p><p>Trade reference date: {safe(trade_date)}. Production, present Market value and later team outcomes are separate. Retained FOIS grades remain NOT REVALIDATED.</p><details class="timeline-evidence"><summary>Prices, dates and limitations</summary><ul>{"".join(quotes)}</ul><p>Package admission: {safe(str(evidence.get('reason') or 'Unavailable').replace('_', ' '))}</p></details></section>{render_source_coverage(model.get('source_coverage') or {})}<details class="card timeline-evidence"><summary>Source provenance and branch limitations</summary>{"".join("<p>" + safe(x) + "</p>" for x in model["limitations"])}<pre>{safe(chr(10).join(technical))}</pre></details></section>'''
    )


def render_ownership_events(events, *, graph=None, from_trade=None):
    groups = {}
    for event in events:
        parent = event.get("parent_id") or event["event_id"]
        groups.setdefault((parent, event["asset_id"]), []).append(event)
    items = []
    for (parent, _asset), rows in groups.items():
        first = rows[0]
        outgoing = sorted(
            {
                str(r["from_franchise_id"]).rsplit(":", 1)[-1]
                for r in rows
                if r.get("from_franchise_id")
            }
        )
        incoming = sorted(
            {
                str(r["to_franchise_id"]).rsplit(":", 1)[-1]
                for r in rows
                if r.get("to_franchise_id")
            }
        )
        action = (
            f'<a class="ds-action" href="/trades/history/{quote(parent.rsplit("-", 1)[-1], safe="")}{"?from_trade=" + quote(from_trade, safe="") if from_trade else ""}">View trade trail</a>'
            if parent.startswith("TRADE-")
            else ""
        )
        if graph:
            outgoing = [graph.franchise_label(f'{graph.league_id}:franchise:{f}', first['season']) for f in outgoing]
            incoming = [graph.franchise_label(f'{graph.league_id}:franchise:{f}', first['season']) for f in incoming]
        items.append(f"<li>{escape(str(first.get('occurred_at') or 'Date unavailable'))} · {escape(first['event_type'].replace('_', ' ').title())} · {escape(', '.join(outgoing) or 'Source')} → {escape(', '.join(incoming) or 'Left roster')} · {escape(first['event_status'])} {action}</li>")
    return "".join(items)
