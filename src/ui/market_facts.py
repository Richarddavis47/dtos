"""Shared readable Market provenance; raw generation IDs stay in disclosure."""
from dataclasses import asdict, is_dataclass
from html import escape


def market_fact_html(fact) -> str:
    if fact is None:
        return ""
    row = asdict(fact) if is_dataclass(fact) else fact
    freshness = str(row.get('freshness') or 'unavailable').replace('_', ' ').capitalize()
    fallback = ' · Last valid provider evidence (refresh unavailable)' if row.get('fallback') else ''
    source = row.get('source_updated_at')
    retrieved = row.get('retrieved_at')
    time_label = f'Source as of {source}' if source else 'Source timestamp unavailable'
    if retrieved:
        time_label += f' · Retrieved {retrieved}'
    reason = row.get('unavailability_reason')
    support = ', '.join(row.get('evidence_coverage') or ()) or 'No supported source'
    return (
        '<div class="market-fact" style="min-width:0;overflow-wrap:anywhere" '
        f'data-market-generation="{escape(str(row.get("generation") or ""), quote=True)}" '
        f'data-market-availability="{escape(str(row.get("availability") or "unavailable"), quote=True)}" '
        f'data-market-freshness="{escape(str(row.get("freshness") or "unavailable"), quote=True)}">'
        f'{f"<p>{escape(reason)}</p>" if reason else ""}'
        f'<small>{escape(freshness + fallback)} · {escape(time_label)}</small>'
        '<details><summary>Market evidence</summary>'
        f'<p>{escape(support)} · Evidence confidence {row.get("confidence", 0)}/100. '
        'Evidence support and freshness; not recommendation or acceptance confidence.</p>'
        f'<p>{escape(str(row.get("warning") or ""))}</p>'
        f'<p>Source generation: <code>{escape(str(row.get("generation") or "Unavailable"))}</code></p>'
        '</details></div>'
    )
