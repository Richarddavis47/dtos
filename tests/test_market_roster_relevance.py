"""Retained canonical quotes + real prepared roster diagnostics + authorized routes."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from routes.market import create_market_router
from src.core.asset_market import AssetMarketCache
from src.core.historical_memory.store import HistoricalStore
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.valuation.normalization import prepare_market_normalization
from src.core.valuation.universe import ValuationUniverse
from src.core.valuation_intelligence.engine import _score_asset
from src.ui.render_cache import GenerationRenderCache
from tests import test_team_trade_need_browser as need_fixture
from tests.test_market_observation_producer_identity import checkpoint


class MarketNeedFixture:
    def __init__(
        self,
        case,
        *,
        superflex=False,
        depth=False,
        history=True,
        old_raw=1800,
        current_raw=3600,
    ):
        import dtos_app

        helper_case = need_fixture.TeamTradeNeedBrowserTests()
        case.addCleanup(helper_case.doCleanups)
        self.need_case = helper_case
        self.helper, self.f = helper_case.fixture(superflex=superflex, depth=depth)
        self.data = self.f.editor.data
        self.player_id = "2-RB-0"
        self.asset_id = "player:" + self.player_id
        self.root = Path(self.f.capital.tmp.name)
        self.memory = IntelligenceCheckpointStore(self.root / "market-need.sqlite3")
        self.history = HistoricalStore(self.root / "market-history.sqlite3")
        self.cache = AssetMarketCache()
        case.addCleanup(self.cache.clear)
        self.data["normalized_players"] = self.data["players"]
        self.data["market_data"]["providers"]["FantasyCalc"][self.player_id] = {
            "value": current_raw,
            "confidence": 90,
        }
        self.stamp = datetime.now(timezone.utc)
        for quote in self.data["market_data"]["providers"]["FantasyCalc"].values():
            quote.update(
                format="dynasty_2qb",
                format_details={"num_teams": 12, "num_qbs": 2, "ppr": 1},
                source_updated_at=None,
                retrieved_at=self.stamp.isoformat(),
            )
        prepare_market_normalization(self.data["market_data"])
        universe = ValuationUniverse(self.data, {"data": self.data})
        self.data["valuation_intelligence"] = {
            "assets": {
                key: _score_asset(row, [], {}, None)
                for key, row in universe.by_id.items()
            }
        }
        self.state = {"data": self.data, "last_sync": self.stamp.isoformat()}
        if history:
            self.add_point(old_raw)
        self.market = self.cache.get(self.data, self.state, self.history, "league-1")
        # The prepared Trade fixture and real Market quote share canonical prices.
        row = self.f.editor.market.row(
            self.asset_id,
            self.data["valuation_intelligence"]["assets"][self.asset_id][
                "valuation_layers"
            ]["market_value"]["value"],
            "RB",
            self.player_id,
        )
        self.f.editor.market.rows.append(row)
        self.body_cache = GenerationRenderCache("market-need-test-body")
        self.page_cache = GenerationRenderCache("market-need-test-page")
        case.enterContext(patch("routes.market.market_render_cache", self.page_cache))
        case.enterContext(
            patch("routes.market.market_body_render_cache", self.body_cache)
        )
        case.enterContext(patch("routes.market.historical_store", self.history))

        def market_route(route):
            path = getattr(route, "path", "")
            if path == "/market" or path.startswith("/api/market/"):
                return True
            original = getattr(route, "original_router", None)
            return bool(
                original and any(market_route(child) for child in original.routes)
            )

        self.f.editor.app.router.routes[:] = [
            r for r in self.f.editor.app.router.routes if not market_route(r)
        ]
        with patch("routes.market.intelligence_checkpoint_store", self.memory):
            self.f.editor.app.include_router(
                create_market_router(
                    require_data=lambda: self.data,
                    state=self.state,
                    league_id="league-1",
                    page=dtos_app.page,
                    context_resolver=lambda: SimpleNamespace(
                        state=self.state,
                        league_id=str(self.data["league"]["league_id"]),
                        market=self.cache,
                        projection=self.f.capital.reader,
                    ),
                )
            )
        case.enterContext(
            patch(
                "services.sleeper.sync_sleeper",
                side_effect=AssertionError("No source synchronization on a read"),
            )
        )
        case.enterContext(
            patch.object(
                CheckpointPipeline,
                "ingest_runtime",
                side_effect=AssertionError("No acquisition on a read"),
            )
        )
        self.client = self.f.editor.client

    def add_point(self, raw, *, incompatible=False, days=2, name="need-old"):
        data = deepcopy(self.data)
        stamp = (self.stamp - timedelta(days=days)).isoformat()
        data["market_data"]["providers"]["FantasyCalc"][self.player_id].update(
            value=raw, retrieved_at=stamp
        )
        prepare_market_normalization(data["market_data"])
        universe = ValuationUniverse(data, {"data": data})
        data["valuation_intelligence"] = {
            "assets": {
                self.asset_id: _score_asset(universe.by_id[self.asset_id], [], {}, None)
            }
        }
        observations = CheckpointPipeline._market_observations(data, self.asset_id)
        observations = tuple(
            replace(
                o,
                observed_at=stamp,
                metadata={
                    **o.metadata,
                    **(
                        {
                            "comparison_semantics": {
                                **o.metadata["comparison_semantics"],
                                "format_key": "incompatible",
                            }
                        }
                        if incompatible
                        else {}
                    ),
                },
            )
            for o in observations
        )
        assert observations
        self.old_value = observations[0].normalized_value
        point = replace(checkpoint(name, self.old_value, stamp), asset_id=self.asset_id)
        self.memory.put_sparse(
            point,
            market_context_id="source-compatible-fixture",
            provider_evidence=observations,
        )

    def panel(self, **params):
        response = self.client.get(
            "/market", params={"q": self.player_id, "front_office": 1, **params}
        )
        assert response.status_code == 200, response.text[:1000]
        html = response.text
        start = html.index('id="market-roster-movement"')
        return html[start:], response

    def link(self):
        html, _ = self.panel()
        match = re.search(r'href="([^"]+)"[^>]*>Explore in Trade For', html)
        assert match, html[:3000]
        return unescape(match[1])


class MarketRosterRelevanceTests(unittest.TestCase):
    def test_actual_prepared_movement_and_starter_need_reach_scoped_handoff(self):
        f = MarketNeedFixture(self)
        html, _ = f.panel()
        self.assertIn("supported RB addition", html)
        self.assertIn("starter need", html)
        self.assertIn(
            "match does not establish this player’s legal-lineup improvement", html
        )
        self.assertIn("FantasyCalc", html)
        self.assertIn("days since", html)
        current = f.data["valuation_intelligence"]["assets"][f.asset_id][
            "valuation_layers"
        ]["market_value"]["value"]
        self.assertIn(f"{current - f.old_value:+,.2f} Market points", html)
        target = f.client.get(f.link())
        self.assertEqual(target.status_code, 200)
        self.assertIn("Opened from Market", target.text)
        self.assertIn('data-preload-asset="2-RB-0"', target.text)
        self.assertIn("Market movement is not revalidated here", target.text)
        for cache in (f.body_cache, f.page_cache):
            self.assertTrue(cache._entries)
            self.assertFalse(
                any(
                    b"Explore in Trade For" in body or b"team_need=" in body
                    for body in cache._entries.values()
                )
            )

    def test_market_only_runtime_without_projection_owner_keeps_neutral_movement(self):
        from src.platform.league_context import _CURRENT_CONTEXT

        f = MarketNeedFixture(self)
        marker = _CURRENT_CONTEXT.set(
            SimpleNamespace(league_id="league-1", state=f.state, data=f.data)
        )
        try:
            response = f.f.editor.client.get("/market?q=2-RB-0")
            self.assertEqual(response.status_code, 200)
            self.assertIn(
                "Compatible prepared roster projections are unavailable", response.text
            )
            self.assertIn("Observed change: +150.00 Market points", response.text)
            self.assertNotIn("Explore in Trade For", response.text)
        finally:
            _CURRENT_CONTEXT.reset(marker)

    def test_warm_market_reuses_directory_and_trend_batch(self):
        f = MarketNeedFixture(self)
        with patch.object(f.market, "search", wraps=f.market.search) as search:
            first, _ = f.panel()
            second, _ = f.panel()
        self.assertEqual(search.call_count, 1)
        self.assertIn("Observed change: +150.00 Market points", first)
        self.assertIn("Observed change: +150.00 Market points", second)

    def test_old_format_movement_cannot_become_a_current_personal_lead(self):
        f = MarketNeedFixture(self)
        f.add_point(2400, days=1, name="need-second")
        for quote in f.data["market_data"]["providers"]["FantasyCalc"].values():
            quote.update(
                format="dynasty_1qb",
                format_details={"num_teams": 12, "num_qbs": 1, "ppr": 1},
            )
        prepare_market_normalization(f.data["market_data"])
        universe = ValuationUniverse(f.data, f.state)
        f.data["valuation_intelligence"] = {
            "assets": {
                key: _score_asset(row, [], {}, None)
                for key, row in universe.by_id.items()
            }
        }
        f.cache.clear()
        f.market = f.cache.get(f.data, f.state, f.history, "league-1")
        html, _ = f.panel()
        self.assertNotIn("Explore in Trade For", html)
        self.assertNotIn("Position matches your supported", html)
        # Keep only comparisons admitted by the existing canonical reader.
        # A format boundary may leave neutral history or withhold the change.
        self.assertTrue("Neutral observation" in html or "Movement is unknown" in html)

    def test_zero_movement_is_supported_not_missing(self):
        f = MarketNeedFixture(self, old_raw=3600)
        html, _ = f.panel()
        self.assertIn("+0.00 Market points", html)
        self.assertIn("Explore in Trade For", html)

    def test_missing_history_is_unknown_not_zero_or_no_opportunities(self):
        f = MarketNeedFixture(self, history=False)
        html, _ = f.panel()
        self.assertIn("Movement is unknown, not zero", html)
        self.assertNotIn("Explore in Trade For", html)
        self.assertNotIn("Observed change: +0.00", html)

    def test_incompatible_history_is_excluded_by_existing_reader(self):
        f = MarketNeedFixture(self, history=False)
        f.add_point(1800, incompatible=True)
        html, _ = f.panel()
        self.assertNotIn("Explore in Trade For", html)
        self.assertIn("Compatible dated prices are insufficient", html)

    def test_changed_availability_keeps_neutral_movement_and_expires_link(self):
        f = MarketNeedFixture(self)
        link = f.link()
        f.data["teams"][0]["players"][0]["status"] = "Out"
        f.data["players"][f.data["teams"][0]["players"][0]["id"]]["status"] = "Out"
        html, _ = f.panel()
        self.assertIn("Observed change:", html)
        self.assertIn("matching prepared roster comparison is unavailable", html)
        self.assertNotIn("Explore in Trade For", html)
        response = f.client.get(link)
        self.assertIn("Market handoff needs review", response.text)
        self.assertIn('data-preload-asset=""', response.text)

    def test_aged_projection_keeps_neutral_information(self):
        f = MarketNeedFixture(self)
        f.need_case.publish(f.f, age=75)
        html, _ = f.panel()
        self.assertIn("Observed change:", html)
        self.assertIn("provisional", html)
        self.assertNotIn("Explore in Trade For", html)

    def test_changed_quote_generation_does_not_apply_stale_target(self):
        f = MarketNeedFixture(self)
        link = f.link()
        f.data["valuation_intelligence"]["assets"][f.asset_id]["valuation_layers"][
            "market_value"
        ]["generation"] = "different-quote"
        response = f.client.get(link)
        self.assertEqual(response.status_code, 200)
        self.assertIn("No new target was applied", response.text)
        self.assertIn('data-preload-asset=""', response.text)

    def test_ownership_change_does_not_silently_retarget(self):
        f = MarketNeedFixture(self)
        link = f.link()
        player = next(
            p for p in f.data["teams"][1]["players"] if p["id"] == f.player_id
        )
        f.data["teams"][1]["players"].remove(player)
        f.data["teams"][0]["players"].append(player)
        response = f.client.get(link)
        self.assertIn("Market handoff needs review", response.text)
        self.assertIn('data-preload-asset=""', response.text)

    def test_foreign_franchise_query_is_normalized_to_authorized_context(self):
        f = MarketNeedFixture(self)
        response = f.client.get("/market", params={"q": f.player_id, "front_office": 2})
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="front_office" value="1"', response.text)
        self.assertIn("supported RB addition", response.text)
        self.assertNotIn("front_office=2&amp;asset_id=", response.text)

    def test_account_change_does_not_reuse_cached_personal_token(self):
        f = MarketNeedFixture(self)
        original = f.link()
        f.f.editor.use_account("account-b")
        other = f.link()
        self.assertNotEqual(original, other)
        response = f.client.get(original)
        self.assertIn("No new target was applied", response.text)
        self.assertNotIn("Opened from Market", response.text)

    def test_signed_out_request_cannot_replay_scoped_handoff(self):
        f = MarketNeedFixture(self)
        href = f.link()
        f.client.cookies.clear()
        response = f.client.get(href, follow_redirects=False)
        self.assertIn(response.status_code, (302, 303, 307, 401))
        self.assertNotIn("Opened from Market", response.text)

    def test_failed_refresh_keeps_prices_but_withholds_current_relevance(self):
        f = MarketNeedFixture(self)
        href = f.link()
        f.f.capital.reader.begin_external_refresh()
        f.f.capital.reader.fail_external_refresh(
            RuntimeError("controlled fixture refresh failure")
        )
        html, _ = f.panel()
        self.assertIn("Observed change:", html)
        self.assertIn("latest refresh did not complete", html)
        self.assertNotIn("Explore in Trade For", html)
        self.assertIn("No new target was applied", f.client.get(href).text)

    def test_superflex_depth_need_is_not_a_starter_upgrade(self):
        f = MarketNeedFixture(self, superflex=True, depth=True)
        html, _ = f.panel()
        self.assertIn("RB depth need", html)
        self.assertIn("not a starter-upgrade verdict", html)
        self.assertIn(
            "match does not establish this player’s legal-lineup improvement", html
        )

    def test_decline_is_observation_not_buy_low_verdict(self):
        f = MarketNeedFixture(self, old_raw=3600, current_raw=1800)
        html, _ = f.panel()
        self.assertIn("-150.00 Market points", html)
        self.assertIn("A decline does not prove buy low", html)

    def test_explicit_zero_market_price_is_not_unavailable(self):
        f = MarketNeedFixture(self, old_raw=0, current_raw=0)
        html, _ = f.panel()
        self.assertIn("Current neutral Market: 0.00 Market points", html)
        self.assertIn("Observed change: +0.00 Market points", html)

    def test_misjoined_asset_identity_is_not_a_movement_lead(self):
        from services.market_roster_relevance import movement_view
        from src.core.market_trends import MarketTrendService
        from src.core.market_trends.current import current_comparison
        from src.core.player_ownership import PlayerOwnershipIndex

        f = MarketNeedFixture(self)
        value = f.data["valuation_intelligence"]["assets"][f.asset_id][
            "valuation_layers"
        ]["market_value"]["value"]
        trend = MarketTrendService(f.memory).trend_for_asset(
            f.asset_id,
            value,
            league_id="league-1",
            current_semantics=current_comparison(f.data, f.asset_id, value),
        )
        self.assertEqual(trend["magnitude"], 150)
        view = movement_view(
            f.data,
            [dict(asset_id="player:wrong", position="RB", market_trend=trend)],
            1,
            PlayerOwnershipIndex(f.data),
        )
        self.assertFalse(view["cards"])
