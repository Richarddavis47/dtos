"""Bounded ownership-only presentation. No capital scoring or source acquisition."""

import hashlib
import json


def _integer(value):
    if isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
        raise ValueError("Ambiguous pick identity")
    return int(value)


def _pick(row, league_id, rounds, rosters):
    if row.get("league_id") not in (None, league_id):
        raise ValueError("Incompatible pick league")
    year = _integer(row.get("year", row.get("season")))
    if (
        row.get("year") is not None
        and row.get("season") is not None
        and _integer(row["season"]) != year
    ):
        raise ValueError("Conflicting pick season")
    round_number = _integer(row.get("round"))
    original, owner = (
        _integer(row.get("original_roster_id")),
        _integer(row.get("current_owner_id")),
    )
    if round_number > rounds or original not in rosters or owner not in rosters:
        raise ValueError("Pick identity or configured round unavailable")
    return (year, round_number, original), owner


def inventory_baseline(data, active):
    """Reconcile the existing canonical ledger with native transfers and team views.

    Completeness is limited to seasons actually retained in that ledger. Never
    mint a pick/season to fill its grid. Legacy/partial publications stay unknown.
    """
    league = data.get("league") or {}
    result = dict(
        schema=1,
        league=str(league.get("league_id") or ""),
        roster=active,
        complete=False,
        before=[],
        seasons=[],
        rounds=0,
        names={},
        generation=None,
        reason="Compatible complete pick inventory is unavailable; remaining totals are unknown.",
    )
    try:
        teams = data.get("teams") or []
        rosters = {_integer(t.get("roster_id")): t for t in teams}
        if len(rosters) != len(teams):
            raise ValueError("Duplicate franchise identity")
        result["names"] = {
            str(r): str(t.get("team_name") or r)[:100] for r, t in rosters.items()
        }
        configured_rounds = (league.get("settings") or {}).get("draft_rounds")
        if configured_rounds is None:
            return result
        rounds = _integer(configured_rounds)
        if not result["league"] or active not in rosters or rounds > 20:
            return result
        ledger, native = data.get("pick_ledger"), data.get("traded_picks")
        if (
            not isinstance(ledger, list)
            or not ledger
            or len(ledger) > 2048
            or not isinstance(native, list)
            or len(native) > 2048
        ):
            return result
        entries, transfers = {}, {}
        for row in ledger:
            key, owner = _pick(row, result["league"], rounds, rosters)
            if key in entries:
                raise ValueError("Duplicate or conflicting pick inventory")
            entries[key] = owner
        for row in native:
            if _integer(row.get("season")) <= _integer(league.get("season")):
                continue  # Historical transfers are outside this retained future inventory.
            key, owner = _pick(
                dict(
                    row,
                    original_roster_id=row.get("roster_id"),
                    current_owner_id=row.get("owner_id"),
                ),
                result["league"],
                rounds,
                rosters,
            )
            if key in transfers or key not in entries:
                raise ValueError("Duplicate or unavailable transfer identity")
            transfers[key] = owner
        if any(owner != transfers.get(key, key[2]) for key, owner in entries.items()):
            raise ValueError("Canonical/native pick ownership conflicts")
        owned = {}
        for roster, team in rosters.items():
            if not isinstance(team.get("picks_owned"), list):
                return result
            for row in team["picks_owned"]:
                key, owner = _pick(row, result["league"], rounds, rosters)
                if owner != roster or key in owned or entries.get(key) != owner:
                    raise ValueError("Duplicate or conflicting team pick ownership")
                owned[key] = owner
        seasons = sorted({key[0] for key in entries})
        complete = owned == entries and len(entries) == len(seasons) * rounds * len(
            rosters
        )
        body = [
            result["league"],
            rounds,
            sorted(entries.items()),
            sorted((r, str(t.get("team_name") or r)) for r, t in rosters.items()),
        ]
        result["_owners"] = {
            f"{k[0]}-R{k[1]}-{k[2]}": owner for k, owner in entries.items()
        }
        result.update(
            generation=hashlib.sha256(
                json.dumps(body, separators=(",", ":")).encode()
            ).hexdigest(),
            complete=complete,
            before=[
                list(key) for key, owner in sorted(entries.items()) if owner == active
            ],
            seasons=seasons,
            rounds=rounds,
            names={
                str(r): str(t.get("team_name") or r)[:100] for r, t in rosters.items()
            },
            reason="Counts cover only the retained seasons and configured rounds."
            if complete
            else result["reason"],
        )
    except (ValueError, TypeError, AttributeError):
        result.update(
            complete=False,
            before=[],
            generation=None,
            reason="Pick identities or ownership conflict; remaining totals and ambiguous movements are withheld.",
            invalid=True,
        )
    return result


def capital_record(baseline, proposal):
    row = {k: v for k, v in baseline.items() if not k.startswith("_")}
    sent, received = [], []
    try:
        for assets, owner, target in [
            (proposal.assets_sent, proposal.active_roster_id, sent),
            (proposal.assets_received, proposal.partner_roster_id, received),
        ]:
            for asset in assets:
                if asset.kind != "pick":
                    continue
                key = [
                    _integer(asset.season),
                    _integer(asset.round),
                    _integer(asset.original_roster_id),
                ]
                if (
                    (
                        asset.asset_id in baseline.get("_owners", {})
                        and baseline["_owners"][asset.asset_id] != owner
                    )
                    or asset.current_owner_id != owner
                    or asset.source_roster_id != owner
                    or asset.asset_id != f"{key[0]}-R{key[1]}-{key[2]}"
                ):
                    raise ValueError("Unverified exchanged pick")
                target.append(key)
        keys = sent + received
        if len({tuple(k) for k in keys}) != len(keys) or row.get("invalid"):
            raise ValueError("Ambiguous exchanged pick")
        if row["complete"] and (
            any(k not in row["before"] for k in sent)
            or any(k in row["before"] for k in received)
            or any(k[0] not in row["seasons"] or k[1] > row["rounds"] for k in keys)
        ):
            raise ValueError("Exchanged pick conflicts with recorded inventory")
        row.update(sent=sent, received=received)
    except (ValueError, TypeError):
        row.update(
            complete=False,
            before=[],
            sent=[],
            received=[],
            invalid=True,
            reason="Exchanged pick ownership or identity cannot be reconciled; remaining totals are unknown.",
        )
    text = json.dumps(row, separators=(",", ":"))
    if len(text) > 10000:
        text = json.dumps(
            dict(
                schema=1,
                league=row["league"],
                roster=row["roster"],
                complete=False,
                sent=row.get("sent", []),
                received=row.get("received", []),
                invalid=row.get("invalid", False),
                reason="The inventory exceeds the bounded recorded-evidence size; totals are unknown.",
            )
        )
    return dict(
        characters=len(text),
        parts=[text[i : i + 1400] for i in range(0, len(text), 1400)],
    )
