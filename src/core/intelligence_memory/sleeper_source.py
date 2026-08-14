"""Bounded Sleeper historical source adapter used only by explicit cache work."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from config import REQUEST_TIMEOUT, SLEEPER_BASE
from services.sleeper import request_headers

from .chain import SeasonChain, discover_season_chain


class SleeperHistoricalSource:
    def __init__(self, *, base_url: str = SLEEPER_BASE, timeout: float = REQUEST_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _get(self, client: httpx.AsyncClient, path: str) -> Any:
        response = await client.get(f"{self.base_url}{path}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def discover(self, league_id: str) -> SeasonChain:
        async with httpx.AsyncClient(
            timeout=self.timeout, headers=request_headers(),
        ) as client:
            return await discover_season_chain(
                league_id, lambda item: self._get(client, f"/league/{item}"),
            )

    async def completed_season_facts(
        self, league_id: str, season: int,
    ) -> dict[str, Any] | None:
        """Fetch provider-owned facts without consulting Historical Memory."""
        async with httpx.AsyncClient(
            timeout=self.timeout, headers=request_headers(),
        ) as client:
            league = await self._get(client, f"/league/{league_id}")
            if not league:
                return None
            users, rosters, traded_picks, drafts = await asyncio.gather(
                self._get(client, f"/league/{league_id}/users"),
                self._get(client, f"/league/{league_id}/rosters"),
                self._get(client, f"/league/{league_id}/traded_picks"),
                self._get(client, f"/league/{league_id}/drafts"),
            )
            settings = league.get("settings") or {}
            playoff_week = int(settings.get("playoff_week_start") or 15)
            weeks = range(1, min(18, playoff_week + 4) + 1)
            matchup_rows = await asyncio.gather(*(
                self._get(client, f"/league/{league_id}/matchups/{week}")
                for week in weeks
            ))
            transaction_rows = await asyncio.gather(*(
                self._get(client, f"/league/{league_id}/transactions/{week}")
                for week in weeks
            ))
            draft_rows = []
            for draft in drafts or ():
                draft_id = str(draft.get("draft_id") or "")
                if draft_id:
                    draft_rows.extend(await self._get(client, f"/draft/{draft_id}/picks") or ())
            brackets = await asyncio.gather(
                self._get(client, f"/league/{league_id}/winners_bracket"),
                self._get(client, f"/league/{league_id}/losers_bracket"),
            )
        return {
            "league": league, "users": users, "rosters": rosters,
            "matchups": {str(index): rows for index, rows in enumerate(matchup_rows, 1)},
            "transactions": {str(index): rows for index, rows in enumerate(transaction_rows, 1)},
            "drafts": drafts, "draft_picks": draft_rows,
            "traded_picks": traded_picks, "winners_bracket": brackets[0],
            "losers_bracket": brackets[1], "season": int(season),
        }
