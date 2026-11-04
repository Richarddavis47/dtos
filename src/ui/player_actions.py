"""Ownership labels and supported player action links shared by manager views."""
from html import escape
from urllib.parse import urlencode


def player_action(ownership: dict, player_id: str, active_roster_id: int) -> tuple[str, str]:
    for capability, workflow, label in (("SHOP_ASSET", "shop", "Shop Asset"), ("TRADE_FOR", "trade-for", "Trade For")):
        if capability in ownership["actions"]:
            query = urlencode({"front_office": active_roster_id, "asset_id": player_id,
                               "owner_roster_id": ownership["owner"]["roster_id"]})
            return label, f"/trades/{workflow}?{query}"
    return "", ""


def player_actions_html(ownership: dict, player_id: str, active_roster_id: int) -> str:
    label, href = player_action(ownership, player_id, active_roster_id)
    action = f'<a class="ds-action primary" href="{escape(href)}">{label}</a>' if href else ""
    owner = ownership["owner"]
    franchise = f'<a class="ds-action" href="/teams/{owner["roster_id"]}">View owning franchise</a>' if owner else ""
    reason = f'<p class="muted">{escape(ownership["reason"])}</p>' if ownership["reason"] else ""
    controls = f'<div class="ds-actions">{action}{franchise}</div>' if action or franchise else ""
    return (f'<div class="player-ownership" data-ownership-state="{ownership["state"]}">'
            f'<span class="pill player-ownership-label">{escape(ownership["label"])}</span>{reason}{controls}</div>')
