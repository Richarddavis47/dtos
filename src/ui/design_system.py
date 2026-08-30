"""DTOS Design System v1.0 server-rendered presentation contracts."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

DESIGN_SYSTEM_VERSION = "1.1"

DESIGN_SYSTEM_CSS = """
.ds-page-header{position:relative;overflow:hidden;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:22px;align-items:start;margin:0 0 22px;padding:24px;background:radial-gradient(circle at 92% 0,rgba(93,242,55,.10),transparent 32%),linear-gradient(145deg,var(--surface-2),var(--surface-1));border:1px solid var(--line);border-radius:var(--radius-xl);box-shadow:var(--shadow-card)}.ds-page-header:after{content:"";position:absolute;left:24px;bottom:0;width:56px;height:2px;background:var(--accent);box-shadow:0 0 18px var(--accent)}.ds-eyebrow{color:var(--accent);font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.13em}.ds-page-header h1{margin:5px 0 7px;font-size:clamp(25px,4vw,38px);letter-spacing:-.035em}.ds-purpose{max-width:720px;margin:0;color:var(--muted);line-height:1.55}.ds-context{margin-top:11px;font-size:11px;color:var(--gold)}.ds-header-side{display:grid;justify-items:end;gap:12px}.ds-freshness{text-align:right;color:var(--muted);font-size:10px}.ds-freshness b{color:var(--text)}.ds-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.ds-action{display:inline-flex;min-height:42px;align-items:center;justify-content:center;padding:9px 14px;border:1px solid var(--line);border-radius:var(--radius-sm);font-weight:900;transition:transform .15s ease,border-color .15s ease,background .15s ease}.ds-action:hover{transform:translateY(-1px);border-color:var(--line-strong);background:rgba(255,255,255,.025)}.ds-action.primary{background:linear-gradient(135deg,var(--accent),var(--accent-strong));color:#071108;border-color:var(--accent);box-shadow:0 8px 24px rgba(93,242,55,.16)}.ds-recommendation{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;border:1px solid rgba(93,242,55,.28);border-left:4px solid var(--accent);background:linear-gradient(145deg,var(--surface-2),var(--surface-1));border-radius:var(--radius-lg);padding:19px;box-shadow:var(--shadow-card)}.ds-recommendation h2,.ds-recommendation h3{margin:3px 0 6px}.ds-confidence{min-width:92px;text-align:right}.ds-confidence b{display:block;font-size:27px;color:var(--accent)}.ds-recommendation details{grid-column:1/-1}.ds-recommendation summary,.ds-evidence summary{cursor:pointer;color:var(--gold);font-weight:850}.ds-empty{padding:22px;border:1px dashed var(--line-strong);border-radius:var(--radius-md);color:var(--muted);background:rgba(7,13,21,.45)}.ds-empty b{display:block;color:var(--text);margin-bottom:5px}.ds-grade-context{font-size:10px;color:var(--muted);line-height:1.5}.ds-breadcrumbs{display:flex;gap:8px;flex-wrap:wrap;margin:-8px 0 14px;font-size:11px;color:var(--muted)}.ds-breadcrumbs a{color:var(--accent)}
.manager-nav{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:14px 0 20px;padding:6px;background:rgba(7,13,21,.62);border:1px solid var(--line);border-radius:var(--radius-lg)}.manager-nav a{display:flex;gap:8px;min-height:46px;align-items:center;justify-content:center;padding:9px 12px;border:1px solid transparent;border-radius:var(--radius-sm);color:var(--muted);font-weight:850}.manager-nav a[aria-current="page"]{color:var(--text);border-color:rgba(93,242,55,.38);background:rgba(93,242,55,.09)}.manager-nav-icon{color:var(--accent);font-size:15px}.secondary-nav{margin:-8px 0 17px}.secondary-nav summary{cursor:pointer;color:var(--muted);font-size:12px;font-weight:800}.secondary-nav div{display:flex;gap:8px;flex-wrap:wrap;margin-top:9px}.secondary-nav a{padding:7px 10px;border:1px solid var(--line);border-radius:999px;color:var(--muted);font-size:12px}.ux-section{margin:24px 0}.ux-section-head{display:flex;align-items:end;justify-content:space-between;gap:12px;margin-bottom:11px}.ux-section-head h2{margin:0;letter-spacing:-.02em}.ux-section-head p{margin:0;color:var(--muted);font-size:12px}.ux-answer{border-left:4px solid var(--accent)}.ux-competitive-header{padding:18px}.ux-recap{font-size:16px;line-height:1.65;border-left:3px solid var(--gold)}.ux-recap p{max-width:780px}.ux-action-list{display:grid;gap:10px}.ux-action{display:flex;justify-content:space-between;gap:14px;align-items:center;padding:14px;border:1px solid var(--line);border-radius:var(--radius-md);background:var(--surface-1)}.ux-action p{margin:4px 0 0;color:var(--muted)}.technical-details{margin-top:10px}.technical-details>summary{cursor:pointer;color:var(--muted);font-size:11px}.evidence-unavailable{padding:14px;border:1px dashed var(--line);border-radius:12px;color:var(--muted)}
.player-summary{display:flex;gap:10px;align-items:center;min-width:0}.player-portrait{position:relative;flex:0 0 44px;width:44px;height:44px}.player-headshot,.player-headshot-fallback{position:absolute;inset:0;width:44px;height:44px;border-radius:50%;border:1px solid var(--line)}.player-headshot{z-index:1;object-fit:cover;background:#182a40}.player-headshot-fallback{display:grid;place-items:center;background:#182a40;color:var(--accent);font-weight:900}.player-summary-copy{min-width:0}.player-summary-copy b,.player-summary-copy span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.player-summary-copy span{color:var(--muted);font-size:11px}.score-row{display:grid;gap:2px}.score-row small{color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.05em}.score-row.primary b{font-size:clamp(22px,4vw,34px);color:var(--text)}.score-row.supporting b{font-size:13px;color:var(--muted)}
*:focus-visible{outline:3px solid var(--gold);outline-offset:3px}.ds-table-wrap{max-width:100%;overflow-x:auto}
@media(max-width:760px){.ds-page-header{grid-template-columns:1fr;padding:18px}.ds-header-side{justify-items:start}.ds-freshness{text-align:left}.ds-actions{justify-content:flex-start}.ds-action{min-height:44px}.ds-recommendation{grid-template-columns:1fr}.ds-confidence{text-align:left}.ds-confidence b{display:inline;margin-right:6px}table{display:block;max-width:100%;overflow-x:auto}.manager-nav{position:fixed;z-index:30;left:0;right:0;bottom:0;margin:0;padding:7px 7px calc(7px + env(safe-area-inset-bottom));gap:3px;background:rgba(6,11,18,.98);border:0;border-top:1px solid var(--line);border-radius:0;box-shadow:0 -12px 30px rgba(0,0,0,.36)}.manager-nav a{flex-direction:column;gap:2px;min-height:50px;padding:5px 3px;border:0;border-radius:8px;font-size:10px}.manager-nav-icon{font-size:17px;line-height:1}.manager-nav a[aria-current="page"]{background:rgba(93,242,55,.09);color:var(--accent)}.footer{padding-bottom:88px}.ux-section-head{align-items:start;display:block}.ux-section-head p{margin-top:4px}}
"""

DESIGN_SYSTEM_CSS += """
.manager-nav a:before{color:var(--accent);font-size:15px}
.manager-nav a:nth-child(1):before{content:"⌂"}.manager-nav a:nth-child(2):before{content:"♜"}.manager-nav a:nth-child(3):before{content:"⇄"}.manager-nav a:nth-child(4):before{content:"◇"}.manager-nav a:nth-child(5):before{content:"⌕"}
@media(max-width:760px){.manager-nav a:before{font-size:17px;line-height:1}}
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
    if "front office intelligence system" in normalized:
        return PagePresentation(
            "Evaluate General Manager performance using results, process, context, recovery, and complete league history.",
            "General Manager intelligence",
            "View GM Rankings",
            "#gm-rankings",
            "League History",
            "/history",
        )
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


def account_page_header(title: str, *, purpose: str) -> str:
    """Render the reduced, public-safe account/onboarding page shell."""
    return (
        f'<header class="ds-page-header" data-dtos-component="page-header" '
        f'data-dtos-shell="account-onboarding" data-design-system="{DESIGN_SYSTEM_VERSION}">'
        '<div><div class="ds-eyebrow">DTOS — Account &amp; identity</div>'
        f'<h1>{escape(title)}</h1><p class="ds-purpose">{escape(purpose)}</p>'
        '<div class="ds-context">Secure Sleeper-backed front office access</div></div>'
        '</header>'
    )


def manager_navigation(title: str) -> str:
    """Render the five primary manager destinations and subordinate tools."""
    normalized = title.casefold()
    if title == "Home":
        active = "Home"
    elif "headquarters" in normalized or title in {"Teams", "My Team"}:
        active = "My Team"
    elif "trade" in normalized:
        active = "Trade"
    elif any(word in normalized for word in ("league", "matchup", "history", "transaction", "draft", "fois", "commissioner")):
        active = "League"
    elif "market" in normalized or "player" in normalized:
        active = "Market"
    else:
        active = ""
    primary = (("Home", "/"), ("My Team", "/teams"), ("Trade", "/trades"), ("League", "/league"), ("Market", "/market"))
    links = "".join(
        f'<a href="{href}"{" aria-current=\"page\"" if label == active else ""}>{label}</a>'
        for label, href in primary
    )
    secondary = (
        ("FOIS", "/fois"), ("Commissioner", "/commissioner"),
        ("History", "/history"), ("Transactions", "/transactions"),
        ("Draft Capital", "/picks"), ("Advanced", "/brain"),
        ("Calibration", "/valuation/calibration"), ("Settings", "/settings"),
    )
    tools = "".join(f'<a href="{href}">{label}</a>' for label, href in secondary)
    return f'<nav class="manager-nav" aria-label="Primary navigation">{links}</nav><details class="secondary-nav"><summary>More league tools</summary><div>{tools}</div></details>'


def player_summary(*, player_id: str, name: str, position: str | None, nfl_team: str | None, context: str | None = None) -> str:
    """Render a reusable provider-backed player identity with safe fallback."""
    safe_id = "".join(character for character in str(player_id) if character.isalnum() or character in {"-", "_"})
    initials = "".join(part[:1] for part in name.split()[:2]).upper() or "DT"
    metadata = " · ".join(item for item in (position, nfl_team, context) if item)
    image = (
        f'<img class="player-headshot" src="https://sleepercdn.com/content/nfl/players/{escape(safe_id)}.jpg" alt="{escape(name)} headshot" loading="lazy" onerror="this.hidden=true">'
        if safe_id else ""
    )
    return f'<span class="player-summary"><span class="player-portrait">{image}<span class="player-headshot-fallback" aria-hidden="true">{escape(initials)}</span></span><span class="player-summary-copy"><b>{escape(name)}</b><span>{escape(metadata or "Player details unavailable")}</span></span></span>'


def recommendation_panel(*, title: str, recommendation: str, confidence: int, primary_reason: str, evidence: tuple[str, ...], expected_impact: str, action_label: str, action_href: str, limitations: tuple[str, ...] = ()) -> str:
    evidence_html = "".join(f"<li>{escape(item)}</li>" for item in evidence) or "<li>No additional supporting evidence crossed the current confidence boundary.</li>"
    limitations_html = "".join(f"<li>{escape(item)}</li>" for item in limitations) or "<li>No material limitation was identified in the current cached evidence.</li>"
    return f'''<article class="ds-recommendation" data-dtos-component="recommendation"><div><div class="ds-eyebrow">Recommendation</div><h2>{escape(title)}</h2><p>{escape(recommendation)}</p><p><b>Primary reason:</b> {escape(primary_reason)}</p><p><b>Expected impact:</b> {escape(expected_impact)}</p><a class="ds-action primary" href="{escape(action_href)}">{escape(action_label)}</a></div><div class="ds-confidence"><b>{confidence}%</b><span>Confidence</span></div><details><summary>Detailed Evidence</summary><h3>Supporting Evidence</h3><ul>{evidence_html}</ul><h3>Limitations</h3><ul>{limitations_html}</ul></details></article>'''
