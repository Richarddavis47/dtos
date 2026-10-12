"""Phone-first historical trade summary and bounded evidence disclosures."""

from html import escape
from urllib.parse import quote

CSS = """<style>.trade-timeline{min-width:0;overflow-wrap:anywhere}.trade-timeline .timeline-sides{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr));gap:12px}.trade-timeline summary{cursor:pointer;padding:12px 0;min-height:44px}.trade-timeline summary:focus-visible,.trade-timeline a:focus-visible{outline:2px solid #86efac;outline-offset:3px}.trade-timeline .timeline-events{padding-left:20px}.trade-timeline li{margin:12px 0}.trade-timeline .timeline-asset{margin:12px 0}.trade-timeline .timeline-evidence{font-size:.88rem}.trade-timeline .timeline-evidence pre{white-space:pre-wrap;overflow-wrap:anywhere}.trade-timeline .timeline-link{display:inline-block;padding:8px 0}.trade-timeline .timeline-state{border-left:3px solid #86efac;padding-left:12px}</style>"""


def render_timeline(model, dossier, *, return_url="/transactions"):
    def safe(v):
        return escape(str(v))

    def href(v):
        return escape(str(v), quote=True)

    def people(rows):
        return ", ".join(safe(r["name"]) for r in rows) or "Unresolved franchise"

    participants = "".join(
        f"<article class='card'><h3>{safe(p['name'])}</h3><p>{safe(p['manager'] or 'Historical manager unavailable')}</p><small>{safe(p['manager_scope'])}</small></article>"
        for p in model["participants"]
    )
    summary = []
    branches = []
    for branch in model["branches"]:
        link = f"<a class='timeline-link' href='{href(branch['url'])}?from_trade={quote(dossier['transaction_id'], safe='')}'>{safe(branch['label'])}</a>"
        summary.append(
            f"<li>{link}<div>{people(branch['sent_by'])} → {people(branch['received_by'])}</div></li>"
        )
        moves = []
        for m in branch["events"]:
            owners = f"{safe(', '.join(m['from_names']) or 'Source')} → {safe(', '.join(m['to_names']) or 'Left roster')}"
            action = (
                f"<a class='timeline-link' href='{href(m['trade_url'])}?from_trade={quote(dossier['transaction_id'], safe='')}'>Open subsequent trade</a>"
                if m["trade_url"]
                else ""
            )
            selected = (
                f"<a href='{href(m['selected_player_url'])}?from_trade={quote(dossier['transaction_id'], safe='')}'>{safe(m['selected_player_label'])}</a>"
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
        branches.append(
            f"<details class='card timeline-asset'><summary>{safe(branch['label'])} · {len(moves)} supported subsequent events</summary><ol class='timeline-events'>{''.join(moves) or '<li>No later event admitted from prepared evidence.</li>'}</ol><p class='timeline-state'>{safe(branch['state'])}{' · ' + safe(branch.get('current_observed_owner_name') or 'Franchise name unavailable') if branch['current_observed_owner'] else ''}</p>{warnings}</details>"
        )
    evidence = dossier["trade_time_intelligence"]
    if evidence.get("fairness_state") == "comparable_exact_evidence":
        price_text = "Complete comparable decision-time Market evidence is available. No automatic trade winner is declared."
    elif evidence.get("fairness_state") == "estimated_comparison":
        price_text = "Compatible dated estimates are available; they are not exact trade-time quotes. Process quality requires additional evidence."
    else:
        price_text = "Decision-time Market fairness unavailable: complete compatible dated prices are required, including exact picks."
    quotes = []
    for row in evidence["assets"]:
        quotes.append(
            f"<li>{safe(row['asset_id'])}: {safe(row.get('match_state'))} · {safe(row.get('value') if row.get('value') is not None else 'Value unavailable')}<p>Quote observed: {safe(row.get('observed_at') or 'Unavailable')} · Source knowledge: {safe(row.get('source_knowledge_at') or 'Unavailable')} · Confidence: {safe(row.get('temporal_confidence', 0))}</p><p>{safe(row.get('limitation') or '')}</p></li>"
        )
    technical = [f"{k}: {v}" for k, v in dossier["source"].items()]
    return (
        CSS
        + f'''<section class="trade-timeline"><a class="back" href="{href(return_url)}">← Back to transaction history</a><h2>Original completed trade</h2><p><b>{safe(model["league_name"])} · {safe(model["season"])}</b></p><p>Transaction date: <b>{safe(model["occurred_at"] or "Unavailable")}</b></p><div class="timeline-sides">{participants}</div><section class="card"><h3>Assets sent and received</h3><ul>{"".join(summary)}</ul></section><h3>Subsequent events</h3>{"".join(branches)}<section class="card"><h3>At the time: Market evidence</h3><p>{price_text}</p><p>Production while held, present Market value and later team outcomes are separate. Retained FOIS grades remain NOT REVALIDATED.</p><details class="timeline-evidence"><summary>Prices, dates and limitations</summary><ul>{"".join(quotes)}</ul><pre>{safe(evidence.get("reason"))}</pre></details></section><details class="card timeline-evidence"><summary>Source coverage and limitations</summary>{"".join("<p>" + safe(x) + "</p>" for x in model["limitations"])}<pre>{safe(chr(10).join(technical))}</pre></details></section>'''
    )


def render_ownership_events(events):
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
            f'<a href="/trades/history/{quote(parent.rsplit("-", 1)[-1], safe="")}">View trade trail</a>'
            if parent.startswith("TRADE-")
            else ""
        )
        items.append(
            f"<li>{escape(str(first['season']))} · {escape(first['event_type'].replace('_', ' ').title())} · {escape(', '.join(outgoing) or 'Source')} → {escape(', '.join(incoming) or 'Left roster')} · {escape(first['event_status'])} {action}</li>"
        )
    return "".join(items)
