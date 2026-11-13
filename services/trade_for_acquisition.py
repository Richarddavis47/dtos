"""Bounded presentation selection from already evaluated exact-target offers.

No discovery, pricing, evaluation or acceptance policy lives here. Neutral cost
is read from the shared evaluator and checked against its admitted asset pool.
"""

from src.core.intelligence import trade_market_balance as market_balance
from src.core.intelligence import trade_pick_identity_errors
from services.trade_search_policy import ELIGIBLE, classify


def cost_evidence(row, assets, target):
    proposal = row["proposal"]
    sent, received = proposal["assets_sent"], proposal["assets_received"]
    unknown = {
        "availability": "unknown",
        "reason": "Complete compatible Neutral Market cost is unavailable for this assessment.",
    }
    if (
        target not in received
        or not sent
        or not received
        or len(set(sent + received)) != len(sent + received)
        or any(key not in assets for key in sent + received)
    ):
        return unknown
    for ids, owner in (
        (sent, proposal["active_roster_id"]),
        (received, proposal["partner_roster_id"]),
    ):
        if any(
            assets[key].source_roster_id != owner
            or (
                assets[key].kind == "pick"
                and (
                    any(
                        value is None
                        for value in (
                            assets[key].season,
                            assets[key].round,
                            assets[key].original_roster_id,
                        )
                    )
                    or trade_pick_identity_errors(assets[key])
                )
            )
            for key in ids
        ):
            return unknown
    evidence = (row.get("evaluation") or {}).get("market_evidence") or {}
    try:
        calculated = market_balance(
            tuple(assets[key] for key in sent), tuple(assets[key] for key in received)
        )
    except (ValueError, TypeError):
        return unknown
    if (
        calculated["availability"] != "full"
        or evidence.get("availability") != "full"
        or evidence.get("unit") != calculated["unit"]
        or any(
            (evidence.get(side) or {}).get("availability") != "full"
            or (evidence.get(side) or {}).get("total") != calculated[side]["total"]
            for side in ("sent", "received")
        )
    ):
        return unknown
    extras = [key for key in received if key != target]
    return {
        "availability": "full",
        "unit": calculated["unit"],
        "outgoing": calculated["sent"]["total"],
        "incoming": calculated["received"]["total"],
        "net_received_minus_sent": calculated["difference"],
        "extra_received_asset_ids": extras,
        "extra_received_value": market_balance(
            (), tuple(assets[key] for key in extras)
        )["received"]["total"],
    }


def select_offers(ranked, assets, target, distinct, *, limit=3):
    """Keep strategic leader and cheapest fully priced eligible construction.

    Input order is the existing strategy/preference order. Ties keep that order.
    Diversity can fill spare places, but cannot remove either leader. No row is
    duplicated, even when both roles belong to the same exact package.
    """
    rows = [
        row
        for row in ranked
        if classify(row["evaluation"]) in ELIGIBLE
        and target in row["proposal"]["assets_received"]
    ]
    if not rows:
        return []
    costs = [cost_evidence(row, assets, target) for row in rows]
    priced = [i for i, cost in enumerate(costs) if cost["availability"] == "full"]
    cheapest = min(priced, key=lambda i: costs[i]["outgoing"]) if priced else None
    chosen = [0] + ([cheapest] if cheapest not in (None, 0) else [])
    diversified = distinct(rows, assets)
    shapes, rest = {}, []
    for row in diversified:
        p = row["proposal"]
        shape = tuple(
            tuple(sorted(assets[key].kind for key in p[side]))
            for side in ("assets_sent", "assets_received")
        )
        if shape in shapes:
            rest.append(row)
        else:
            shapes[shape] = row
    index_by_object = {id(row): i for i, row in enumerate(rows)}
    for row in [*shapes.values(), *rest]:
        index = index_by_object[id(row)]
        if index not in chosen and len(chosen) < limit:
            chosen.append(index)
    result = []
    for i in chosen[:limit]:
        roles = (["best_fit"] if i == 0 else []) + (
            ["lowest_cost"] if i == cheapest else []
        )
        result.append(
            {
                **rows[i],
                "acquisition_comparison": {
                    "roles": roles,
                    "cost": costs[i],
                    "eligible_assessed": len(rows),
                    "cost_comparable_assessed": len(priced),
                    "lowest_cost_ties": sum(
                        costs[j]["outgoing"] == costs[i]["outgoing"] for j in priced
                    )
                    if i == cheapest
                    else 0,
                    "basis": "gross outgoing Neutral Market cost; bounded eligible assessed offers only",
                },
            }
        )
    return result
