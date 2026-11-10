"""Read-only handoff over a matching, currently qualified roster diagnostic.

The fingerprint is freshness/context identity, never authorization. Membership
and the prepared diagnostic are checked again on the destination page.
"""

from hashlib import sha256
import json
from urllib.parse import urlencode

from services.trade_workspace_context import workspace_context
from src.core.intelligence.roster_diagnostics import POSITIONS, BENCH_SLOTS
from src.core.intelligence import lineup_slot_eligible
from src.platform.account_context import current_account


def supported_positions(data):
    slots = (
        data.get("roster_positions")
        or (data.get("league") or {}).get("roster_positions")
        or []
    )
    return [
        pos
        for pos in POSITIONS
        if any(
            str(slot).upper() not in BENCH_SLOTS
            and lineup_slot_eligible(pos, str(slot).upper())
            for slot in slots
        )
    ]


def prepared_need(data, roster_id, diagnostic):
    account = current_account()
    context = workspace_context(data, roster_id)
    membership = account.membership if account else None
    if (
        not membership
        or membership.league_id != context["league_id"]
        or membership.roster_id != roster_id
        or not diagnostic
        or diagnostic.get("league_id") != context["league_id"]
        or diagnostic.get("week") != data.get("week")
        or not diagnostic.get("generation")
        or not diagnostic.get("projection_generation")
    ):
        return None
    row = (diagnostic.get("teams") or {}).get(str(roster_id)) or {}
    for kind, flags in (
        ("starter", ("starter_need",)),
        ("depth", ("resilience_need", "quality_depth_need")),
    ):
        for pos in supported_positions(data):
            facts = (row.get("positions") or {}).get(pos) or {}
            evidence = facts.get("evidence") or {}
            if (
                not evidence.get("calculation_supported")
                or facts.get("conclusion_state") != "current"
                or not any(facts.get(flag) is True for flag in flags)
            ):
                continue
            reason = (
                f"Week {diagnostic['week']}: a supported {pos} addition can improve the legal starting lineup."
                if kind == "starter"
                else f"Week {diagnostic['week']}: prepared {pos} replacement evidence identifies a depth need, not a starter-upgrade verdict."
            )
            identity = [
                context["binding"],
                context["ownership_generation"],
                diagnostic["league_id"],
                diagnostic["week"],
                diagnostic["generation"],
                diagnostic["projection_generation"],
                pos,
                kind,
            ]
            fingerprint = sha256(
                json.dumps(identity, separators=(",", ":")).encode()
            ).hexdigest()
            return {
                "position": pos,
                "kind": kind,
                "reason": reason,
                "fingerprint": fingerprint,
                "href": "/trades/recommended?"
                + urlencode({"front_office": roster_id, "team_need": fingerprint}),
            }
    return None


def requested_position(data, value):
    if value in (None, "", "all"):
        return None
    if not isinstance(value, str) or value not in supported_positions(data):
        raise ValueError(
            "Choose an eligible Recommended Trades position or clear the filter."
        )
    return value


def position_matches(row, assets, position):
    return not position or any(
        (asset := assets.get(asset_id)) is not None
        and asset.kind == "player"
        and asset.position == position
        for asset_id in row["proposal"]["assets_received"]
    )
