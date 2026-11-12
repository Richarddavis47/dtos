"""Bounded presentation join of admitted Market movement and prepared roster need.

No ranking model, acquisition, lineup calculation, cache or runtime owner. Tokens
identify evidence; existing manager membership and target ownership authorize it.
"""

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from urllib.parse import urlencode

from services.team_trade_need import prepared_need
from src.core.intelligence.roster_diagnostics import prepared_diagnostics
from src.core.market_trends.current import current_comparison
from src.core.player_ownership import PlayerOwnershipIndex
from src.platform.account_context import current_account
from src.platform.league_context import current_league_context

SAMPLE_LIMIT = 10
CARD_LIMIT = 3


def _number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
    )


def need_context(data, roster_id, *, snapshot=None, reader=None):
    account = current_account()
    membership = account.membership if account else None
    league = str((data.get("league") or {}).get("league_id") or "")
    if (
        not membership
        or membership.league_id != league
        or membership.roster_id != roster_id
    ):
        return (
            None,
            "Personal relevance needs your authorized active franchise. Neutral Market information remains available.",
        )
    # Market can remain usable without a prepared analytical publication.
    # Do not ask diagnostics to resolve an absent runtime projection owner.
    from src.core.projection_intelligence import projection_service

    runtime = current_league_context()
    runtime_reader = (
        getattr(runtime, "projection", None) if runtime else projection_service
    )
    if runtime_reader is None:
        return (
            None,
            "Compatible prepared roster projections are unavailable for this league. Neutral Market information remains available.",
        )
    reader = reader or runtime_reader
    snapshot = reader.snapshot() if snapshot is None else snapshot
    if snapshot is None:
        return (
            None,
            "Compatible prepared roster projections are unavailable for this league. Neutral Market information remains available.",
        )
    diagnostic = prepared_diagnostics(data, snapshot, projection_reader=reader)
    need = prepared_need(data, roster_id, diagnostic)
    if need:
        return need, need["reason"]
    if not diagnostic:
        return (
            None,
            "A matching prepared roster comparison is unavailable for this league, week, scoring and availability. Neutral movement is still usable.",
        )
    row = (diagnostic.get("teams") or {}).get(str(roster_id)) or {}
    evidence = row.get("evidence") or {}
    reasons = list(dict.fromkeys(evidence.get("limitations") or []))[:2]
    if evidence.get("conclusion_state") != "current":
        return (
            None,
            "Roster evidence is provisional or incomplete; no current personalized relevance is established. "
            + " ".join(str(r)[:240] for r in reasons),
        )
    return (
        None,
        "No current supported starter or depth need maps to this view. This does not mean no useful trades exist.",
    )


def handoff_token(data, need, asset_id):
    asset = ((data.get("valuation_intelligence") or {}).get("assets") or {}).get(
        asset_id
    ) or {}
    value = ((asset.get("valuation_layers") or {}).get("market_value") or {}).get(
        "value"
    )
    evidence = current_comparison(data, asset_id, value)
    if not need or not evidence:
        return None
    return sha256(
        json.dumps(
            [need["fingerprint"], asset_id, evidence],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def admitted_handoff(data, roster_id, player_id, token):
    need, _ = need_context(data, roster_id)
    identity = "player:" + str(player_id)
    player = (data.get("players") or {}).get(str(player_id)) or {}
    if not need or player.get("position") != need["position"]:
        return None
    ownership = PlayerOwnershipIndex(data).resolve(str(player_id), roster_id)
    if (
        "TRADE_FOR" not in ownership.get("actions", ())
        or handoff_token(data, need, identity) != token
    ):
        return None
    return {
        **need,
        "asset_id": identity,
        "name": str(player.get("full_name") or player.get("name") or identity)[:100],
    }


def _age(stamp):
    try:
        observed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        observed = (
            observed if observed.tzinfo else observed.replace(tzinfo=timezone.utc)
        )
        days = (datetime.now(timezone.utc) - observed).total_seconds() / 86400
        return (
            f"about {int(days)} days since the comparison endpoint"
            if days >= 0
            else "Observation age unknown"
        )
    except (ValueError, TypeError, OverflowError):
        return "Observation age unknown"


def movement_inputs(rows):
    """Neutral, bounded DTO alongside the existing cached page; no runtime owner."""
    fields = (
        "asset_id",
        "magnitude",
        "comparison_reasons",
        "comparison_units",
        "comparison_start_at",
        "comparison_end_at",
        "checkpoint_count",
        "comparison_scope",
        "current_qualification",
    )
    result = []
    for row in rows[:SAMPLE_LIMIT]:
        trend = row.get("market_trend") or {}
        provenance = trend.get("provenance") or {}
        result.append(
            dict(
                asset_id=row.get("asset_id"),
                display_name=row.get("display_name"),
                position=row.get("position"),
                values={"market_value": (row.get("values") or {}).get("market_value")},
                market_trend={
                    **{key: trend.get(key) for key in fields},
                    "provenance": {
                        "current_endpoint_comparable": provenance.get(
                            "current_endpoint_comparable"
                        ),
                        "current_evidence": {
                            "providers": (
                                (provenance.get("current_evidence") or {}).get(
                                    "providers"
                                )
                                or []
                            )[:5]
                        },
                    },
                },
            )
        )
    return result


def movement_view(
    data, rows, roster_id, ownership, *, market_data=None, snapshot=None, reader=None
):
    need, reason = need_context(data, roster_id, snapshot=snapshot, reader=reader)
    sample = rows[:SAMPLE_LIMIT]
    candidates = []
    for row in sample:
        trend = row.get("market_trend") or {}
        if (
            not _number(trend.get("magnitude"))
            or trend.get("comparison_reasons")
            or trend.get("comparison_units") != "0-1000"
            or not trend.get("comparison_start_at")
            or not trend.get("comparison_end_at")
        ):
            continue
        identity = str(row.get("asset_id") or "")
        if trend.get("asset_id") != identity:
            continue
        resolved = (
            ownership.resolve(identity[7:], roster_id)
            if identity.startswith("player:")
            else {}
        )
        related = bool(
            need
            and (trend.get("provenance") or {}).get("current_endpoint_comparable")
            is True
            and row.get("position") == need["position"]
            and "TRADE_FOR" in resolved.get("actions", ())
        )
        token = handoff_token(market_data or data, need, identity) if related else None
        providers = ((trend.get("provenance") or {}).get("current_evidence") or {}).get(
            "providers"
        ) or ()
        source = (
            "Canonical Market · " + ", ".join(str(p)[:80] for p in providers[:5])
            if providers
            and (trend.get("provenance") or {}).get("current_endpoint_comparable")
            else "Retained canonical Market observations; provider identities are not included in this summary"
        )
        href = (
            "/trades/trade-for?"
            + urlencode(
                dict(
                    front_office=roster_id,
                    asset_id=identity[7:],
                    owner_roster_id=resolved["owner"]["roster_id"],
                    team_need=token,
                )
            )
            if token
            else None
        )
        candidates.append(
            dict(
                asset_id=identity,
                name=str(row.get("display_name") or identity)[:100],
                trend=trend,
                related=related,
                href=href,
                source=source,
                age=_age(trend["comparison_end_at"]),
                value=(row.get("values") or {}).get("market_value"),
            )
        )
    related = [row for row in candidates if row["related"]]
    return dict(
        need=need,
        reason=reason,
        sampled=len(sample),
        cards=(related or candidates)[:CARD_LIMIT],
        has_related=bool(related),
    )
