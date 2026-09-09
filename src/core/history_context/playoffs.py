"""Source-backed postseason facts; never infer seeds from final placements."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def playoff_facts(bracket: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Reconcile only the winners bracket, including teams with first-round byes.

    Sleeper's ``p`` is a placement match, not a seed. Semifinals are the winner
    dependencies of the championship, not every game in the preceding round.
    Missing dependencies remain explicitly incomplete.
    """
    matches: dict[str, Mapping[str, Any]] = {}
    conflicting_matches = False
    for row in bracket:
        if row.get("m") is not None:
            key = str(row["m"])
            if key in matches and matches[key] != row:
                conflicting_matches = True
            matches[key] = row
    finals = [row for row in matches.values() if row.get("p") == 1]
    qualified = sorted({str(row[key]) for row in bracket for key in ("t1", "t2")
                        if isinstance(row.get(key), (int, str))})
    result: dict[str, Any] = {
        "qualified_roster_ids": qualified,
        "champion_roster_id": None, "runner_up_roster_id": None,
        "championship_roster_ids": [], "semifinal_roster_ids": [],
        "first_round_bye_roster_ids": [],
        "placements": {}, "reason_codes": [],
    }
    if conflicting_matches:
        result["reason_codes"] = ["bracket_match_identity_conflict"]
        return result
    # Sleeper documents both inline {w/l: match_id} and *_from forms.
    # Resolve only explicitly reported parent outcomes, never projected winners.
    resolved = []
    for row in matches.values():
        normalized = dict(row)
        for side in ("t1", "t2"):
            dependency = row.get(side) if isinstance(row.get(side), Mapping) else row.get(f"{side}_from")
            if isinstance(dependency, Mapping):
                normalized[f"{side}_from"] = dependency
                if not isinstance(row.get(side), (int, str)):
                    normalized[side] = None
                    if len(dependency) == 1:
                        outcome, match_id = next(iter(dependency.items()))
                        parent = matches.get(str(match_id))
                        value = parent.get(outcome) if parent and outcome in {"w", "l"} else None
                        if isinstance(value, (int, str)):
                            normalized[side] = value
        resolved.append(normalized)
    bracket = resolved
    matches = {str(row["m"]): row for row in bracket}
    finals = [row for row in bracket if row.get("p") == 1]
    qualified = sorted({str(row[key]) for row in bracket for key in ("t1", "t2")
                        if isinstance(row.get(key), (int, str))})
    result["qualified_roster_ids"] = qualified
    rounds = [row["r"] for row in bracket if isinstance(row.get("r"), int)]
    if rounds:
        opening = min(rounds)
        opening_teams = {str(row[key]) for row in bracket if row.get("r") == opening
                         for key in ("t1", "t2") if isinstance(row.get(key), (int, str))}
        result["first_round_bye_roster_ids"] = sorted(set(qualified) - opening_teams)
    if len(finals) != 1:
        result["reason_codes"] = ["championship_missing" if not finals else "championship_conflict"]
        return result
    final = finals[0]
    result["championship_roster_ids"] = [str(final[key]) for key in ("t1", "t2")
                                          if isinstance(final.get(key), (int, str))]
    result["champion_roster_id"] = final.get("w")
    result["runner_up_roster_id"] = final.get("l")
    if final.get("w") is None or final.get("l") is None:
        result["reason_codes"].append("championship_unresolved")
    semifinalists: set[str] = set()
    for key in ("t1_from", "t2_from"):
        dependency = final.get(key)
        preceding = matches.get(str(dependency.get("w"))) if isinstance(dependency, Mapping) and "w" in dependency else None
        if preceding is None:
            result["reason_codes"].append("semifinal_dependency_unavailable")
            continue
        semifinalists.update(str(preceding[side]) for side in ("t1", "t2") if isinstance(preceding.get(side), (int, str)))
    result["semifinal_roster_ids"] = sorted(semifinalists)
    if len(semifinalists) != 4:
        result["reason_codes"].append("semifinal_participants_incomplete")
    conflicting_placements: set[str] = set()
    for row in bracket:
        placement = row.get("p")
        if isinstance(placement, int) and placement > 0:
            for rank, key in ((placement, "w"), (placement + 1, "l")):
                if row.get(key) is not None:
                    rank_key = str(rank)
                    if rank_key in conflicting_placements:
                        continue
                    existing = result["placements"].get(rank_key)
                    if existing is not None and existing != row[key]:
                        result["reason_codes"].append("placement_conflict")
                        result["placements"].pop(rank_key)
                        conflicting_placements.add(rank_key)
                    else:
                        result["placements"][rank_key] = row[key]
    result["reason_codes"] = sorted(set(result["reason_codes"]))
    return result
