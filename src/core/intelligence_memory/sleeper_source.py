"""Bounded Sleeper historical source adapter used only by explicit cache work."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

from config import REQUEST_TIMEOUT, SLEEPER_BASE
from services.sleeper import request_headers

from .chain import SeasonChain, discover_season_chain
from src.core.history_context.timestamps import canonical_draft_bounds


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

    async def _transaction_periods(self, client, league_id, season, periods):
        from src.core.history_context.transaction_periods import SCHEMA, record_period
        periods = tuple(periods)
        if len(periods) > 19 or len(set(periods)) != len(periods) or any(
                type(w) is not int or not 0 <= w <= 18 for w in periods):
            raise ValueError('Unsupported transaction recovery periods')
        gate = asyncio.Semaphore(4)

        async def get(week):
            async with gate:
                try:
                    rows = await self._get(client, f'/league/{league_id}/transactions/{week}')
                    state = None if isinstance(rows, list) and all(isinstance(r, dict) for r in rows) else 'unavailable' if rows is None else 'malformed'
                except Exception:
                    rows, state = None, 'failed'
                return week, rows, state, datetime.now(timezone.utc).isoformat()

        metadata = dict(schema=SCHEMA, league_id=str(league_id), season=str(season), periods={})
        buckets = {}
        for week, rows, state, stamp in await asyncio.gather(*(get(w) for w in periods)):
            buckets[str(week)] = rows if state is None else None
            metadata = record_period(metadata, week, rows, observed_at=stamp, state=state)
        return buckets, metadata

    async def recover_transaction_periods(self, league_id, season, periods):
        """Only requested gaps from an already verified source league/season.

        Called by admitted cache preparation, never a renderer. Four requests
        at once, at most19periods, no whole-season refetch or automatic loop.
        """
        async with httpx.AsyncClient(timeout=self.timeout, headers=request_headers()) as client:
            return await self._transaction_periods(client, league_id, season, periods)

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
            if str(league.get("league_id")) != str(league_id) or str(league.get("season")) != str(season):
                raise ValueError("Sleeper league/season identity mismatch.")
            users, rosters, traded_picks, drafts = await asyncio.gather(
                self._get(client, f"/league/{league_id}/users"),
                self._get(client, f"/league/{league_id}/rosters"),
                self._get(client, f"/league/{league_id}/traded_picks"),
                self._get(client, f"/league/{league_id}/drafts"),
            )
            settings = league.get("settings") or {}
            playoff_week = int(settings.get("playoff_week_start") or 15)
            weeks = range(1, min(18, playoff_week + 4) + 1)
            transaction_weeks = range(0, min(18, playoff_week + 4) + 1)
            matchup_rows = await asyncio.gather(*(
                self._get(client, f"/league/{league_id}/matchups/{week}")
                for week in weeks
            ))
            transaction_rows, acquisition = await self._transaction_periods(
                client, league_id, season, transaction_weeks)
            draft_rows = []
            for index, draft in enumerate(drafts or ()):
                detail = await self._get(client, f"/draft/{draft.get('draft_id')}") if draft.get("draft_id") else None
                if isinstance(detail, dict) and str(detail.get("draft_id")) == str(draft.get("draft_id")) and str(detail.get("league_id")) == str(league_id):
                    draft = {**draft, **detail}
                    drafts[index] = draft
                draft_id = str(draft.get("draft_id") or "")
                if draft_id:
                    for pick in await self._get(client, f"/draft/{draft_id}/picks") or ():
                        if pick.get("draft_id") and str(pick["draft_id"]) != draft_id:
                            raise ValueError("Draft selection source identity mismatch.")
                        draft_rows.append({**pick, "draft_id": draft_id, **canonical_draft_bounds(draft)})
            brackets = await asyncio.gather(
                self._get(client, f"/league/{league_id}/winners_bracket"),
                self._get(client, f"/league/{league_id}/losers_bracket"),
            )
        return {
            "league": league, "users": users, "rosters": rosters,
            "matchups": {str(index): rows for index, rows in enumerate(matchup_rows, 1)},
            "transactions": transaction_rows, "transaction_acquisition": acquisition,
            "drafts": drafts, "draft_picks": draft_rows,
            "traded_picks": traded_picks, "winners_bracket": brackets[0],
            "losers_bracket": brackets[1], "season": int(season),
        }
