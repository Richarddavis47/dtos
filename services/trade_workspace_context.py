"""Small, non-persistent Trade workspace context and ownership boundary."""
from __future__ import annotations

import hashlib
import json

from src.platform.account_context import current_account


def workspace_binding(league_id: str, roster_id: int | None) -> str:
    """The existing opaque identity, independent of ownership/source generations."""
    account = current_account()
    identity = (account.account_id, account.session_id) if account else ("local", "local")
    return hashlib.sha256(json.dumps((identity, league_id, roster_id), separators=(",", ":")).encode()).hexdigest()


def workspace_context(data: dict, roster_id: int) -> dict:
    """Bind temporary state to account/session/league and canonical ownership."""
    league_id = str((data.get("league") or {}).get("league_id") or data.get("league_id") or "")
    ownership = []
    for team in data.get("teams") or ():
        owner = int(team.get("roster_id") or 0)
        players = sorted(str(p.get("id") or p.get("player_id")) for p in team.get("players") or ())
        picks = sorted((str(p.get("season")), str(p.get("round")), str(p.get("original_roster_id")), str(p.get("current_owner_id"))) for p in team.get("picks_owned") or ())
        ownership.append((owner, players, picks))
    generation = hashlib.sha256(json.dumps(sorted(ownership), separators=(",", ":")).encode()).hexdigest()
    binding = workspace_binding(league_id, roster_id)
    from services.strategy_session import strategy_scope
    account = current_account()
    own = bool(account and account.membership and account.membership.league_id == league_id
               and account.membership.roster_id == roster_id)
    return {"league_id": league_id, "roster_id": roster_id, "binding": binding, "ownership_generation": generation, "schema": 1,
            "strategy_scope": strategy_scope(),
            "franchise_goal": getattr(account, "franchise_goal", None) if own else None,
            "franchise_goal_revision": getattr(account, "franchise_goal_revision", 0) if own else 0}


def authorize_workspace(data: dict, payload: dict) -> None:
    """Do not reinterpret an old proposal under another session/league/franchise."""
    account = current_account()
    if account is None:
        return  # Existing non-authenticated fixture/CLI service contract.
    membership = account.membership
    supplied = payload.get("workspace_context")
    if membership is None or payload.get("active_roster_id") != membership.roster_id:
        raise ValueError("unauthorized_franchise")
    expected = workspace_context(data, membership.roster_id)
    if membership.league_id != expected["league_id"]:
        raise ValueError("unauthorized_league")
    if not isinstance(supplied, dict) or any(supplied.get(key) != expected[key] for key in ("binding", "league_id", "roster_id", "schema")):
        raise ValueError("workspace_context_changed")
    # Ownership itself is revalidated by the evaluator so it can name affected
    # assets. A refresh of unrelated ownership must not silently change a proposal.
