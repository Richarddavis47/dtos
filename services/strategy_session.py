"""Read explicit account goals, with read-only legacy session compatibility."""

import base64
import hashlib
import json

from src.platform.account_context import current_account

COOKIE = "dtos_strategy"
STRATEGIES = ("", "WIN NOW", "RETOOL", "REBUILD")
MAX_CONTEXTS = 64


def strategy_scope():
    account = current_account()
    identity = (
        (account.account_id, account.session_id) if account else ("local", "local")
    )
    return hashlib.sha256(
        json.dumps(identity, separators=(",", ":")).encode()
    ).hexdigest()


def selected_strategy(raw, league_id, roster_id):
    """Client intent is not evidence; admit only this authenticated context."""
    account = current_account()
    if (
        account
        and account.membership
        and account.membership.league_id == league_id
        and account.membership.roster_id == roster_id
        and getattr(account, "franchise_goal_revision", 0) > 0
    ):
        return (
            getattr(account, "franchise_goal", None)
            if getattr(account, "franchise_goal", None) in STRATEGIES
            else ""
        )
    if not raw or len(raw) > 3800:
        return ""
    try:
        value = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        rows = value.get("rows")
        if (
            value.get("scope") != strategy_scope()
            or not isinstance(rows, list)
            or len(rows) > MAX_CONTEXTS
        ):
            return ""
        key = f"{league_id}:{roster_id}"
        for row in rows:
            if isinstance(row, list) and len(row) == 2 and row[0] == key:
                return row[1] if row[1] in STRATEGIES else ""
    except (ValueError, TypeError, AttributeError):
        pass
    return ""
