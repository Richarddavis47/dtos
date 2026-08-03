"""DTOS Design System v1.0 server-rendered presentation contracts."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

DESIGN_SYSTEM_VERSION = "1.0"

DESIGN_SYSTEM_CSS = """
.ds-page-header{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:18px;align-items:start;margin:0 0 20px;padding:19px;background:linear-gradient(135deg,#152b45,#0b1727);border:1px solid var(--line);border-radius:18px}.ds-eyebrow{color:var(--accent);font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.1em}.ds-page-header h1{margin:4px 0 6px;font-size:clamp(24px,4vw,34px)}.ds-purpose{max-width:720px;margin:0;color:var(--muted);line-height:1.55}.ds-context{margin-top:9px;font-size:11px;color:var(--gold)}.ds-header-side{display:grid;justify-items:end;gap:10px}.ds-freshness{text-align:right;color:var(--muted);font-size:10px}.ds-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.ds-action{display:inline-flex;min-height:42px;align-items:center;justify-content:center;padding:9px 13px;border:1px solid var(--line);border-radius:10px;font-weight:850}.ds-action.primary{background:var(--accent);color:#062018;border-color:var(--accent)}.ds-recommendation{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;border-left:4px solid var(--gold);background:linear-gradient(135deg,#172940,#101d2d);border-radius:14px;padding:17px}.ds-recommendation h2,.ds-recommendation h3{margin:3px 0 6px}.ds-confidence{min-width:92px;text-align:right}.ds-confidence b{display:block;font-size:25px;color:var(--accent)}.ds-recommendation details{grid-column:1/-1}.ds-recommendation summary,.ds-evidence summary{cursor:pointer;color:var(--gold);font-weight:850}.ds-empty{padding:18px;border:1px dashed var(--line);border-radius:12px;color:var(--muted)}.ds-empty b{display:block;color:var(--text);margin-bottom:5px}.ds-grade-context{font-size:10px;color:var(--muted);line-height:1.5}.ds-breadcrumbs{display:flex;gap:8px;flex-wrap:wrap;margin:-8px 0 14px;font-size:11px;color:var(--muted)}.ds-breadcrumbs a{color:var(--accent)}
*:focus-visible{outline:3px solid var(--gold);outline-offset:3px}.ds-table-wrap{max-width:100%;overflow-x:auto}
@media(max-width:760px){.ds-page-header{grid-template-columns:1fr;padding:15px}.ds-header-side{justify-items:start}.ds-freshness{text-align:left}.ds-actions{justify-content:flex-start}.ds-action{min-height:44px}.ds-recommendation{grid-template-columns:1fr}.ds-confidence{text-align:left}.ds-confidence b{display:inline;margin-right:6px}table{display:block;max-width:100%;overflow-x:auto}}
"""


@dataclass(frozen=True)
class PagePresentation:
    purpose: str
    context: str
    primary_label: str
    primary_href: str
    secondary_label: str = "Home"
    secondary_href: str = "/"


def _presentation(title: str) -> PagePresentation:
    normalized = title.casefold()
    if "headquarters" in normalized or normalized == "teams":
        return PagePresentation("Understand this franchise's direction, strengths, and next move.", "Front Office direction", "Open Trade Center", "/trades")
    if "player intelligence" in normalized or "player dossier" in normalized:
        return PagePresentation("Decide whether to acquire, hold, build around, or move this player.", "Player decision", "Open Trade Center", "/trades")
    if "trade" in normalized:
        return PagePresentation("Find the best realistic trade to pursue for the active Front Office.", "Trade planning", "Review Teams", "/teams")
    if "front office" in normalized:
        return PagePresentation("Understand how this franchise builds, competes, and negotiates.", "Franchise management", "Open Team HQ", "/teams")
    if "matchup" in normalized:
        return PagePresentation("Understand the weekly matchup, lineup leverage, and likely pressure points.", "Weekly competition", "Review Teams", "/teams")
    if "history" in normalized:
        return PagePresentation("Understand how league and franchise decisions produced today's position.", "Historical evidence", "Open Team HQ", "/teams")
    if "draft" in normalized or "pick" in normalized:
        return PagePresentation("Understand the league's draft-capital ownership and strategic flexibility.", "Draft capital", "Open Trade Center", "/trades")
    if "transaction" in normalized:
        return PagePresentation("See what changed across the league and which assets moved.", "League activity", "Refresh Transactions", "/transactions?refresh=1")
    if "setting" in normalized:
        return PagePresentation("Review league rules, synchronization state, and application information.", "League configuration", "Review Sync Status", "/settings#sync-status")
    return PagePresentation("Navigate the league and open the Front Office question that matters now.", "League overview", "Open Team HQ", "/teams")


def page_header(title: str, *, league_name: str, last_updated: str) -> str:
    presentation = _presentation(title)
    return f'''<header class="ds-page-header" data-dtos-component="page-header" data-design-system="{DESIGN_SYSTEM_VERSION}"><div><div class="ds-eyebrow">DTOS — {escape(presentation.context)}</div><h1>{escape(title)}</h1><p class="ds-purpose">{escape(presentation.purpose)}</p><div class="ds-context">{escape(league_name)}</div></div><div class="ds-header-side"><div class="ds-freshness">League Sync<br><b>{escape(last_updated or "Not synchronized yet")}</b></div><div class="ds-actions"><a class="ds-action primary" href="{escape(presentation.primary_href)}">{escape(presentation.primary_label)}</a><a class="ds-action" href="{escape(presentation.secondary_href)}">{escape(presentation.secondary_label)}</a></div></div></header>'''


def recommendation_panel(*, title: str, recommendation: str, confidence: int, primary_reason: str, evidence: tuple[str, ...], expected_impact: str, action_label: str, action_href: str, limitations: tuple[str, ...] = ()) -> str:
    evidence_html = "".join(f"<li>{escape(item)}</li>" for item in evidence) or "<li>No additional supporting evidence crossed the current confidence boundary.</li>"
    limitations_html = "".join(f"<li>{escape(item)}</li>" for item in limitations) or "<li>No material limitation was identified in the current cached evidence.</li>"
    return f'''<article class="ds-recommendation" data-dtos-component="recommendation"><div><div class="ds-eyebrow">Recommendation</div><h2>{escape(title)}</h2><p>{escape(recommendation)}</p><p><b>Primary reason:</b> {escape(primary_reason)}</p><p><b>Expected impact:</b> {escape(expected_impact)}</p><a class="ds-action primary" href="{escape(action_href)}">{escape(action_label)}</a></div><div class="ds-confidence"><b>{confidence}%</b><span>Confidence</span></div><details><summary>Detailed Evidence</summary><h3>Supporting Evidence</h3><ul>{evidence_html}</ul><h3>Limitations</h3><ul>{limitations_html}</ul></details></article>'''
