"""Bounded redirect regressions for optional Sleeper projection evidence."""
from __future__ import annotations

import unittest

import httpx

from src.core.projection_intelligence.sleeper_provider import (
    MAX_REDIRECTS, SleeperProjectionClient, SleeperProjectionTransportError,
)


PAYLOAD = [{
    "player_id": "10", "season": "2026", "week": 1,
    "player": {"position": "QB"}, "stats": {"pass_yd": 250, "pts_ppr": 18.5},
}]


class SleeperProjectionTransportTests(unittest.IsolatedAsyncioTestCase):
    async def _fetch(self, handler):
        provider = SleeperProjectionClient()
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=False,
        ) as client:
            result = await provider.fetch(client, season=2026, week=1)
        return provider, result

    async def test_301_same_sleeper_host_redirects_once_to_valid_payload(self) -> None:
        calls = []
        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(301, headers={"Location": "/canonical/projections"}, request=request)
            return httpx.Response(200, json=PAYLOAD, request=request)
        provider, (payload, size, details) = await self._fetch(handler)
        self.assertEqual(payload, PAYLOAD)
        self.assertGreater(size, 0)
        self.assertEqual(details["redirect_count"], 1)
        self.assertEqual(details["final_status"], 200)
        self.assertEqual(provider.last_transport, details)

    async def test_302_is_supported(self) -> None:
        calls = 0
        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(302, headers={"Location": "/final"}, request=request) if calls == 1 else httpx.Response(200, json=PAYLOAD, request=request)
        _, (_, _, details) = await self._fetch(handler)
        self.assertEqual(details["redirect_count"], 1)

    async def test_200_without_redirect(self) -> None:
        _, (payload, _, details) = await self._fetch(
            lambda request: httpx.Response(200, json=PAYLOAD, request=request)
        )
        self.assertEqual(payload, PAYLOAD)
        self.assertFalse(details["redirect_encountered"])

    async def test_redirect_loop_fails_closed(self) -> None:
        with self.assertRaisesRegex(SleeperProjectionTransportError, "loop"):
            await self._fetch(lambda request: httpx.Response(301, headers={"Location": str(request.url)}, request=request))

    async def test_excessive_redirects_fail_closed(self) -> None:
        calls = 0
        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(301, headers={"Location": f"/redirect/{calls}"}, request=request)
        with self.assertRaisesRegex(SleeperProjectionTransportError, "limit"):
            await self._fetch(handler)
        self.assertEqual(calls, MAX_REDIRECTS + 1)

    async def test_unexpected_host_is_rejected_before_second_request(self) -> None:
        calls = 0
        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(301, headers={"Location": "https://example.invalid/feed"}, request=request)
        with self.assertRaisesRegex(SleeperProjectionTransportError, "unexpected host"):
            await self._fetch(handler)
        self.assertEqual(calls, 1)

    async def test_https_downgrade_is_rejected(self) -> None:
        with self.assertRaisesRegex(SleeperProjectionTransportError, "insecure"):
            await self._fetch(lambda request: httpx.Response(301, headers={"Location": "http://api.sleeper.app/feed"}, request=request))

    async def test_missing_location_is_rejected(self) -> None:
        with self.assertRaisesRegex(SleeperProjectionTransportError, "Location"):
            await self._fetch(lambda request: httpx.Response(301, request=request))

    async def test_redirected_non_200_final_response_is_preserved_as_failure(self) -> None:
        calls = 0
        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(301, headers={"Location": "/final"}, request=request) if calls == 1 else httpx.Response(503, request=request)
        with self.assertRaises(httpx.HTTPStatusError):
            await self._fetch(handler)


if __name__ == "__main__":
    unittest.main()
