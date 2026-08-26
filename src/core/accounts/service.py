"""Account authentication and truthful Sleeper identity resolution."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
from pwdlib import PasswordHash

from config import HISTORICAL_START_SEASON, SESSION_TTL_HOURS, SLEEPER_BASE
from .models import AccountContext
from .store import AccountStore, _token_digest


class AccountService:
    def __init__(self, store: AccountStore, *, client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient) -> None:
        self.store = store
        self.passwords = PasswordHash.recommended()
        self.client_factory = client_factory

    def create_account(self, username: str, display_name: str, password: str) -> tuple[str, list[str]]:
        username = username.strip()
        if not 3 <= len(username) <= 64 or not all(ch.isalnum() or ch in "._-" for ch in username):
            raise ValueError("Choose a username with 3-64 letters, numbers, dots, dashes, or underscores.")
        if len(password) < 12:
            raise ValueError("Use at least 12 characters for your DTOS password.")
        codes = [secrets.token_urlsafe(12) for _ in range(8)]
        account_id = str(uuid.uuid4())
        self.store.create_account(account_id, username, display_name or username, self.passwords.hash(password), [_token_digest(code) for code in codes])
        return account_id, codes

    def authenticate(self, username: str, password: str) -> str | None:
        row = self.store.account_by_username(username)
        if row is None or not self.passwords.verify(password, row["password_hash"]):
            return None
        return str(row["account_id"])

    def recover(self, username: str, recovery_code: str, new_password: str) -> tuple[str, list[str]] | None:
        if len(new_password) < 12:
            raise ValueError("Use at least 12 characters for your DTOS password.")
        if not username.strip() or not recovery_code.strip():
            return None
        codes = [secrets.token_urlsafe(12) for _ in range(8)]
        account_id = self.store.recover_account(
            username,
            _token_digest(recovery_code.strip()),
            self.passwords.hash(new_password),
            [_token_digest(code) for code in codes],
        )
        return (account_id, codes) if account_id else None

    def new_session(self, account_id: str) -> tuple[str, str]:
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        self.store.create_session(account_id=account_id, token=token, session_id=str(uuid.uuid4()), csrf_token=csrf, ttl_hours=SESSION_TTL_HOURS)
        return token, csrf

    async def resolve_sleeper(self, username: str) -> dict[str, Any]:
        async with self.client_factory(timeout=15) as client:
            response = await client.get(f"{SLEEPER_BASE}/user/{username.strip()}")
            if response.status_code == 404:
                raise ValueError("We could not find that Sleeper username.")
            response.raise_for_status()
            payload = response.json()
        if not payload or not payload.get("user_id"):
            raise ValueError("We could not find that Sleeper username.")
        return payload

    async def discover(self, sleeper_user_id: str, *, seasons: tuple[int, ...] | None = None) -> list[dict[str, Any]]:
        year = datetime.now(timezone.utc).year
        seasons = seasons or tuple(range(year, HISTORICAL_START_SEASON - 1, -1))
        async with self.client_factory(timeout=20) as client:
            responses = await __import__("asyncio").gather(*[
                client.get(f"{SLEEPER_BASE}/user/{sleeper_user_id}/leagues/nfl/{season}") for season in seasons
            ])
        leagues: dict[str, dict[str, Any]] = {}
        for response in responses:
            response.raise_for_status()
            for league in response.json() or ():
                if league.get("league_id"):
                    leagues[str(league["league_id"])] = league
        return sorted(leagues.values(), key=lambda row: (-int(row.get("season") or 0), str(row.get("name") or "")))

    async def league(self, league_id: str) -> dict[str, Any]:
        if not league_id.strip() or not league_id.isdigit():
            raise ValueError("Enter a valid Sleeper league ID.")
        async with self.client_factory(timeout=15) as client:
            response = await client.get(f"{SLEEPER_BASE}/league/{league_id}")
            if response.status_code == 404:
                raise ValueError("We could not find that Sleeper league.")
            response.raise_for_status()
            payload = response.json()
        if not payload or not payload.get("league_id"):
            raise ValueError("We could not find that Sleeper league.")
        return payload

    async def resolve_membership(self, league: dict[str, Any], sleeper_user_id: str) -> tuple[int | None, str | None, str]:
        league_id = str(league.get("league_id") or "")
        async with self.client_factory(timeout=20) as client:
            rosters_response, users_response = await __import__("asyncio").gather(
                client.get(f"{SLEEPER_BASE}/league/{league_id}/rosters"),
                client.get(f"{SLEEPER_BASE}/league/{league_id}/users"),
            )
        rosters_response.raise_for_status()
        users_response.raise_for_status()
        matches = [row for row in rosters_response.json() or () if sleeper_user_id in {str(row.get("owner_id") or ""), *map(str, (row.get("co_owners") or ())) }]
        if len(matches) != 1:
            return None, None, "ambiguous" if len(matches) > 1 else "no_franchise"
        roster = matches[0]
        users = {str(row.get("user_id")): row for row in users_response.json() or ()}
        owner = users.get(str(roster.get("owner_id") or ""), {})
        metadata = roster.get("metadata") or {}
        name = metadata.get("team_name") or owner.get("display_name") or owner.get("username")
        return int(roster.get("roster_id")), str(name or "Franchise"), "active"

    @staticmethod
    def public_context(context: AccountContext) -> dict[str, Any]:
        membership = context.membership
        return {
            "status": "authenticated", "account": {"username": context.username, "display_name": context.display_name},
            "sleeper_identity": ({"username": context.sleeper_username, "link_state": context.sleeper_link_state, "ownership_verified": False} if context.sleeper_user_id else None),
            "active_league": ({"league_id": membership.league_id, "league_name": membership.league_name, "franchise_name": membership.franchise_name, "roster_id": membership.roster_id} if membership else None),
        }
