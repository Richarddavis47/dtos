"""Bounded, read-only news over prepared Sleeper transactions and Market facts.

No provider calls, historical archive preparation, preference writes or scoring.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any

from services.transactions import normalize_transactions
from src.core.history_context.timestamps import canonical_utc_timestamp
from src.core.valuation.calibration import cached_market_facts
from src.core.data_platform.pick_quotes import canonical_pick_market, select_pick_quote
from src.core.valuation.normalization import _freshness
from src.core.valuation.source_time import market_times
from src.core.valuation.config import NORMALIZATION_VERSION
from src.core.intelligence.pick_context import assess_pick_range

WINDOW = timedelta(hours=168)
CARD_LIMIT = 6
BUCKET_LIMIT = 19  # Existing active-season Sleeper buckets, never an archive fetch.
ROW_LIMIT = 10_000


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def completion_clock(raw, now):
    """A completed row's status_updated is a status observation, not creation.

    Sleeper does not publish a separately verified completed_at field. Its latest
    status-update time, when completed and not before creation, qualifies this
    feed with that explicit provenance. Never promote creation-only evidence.
    """
    if str(raw.get("status") or "").casefold() not in {"complete", "completed"}:
        return None, "Not a confirmed completed transaction"
    stamp = canonical_utc_timestamp(raw.get("status_updated"))
    if not stamp:
        return None, "Completion time unavailable; creation alone is insufficient"
    completed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    created = canonical_utc_timestamp(raw.get("created"))
    if completed > now or (
        created and completed < datetime.fromisoformat(created.replace("Z", "+00:00"))
    ):
        return None, "Future or contradictory completion clock"
    return (
        completed,
        "Sleeper status-update timestamp on a completed transaction; not a separately verified completed-at clock",
    )


def recent_candidates(data, *, now=None):
    """Select time-qualified rows on EVERY read, including warm cached Home."""
    now = now or datetime.now(timezone.utc)
    league = str((data.get("league") or {}).get("league_id") or "")
    buckets = data.get("season_transactions") or {}
    rows, limitations = [], []
    if isinstance(buckets, dict):
        keys = sorted(
            buckets, key=lambda k: int(k) if str(k).isdigit() else -1, reverse=True
        )
        if len(keys) > BUCKET_LIMIT:
            limitations.append(
                "Only the latest 19 prepared transaction buckets are inspected."
            )
        for key in keys[:BUCKET_LIMIT]:
            bucket = buckets[key]
            if isinstance(bucket, list):
                rows.extend(bucket)
            else:
                limitations.append(
                    "A prepared transaction period is unavailable; this is not a complete archive."
                )
    active = data.get("transactions") or []
    if isinstance(active, list):
        rows.extend(active)
    if len(rows) > ROW_LIMIT:
        limitations.append(
            "Prepared transaction row limit reached; additional source rows are not represented."
        )
    by_id, conflicts = {}, set()
    untimed = 0
    for raw in rows[:ROW_LIMIT]:
        if not isinstance(raw, dict) or raw.get("type") != "trade":
            continue
        if str(raw.get("league_id") or league) != league:
            continue
        identity = str(raw.get("transaction_id") or "")
        if not identity or len(identity) > 100:
            continue
        evidence = {k: v for k, v in raw.items() if k not in {"week", "leg"}}
        if identity in by_id and by_id[identity] != evidence:
            conflicts.add(identity)
        by_id[identity] = evidence
    candidates = []
    for identity, raw in by_id.items():
        if identity in conflicts:
            limitations.append(
                "Conflicting prepared copies of a transaction are withheld until source reconciliation."
            )
            continue
        clock, provenance = completion_clock(raw, now)
        if clock is None:
            if str(raw.get("status") or "").casefold() in {"complete", "completed"}:
                untimed += 1
            continue
        if now - WINDOW < clock <= now:
            candidates.append(
                {
                    "raw": raw,
                    "completed_at": clock.isoformat(),
                    "clock_provenance": provenance,
                }
            )
    if untimed:
        limitations.append(
            f"{untimed} completed trade(s) lack eligible completion-time evidence and are withheld from this dated feed."
        )
    candidates.sort(
        key=lambda r: (r["completed_at"], str(r["raw"]["transaction_id"])), reverse=True
    )
    return candidates, list(dict.fromkeys(limitations))


def news_identity(data, candidates, now):
    """One compatible publication fingerprint, not each player's distinct ID.

    Minute boundary also rechecks existing quote freshness. Rolling eligibility
    is resolved before this key, so expiration never waits for another sync.
    """
    market = data.get("market_data") or {}
    player_ids = {
        str(pid)
        for c in candidates
        for field in ("adds", "drops")
        for pid in c["raw"].get(field) or {}
    }
    freshness = [
        (
            provider,
            pid,
            _freshness(market_times(table[pid])["source_updated_at"], provider),
        )
        for provider, table in (market.get("providers") or {}).items()
        for pid in sorted(player_ids)
        if isinstance(table.get(pid), dict)
    ]
    quotes = [q for rows in (market.get("pick_quotes") or {}).values() for q in rows]
    # Reuse source admission even inside a minute: an expired prepared quote
    # cannot remain comparable beside a newly read canonical Market page.
    quote_admission = [
        select_pick_quote(
            {
                "year": q.get("year"),
                "round": q.get("round"),
                "range_supported": q.get("pick_type") == "projected_range",
                "projected_range": q.get("range"),
                "exact_slot_established": q.get("pick_type") == "exact_slot",
                "exact_slot": q.get("exact_slot"),
            },
            [q],
            market_format="fc:12:2qb:ppr",
            now=now,
        )
        for q in quotes
    ]
    return _digest(
        [
            freshness,
            quote_admission,
            (data.get("league") or {}),
            data.get("teams"),
            data.get("players"),
            data.get("market_data"),
            candidates,
            int(now.timestamp() // 60),
        ]
    )


def _reference_identity(ref):
    return (ref.get("generation"), ref.get("version"), ref.get("method"))


def _comparison_references(market):
    refs = {}
    for provider, table in (market.get("providers") or {}).items():
        found = {
            _reference_identity(r.get("normalization_reference") or {})
            for r in table.values()
            if isinstance(r, dict) and r.get("value") is not None
        }
        refs[provider] = (
            next(iter(found))
            if len(found) == 1
            and all(all(bool(part) for part in ref) for ref in found)
            else None
        )
    return refs


def build_news(data: dict[str, Any], candidates, limitations, *, now=None):
    """Batch canonical values once; no current ownership assumption about actors."""
    now = now or datetime.now(timezone.utc)
    league = str((data.get("league") or {}).get("league_id") or "")
    market = data.get("market_data") or {}
    snapshot = _digest([league, market])
    player_ids = {
        str(pid)
        for item in candidates
        for field in ("adds", "drops")
        for pid in (item["raw"].get(field) or {})
    }
    facts = cached_market_facts(market, player_ids)
    references = _comparison_references(market)
    teams = {str(t.get("roster_id")): t for t in data.get("teams") or []}
    ledger = {
        (
            str(p.get("season", p.get("year"))),
            str(p.get("round")),
            str(p.get("original_roster_id", p.get("roster_id"))),
        ): p
        for t in teams.values()
        for p in t.get("picks_owned") or []
    }
    for pick in data.get("pick_ledger") or []:
        ledger[
            (
                str(
                    pick.get("season")
                    if pick.get("season") is not None
                    else pick.get("year")
                ),
                str(pick.get("round")),
                str(pick.get("original_roster_id")),
            )
        ] = pick
    cards = []
    for item in candidates:
        raw = item["raw"]
        display_raw = {**raw, "created": 0}
        try:
            normalized = normalize_transactions(
                {**data, "transactions": [display_raw]}
            )[0]
        except (ValueError, TypeError, AttributeError):
            limitations = [
                *limitations,
                "A completed trade has malformed consideration; its news card is withheld, independent Home content remains available.",
            ]
            continue
        assets, seen, invalid = [], set(), False
        for asset in normalized["assets"]:
            sender, receiver = asset["source_id"], asset["destination_id"]
            if sender not in teams or receiver not in teams or sender == receiver:
                invalid = True
                continue
            value, compatible, evidence = None, False, {}
            if asset["kind"] == "player":
                identity = "player:" + asset["player_id"]
                if asset["label"] == asset["player_id"]:
                    asset["label"] = "Player name unavailable"
                fact = facts[asset["player_id"]]
                value, evidence = fact.value, fact.to_dict()
                compatible = value is not None and bool(fact.evidence_coverage)
                for provider in fact.evidence_coverage:
                    row = (market.get("providers") or {}).get(provider, {}).get(
                        asset["player_id"]
                    ) or {}
                    ref = row.get("normalization_reference") or {}
                    compatible = (
                        compatible
                        and bool(references.get(provider))
                        and _reference_identity(ref) == references[provider]
                        and ref.get("version") == NORMALIZATION_VERSION
                        and ref.get("provider") == provider
                        and ref.get("raw_value") == float(row["value"])
                        and ref.get("method")
                        in {"provider_range_linear", "provider_range_70_percentile_30"}
                    )
            else:
                identity = asset["canonical_pick_id"]
                pick = next(
                    (
                        p
                        for p in raw.get("draft_picks") or []
                        if f"PICK-{p.get('season')}-R{p.get('round')}-ORIG{p.get('roster_id')}"
                        == identity
                    ),
                    {},
                )
                key = (
                    str(pick.get("season")),
                    str(pick.get("round")),
                    str(pick.get("roster_id")),
                )
                # Only the exact current ledger can supply range/slot context.
                try:
                    context = (
                        ledger.get(
                            key,
                            {"year": int(pick["season"]), "round": int(pick["round"])},
                        )
                        if identity
                        else {}
                    )
                except (ValueError, TypeError, KeyError):
                    context = {}
                    identity = None
                context = assess_pick_range(context, league_id=league)
                evidence = (
                    canonical_pick_market(context, market, now=now) if identity else {}
                )
                value = evidence.get("normalized_market_price")
                quote = evidence.get("quote") or {}
                compatible = (
                    value is not None
                    and bool(references.get(quote.get("provider")))
                    and _reference_identity(quote.get("normalization_reference") or {})
                    == references.get(quote.get("provider"))
                )
                asset["label"] += " · originally " + str(
                    asset.get("original") or "original franchise unavailable"
                )
            if not identity:
                invalid = True
                continue
            directed = (identity, sender, receiver)
            if directed in seen:
                continue
            if any(a["identity"] == identity for a in assets):
                invalid = True  # One original asset cannot have competing legs.
                continue
            seen.add(directed)
            assets.append(
                {
                    **asset,
                    "identity": identity,
                    "value": value,
                    "comparable": bool(compatible),
                    "evidence": evidence,
                }
            )
        cash_seen = set()
        for cash in raw.get("waiver_budget") or []:
            from src.core.history_context.results import number

            amount = number(cash.get("amount"))
            sender, receiver = str(cash.get("sender")), str(cash.get("receiver"))
            if (
                amount is None
                or amount < 0
                or sender not in teams
                or receiver not in teams
                or sender == receiver
            ):
                invalid = True
                continue
            key = (sender, receiver, amount)
            if key in cash_seen:
                continue
            cash_seen.add(key)
            assets.append(
                {
                    "kind": "faab",
                    "label": f"{amount:g} FAAB",
                    "identity": f"faab:{sender}:{receiver}:{amount}",
                    "source_id": sender,
                    "destination_id": receiver,
                    "value": None,
                    "comparable": False,
                }
            )
        participants = sorted(
            set(normalized["roster_ids"])
            | {a["source_id"] for a in assets}
            | {a["destination_id"] for a in assets}
        )
        sides = [
            {
                "roster_id": rid,
                "name": str(
                    teams.get(rid, {}).get("team_name") or "Franchise name unavailable"
                ),
                "received": [a for a in assets if a["destination_id"] == rid],
                "sent": [a for a in assets if a["source_id"] == rid],
            }
            for rid in participants
        ]
        priced = [a for a in assets if a["kind"] != "faab"]
        complete = bool(priced) and not invalid and all(a["comparable"] for a in priced)
        for side in sides:
            selected = [a for a in side["received"] if a["kind"] != "faab"]
            side["known_count"] = sum(a["value"] is not None for a in selected)
            side["known_total"] = sum(
                a["value"] for a in selected if a["value"] is not None
            )
            side["total"] = side["known_total"] if complete else None
        cards.append(
            {
                "id": str(raw["transaction_id"]),
                "league_id": league,
                "season": (data.get("league") or {}).get("season"),
                **{k: v for k, v in item.items() if k != "raw"},
                "sides": sides,
                "complete": complete,
                "combined_total": sum(a["value"] for a in priced) if complete else None,
                "pricing_state": "Comparable current values"
                if complete
                else "Size unknown · incomplete or incompatible pricing",
                "has_faab": bool(cash_seen),
                "consideration_partial": invalid,
                "snapshot": snapshot,
                "source": "Sleeper completed transaction; prepared selected-league evidence. Franchise names are season-source observations; exact trade-time manager tenure or renames are not established.",
            }
        )
    ranked = sorted(
        (c for c in cards if c["complete"]),
        key=lambda c: (
            -c["combined_total"],
            -datetime.fromisoformat(c["completed_at"]).timestamp(),
            c["id"],
        ),
    )
    unranked = sorted(
        (c for c in cards if not c["complete"]),
        key=lambda c: (-datetime.fromisoformat(c["completed_at"]).timestamp(), c["id"]),
    )
    # Reserve one slot for honest unranked news, then use remaining capacity.
    selected = ranked[: CARD_LIMIT - bool(unranked)]
    selected += unranked[: CARD_LIMIT - len(selected)]
    return {
        "cards": selected,
        "eligible_count": len(cards),
        "unranked_count": len(unranked),
        "league_id": league,
        "league_name": str((data.get("league") or {}).get("name") or "Selected league"),
        "snapshot": snapshot,
        "limitations": limitations,
        "ranking_policy": "Complete comparable deals: biggest first. Size-unknown deals: recent first, with at least one reserved slot when available. FAAB is shown separately, excluded from Market totals.",
    }
