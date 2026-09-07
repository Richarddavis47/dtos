"""DTOS Design System v2 server-rendered presentation contracts."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .theme import DESIGN_SYSTEM_CSS as DESIGN_SYSTEM_CSS

DESIGN_SYSTEM_VERSION = "2.0"


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
    if "executive profile" in normalized:
        return PagePresentation("Review this manager's process, results, confidence, and historical evidence in the active league.", "General Manager profile", "GM Leaderboard", "/fois", "League History", "/history")
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
    if "history" in normalized or "historical" in normalized or "season archive" in normalized:
        return PagePresentation("Understand how league and franchise decisions produced today's position.", "Historical evidence", "Open Team HQ", "/teams")
    if "draft" in normalized or "pick" in normalized:
        return PagePresentation("Understand the league's draft-capital ownership and strategic flexibility.", "Draft capital", "Open Trade Center", "/trades")
    if "transaction" in normalized:
        return PagePresentation("See what changed across the league and which assets moved.", "League activity", "Refresh Transactions", "/transactions?refresh=1")
    if "setting" in normalized:
        return PagePresentation("Review league rules, synchronization state, and application information.", "League configuration", "Review Sync Status", "/settings#sync-status")
    return PagePresentation("Navigate the league and open the Front Office question that matters now.", "League overview", "Open Team HQ", "/teams")


def page_header(title: str, *, league_name: str, last_updated: str) -> str:
    if title == "Home":
        return f'<header class="ds-page-header ds-overview-header" data-dtos-component="page-header" data-design-system="{DESIGN_SYSTEM_VERSION}"><h1>Home</h1><span class="ds-context">{escape(league_name)}</span></header>'
    presentation = _presentation(title)
    return f'''<header class="ds-page-header" data-dtos-component="page-header" data-design-system="{DESIGN_SYSTEM_VERSION}"><div><h1>{escape(title)}</h1><details class="ds-page-guide"><summary>How it works</summary><p class="ds-purpose">{escape(presentation.purpose)}</p><div class="ds-context">{escape(league_name)} · {escape(presentation.context)}</div><div class="ds-freshness">League Sync: <b>{escape(last_updated or "Not synchronized yet")}</b></div></details></div><div class="ds-header-side"><div class="ds-actions"><a class="ds-action primary" href="{escape(presentation.primary_href)}">{escape(presentation.primary_label)}</a><a class="ds-action" href="{escape(presentation.secondary_href)}">{escape(presentation.secondary_label)}</a></div></div></header>'''


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


def manager_navigation(title: str, *, roster_id: int | None = None) -> str:
    """Render the five primary manager destinations and subordinate tools."""
    normalized = title.casefold()
    if title == "Home":
        active = "Home"
    elif "headquarters" in normalized or title in {"Teams", "My Team"}:
        active = "My Team"
    elif "trade" in normalized:
        active = "Trade"
    elif any(word in normalized for word in ("league", "matchup", "history", "historical", "season archive", "transaction", "draft", "fois", "commissioner", "front office intelligence system", "executive profile")):
        active = "League"
    elif "market" in normalized or "player" in normalized:
        active = "Market"
    else:
        active = ""
    team_href = f"/teams/{roster_id}" if roster_id is not None and roster_id > 0 else "/teams"
    primary = (("Home", "/"), ("My Team", team_href), ("Trade", "/trades"), ("League", "/league"), ("Market", "/market"))
    icons = {
        "Home": '<path d="m3 10 9-7 9 7v11h-6v-7H9v7H3Z"/>',
        "My Team": '<path d="m8 3-5 3 3 5 2-1v11h8V10l2 1 3-5-5-3c0 4-8 4-8 0Z"/>',
        "Trade": '<path d="M3 7h17m-4-4 4 4-4 4M21 17H4m4-4-4 4 4 4"/>',
        "League": '<path d="M8 3h8v5a4 4 0 0 1-8 0ZM8 5H4v2a4 4 0 0 0 4 4m8-6h4v2a4 4 0 0 1-4 4m-4 1v6m-4 3h8m-6-3h4"/>',
        "Market": '<path d="M4 20V10m6 10V4m6 16v-8m5 8H2"/>',
    }
    links = "".join(
        f'<a href="{href}"{" aria-current=\"page\"" if label == active else ""}><svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{icons[label]}</svg>{label}</a>'
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
    return f'''<article class="ds-recommendation" data-dtos-component="recommendation"><div><div class="ds-eyebrow">Recommendation</div><h2>{escape(title)}</h2><p>{escape(recommendation)}</p><p><b>Primary reason:</b> {escape(primary_reason)}</p><a class="ds-action primary" href="{escape(action_href)}">{escape(action_label)}</a></div><div class="ds-confidence"><b>{confidence}%</b><span>Confidence</span></div><details><summary>Detailed Evidence</summary><h3>Expected impact:</h3><p>{escape(expected_impact)}</p><h3>Supporting Evidence</h3><ul>{evidence_html}</ul><h3>Limitations</h3><ul>{limitations_html}</ul></details></article>'''
