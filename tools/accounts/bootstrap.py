"""One-time, data-driven production account bootstrap.

Credentials are accepted only through the process environment. Recovery codes
for a newly created account are written to a caller-selected, exclusive file and
are never printed or logged.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from config import ACCOUNT_DATABASE_FILE
from src.core.accounts import AccountService, AccountStore


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required secure bootstrap setting {name} is absent.")
    return value


def _write_recovery_file(path: Path, codes: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("\n".join(codes) + "\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise


async def bootstrap() -> dict[str, object]:
    username = _required("DTOS_BOOTSTRAP_USERNAME")
    display_name = _required("DTOS_BOOTSTRAP_DISPLAY_NAME")
    password = _required("DTOS_BOOTSTRAP_PASSWORD")
    sleeper_username = _required("DTOS_BOOTSTRAP_SLEEPER_USERNAME")
    league_id = _required("DTOS_BOOTSTRAP_LEAGUE_ID")
    recovery_path = Path(_required("DTOS_BOOTSTRAP_RECOVERY_FILE"))
    store = AccountStore(ACCOUNT_DATABASE_FILE)
    service = AccountService(store)
    existing = store.account_by_username(username)
    created = existing is None
    if created:
        account_id, codes = service.create_account(username, display_name, password)
        _write_recovery_file(recovery_path, codes)
    else:
        account_id = service.authenticate(username, password)
        if account_id is None:
            raise RuntimeError("Bootstrap account exists but supplied credentials do not authenticate.")
    sleeper = await service.resolve_sleeper(sleeper_username)
    store.link_sleeper(account_id, sleeper_user_id=str(sleeper["user_id"]), username=sleeper.get("username"), display_name=sleeper.get("display_name"))
    leagues = {str(item.get("league_id")): item for item in await service.discover(str(sleeper["user_id"]))}
    league = leagues.get(league_id)
    if league is None:
        raise RuntimeError("Requested bootstrap league was not discovered for the resolved Sleeper identity.")
    roster_id, franchise_name, status = await service.resolve_membership(league, str(sleeper["user_id"]))
    if status != "active" or roster_id is None:
        raise RuntimeError("Bootstrap league did not resolve to exactly one associated franchise.")
    store.upsert_membership(account_id, league, str(sleeper["user_id"]), roster_id, franchise_name, status)
    if store.activate(account_id, league_id) is None:
        raise RuntimeError("Bootstrap membership could not be activated.")
    return {
        "status": "complete", "account_created": created,
        "sleeper_identity_state": "resolved_not_ownership_verified",
        "membership_created_or_refreshed": True, "active_league_set": True,
        "source_fallback_added": False,
    }


def main() -> None:
    print(json.dumps(asyncio.run(bootstrap()), sort_keys=True))


if __name__ == "__main__":
    main()
