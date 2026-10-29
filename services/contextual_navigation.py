"""Presentation-only, session/league/franchise-bound navigation identity.

No runtime acquisition, source reads, preference writes or authorization grants.
"""

from html import escape

from src.platform.account_context import current_account
from services.trade_workspace_context import workspace_binding


def navigation_context():
    account = current_account()
    if account is None:
        return None
    member = account.membership
    league = str(member.league_id) if member else ""
    roster = member.roster_id if member else None
    return {
        "scope": workspace_binding(league, roster),
        "team": f"/teams/{roster}" if roster is not None and roster > 0 else "/teams",
    }


def navigation_markup():
    context = navigation_context()
    if context is None:
        return "", ""
    back = (
        '<a id="dtos-back" class="dtos-back" href="/" aria-label="Go back to Home">'
        '<span aria-hidden="true">←</span> Back</a>'
    )
    head = (
        f'<meta name="dtos-navigation-scope" content="{escape(context["scope"], quote=True)}">'
        f'<meta name="dtos-navigation-team" content="{escape(context["team"], quote=True)}">'
        '<link rel="stylesheet" href="/static/css/contextual_navigation.css">'
        '<script src="/static/js/contextual_navigation.js" defer></script>'
    )
    return back, head


def with_back(header, back):
    if not back:
        return header
    start = header.find("<h1")
    end = header.find("</h1>", start)
    if start < 0 or end < 0:
        return header
    return (
        header[:start]
        + '<div class="dtos-page-title">'
        + back
        + header[start : end + 5]
        + "</div>"
        + header[end + 5 :]
    )
