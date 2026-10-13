"""Source-backed postseason facts; never infer seeds from final placements."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def roster_identity(value: Any) -> int | None:
    """Admit positive Sleeper roster IDs; nested values are not outcomes."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        text = str(value)
        if not text.isascii() or not text.isdigit():
            return None
        identity = int(text)
    except ValueError:
        return None
    return identity if identity > 0 else None


def admitted_bracket_row(row: Mapping[str, Any], roster_ids: set[int] | None = None) -> dict[str, Any]:
    """Qualify optional outcomes without changing retained raw source evidence."""
    admitted = dict(row)
    reasons = [reason for reason in row.get('outcome_reason_codes') or [] if isinstance(reason, str)] if isinstance(row.get('outcome_reason_codes', []), list) else []
    outcomes = {}
    for key in ('w', 'l'):
        value = row.get(key)
        identity = roster_identity(value)
        if value is not None and (identity is None or (roster_ids is not None and identity not in roster_ids)):
            reasons.append('bracket_outcome_identity_malformed_or_unsupported')
        outcomes[key] = identity
    # Preserve both identities until multiplicity is checked. A set would erase
    # the contradictory claim that one roster played against itself.
    participant_ids = []
    for key in ('t1', 't2'):
        value = row.get(key)
        dependency = (isinstance(value, Mapping) and len(value) == 1
                      and next(iter(value)) in {'w', 'l'}
                      and roster_identity(next(iter(value.values()))) is not None)
        if dependency:
            continue
        identity = roster_identity(value)
        if value is not None and (identity is None or (roster_ids is not None and identity not in roster_ids)):
            reasons.append('bracket_participant_identity_malformed_or_unsupported')
            identity = None
        admitted[key] = identity
        if identity is not None:
            participant_ids.append(identity)
    if len(participant_ids) != len(set(participant_ids)):
        reasons.append('bracket_participant_identity_conflict')
    participants = set(participant_ids)
    placement = roster_identity(row.get('p'))
    if row.get('p') is not None and (placement is None or (roster_ids and placement > len(roster_ids))):
        reasons.append('placement_identity_malformed_or_unsupported')
        placement = None
    if 'p' in row:
        admitted['p'] = placement
    known_outcomes = set(outcomes.values()) - {None}
    if ((outcomes['w'] is not None and outcomes['w'] == outcomes['l'])
            or (len(participants) == 2 and not known_outcomes <= participants)
            or (len(known_outcomes) == 2 and not participants <= known_outcomes)):
        reasons.append('bracket_outcome_identity_conflict')
    if reasons:
        admitted['retained_outcome_evidence'] = row.get('retained_outcome_evidence') or {key: row.get(key) for key in ('w', 'l')}
        admitted['retained_participant_evidence'] = row.get('retained_participant_evidence') or {key: row.get(key) for key in ('t1', 't2')}
        outcomes = {'w': None, 'l': None}
    admitted.update(outcomes)
    admitted['outcome_reason_codes'] = sorted(set(reasons))
    return admitted


def admitted_playoff_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the same outcome contract on retained checkpoint reads, without repair."""
    result = dict(payload)
    participants = payload.get('championship_roster_ids')
    participant_reasons = []
    if participants is not None and (not isinstance(participants, list) or len(participants) > 2):
        participant_reasons.append('bracket_participant_identity_malformed_or_unsupported')
        participants = []
    pair = admitted_bracket_row({'w': payload.get('champion_roster_id'), 'l': payload.get('runner_up_roster_id'),
                                **{key: value for key, value in zip(('t1', 't2'), participants or [])},
                                'outcome_reason_codes': participant_reasons})
    reasons = [r for r in payload.get('reason_codes') or [] if isinstance(r, str)] if isinstance(payload.get('reason_codes', []), list) else []
    reasons.extend(pair['outcome_reason_codes'])
    result.update(champion_roster_id=pair['w'], runner_up_roster_id=pair['l'])
    placements = payload.get('placements')
    admitted = {}
    conflicting_ranks = set()
    for rank, value in (placements if isinstance(placements, Mapping) else {}).items():
        identity = roster_identity(value)
        if identity is None or roster_identity(rank) is None or (pair['outcome_reason_codes'] and str(rank) in {'1', '2'}):
            reasons.append('placement_identity_unavailable_or_conflicted')
        else:
            normalized_rank = str(roster_identity(rank))
            if normalized_rank in admitted and admitted[normalized_rank] != identity:
                conflicting_ranks.add(normalized_rank)
            admitted[normalized_rank] = identity
    duplicated = {owner for owner in admitted.values() if list(admitted.values()).count(owner) > 1}
    if duplicated:
        conflicting_ranks.update(rank for rank, owner in admitted.items() if owner in duplicated)
        admitted = {rank: owner for rank, owner in admitted.items() if owner not in duplicated}
        reasons.append('placement_identity_conflict')
    for rank, outcome in (('1', pair['w']), ('2', pair['l'])):
        if outcome is not None and rank in admitted and admitted[rank] != outcome:
            conflicting_ranks.add(rank)
    if conflicting_ranks:
        reasons.append('placement_identity_conflict')
        admitted = {rank: owner for rank, owner in admitted.items() if rank not in conflicting_ranks}
    if conflicting_ranks & {'1', '2'} or 'championship_placement_conflict' in reasons:
        result.update(champion_roster_id=None, runner_up_roster_id=None)
        admitted = {rank: owner for rank, owner in admitted.items() if rank not in {'1', '2'}}
        reasons.append('championship_placement_conflict')
    if placements is not None and not isinstance(placements, Mapping):
        reasons.append('placement_identity_malformed')
    result.update(placements=admitted, reason_codes=sorted(set(reasons)))
    return result


def playoff_facts(bracket: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Reconcile only the winners bracket, including teams with first-round byes.

    Sleeper's ``p`` is a placement match, not a seed. Semifinals are the winner
    dependencies of the championship, not every game in the preceding round.
    Missing dependencies remain explicitly incomplete.
    """
    bracket = [admitted_bracket_row(row) for row in bracket if isinstance(row, Mapping)]
    outcome_reasons = sorted({reason for row in bracket for reason in row['outcome_reason_codes']})
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
        "placements": {}, "reason_codes": outcome_reasons,
    }
    if conflicting_matches:
        result["reason_codes"] = sorted(set(outcome_reasons + ["bracket_match_identity_conflict"]))
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
                elif len(dependency) == 1:
                    outcome, match_id = next(iter(dependency.items()))
                    parent = matches.get(str(match_id))
                    value = parent.get(outcome) if parent and outcome in {'w', 'l'} else None
                    if value is not None and roster_identity(value) != roster_identity(row[side]):
                        normalized['outcome_reason_codes'] = list(row['outcome_reason_codes']) + ['bracket_participant_identity_conflict']
        resolved.append(admitted_bracket_row(normalized))
    bracket = resolved
    result['reason_codes'] = sorted(set(result['reason_codes'] + [reason for row in bracket for reason in row['outcome_reason_codes']]))
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
        result["reason_codes"] = sorted(set(outcome_reasons + ["championship_missing" if not finals else "championship_conflict"]))
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
    if conflicting_placements & {'1', '2'}:
        result['reason_codes'].append('championship_placement_conflict')
    return admitted_playoff_result(result)
