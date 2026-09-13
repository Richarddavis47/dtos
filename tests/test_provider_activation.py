"""Provider activation, normalization, fallback, and player-pipeline regressions."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

import httpx

from src.core.data_platform.defaults import build_data_platform
from src.core.data_platform.provider_activation import (
    DYNASTYPROCESS_IDS_URL,
    DYNASTYPROCESS_VALUES_URL,
    FANTASYCALC_URL,
    player_context,
    provider_catalog,
    refresh_public_market,
)


class FixtureResponse:
    def __init__(self, *, json_value=None, text: str = "", status: int = 200) -> None:
        self._json = json_value
        self.text = text
        self.status_code = status

    def json(self):
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("fixture failure", request=httpx.Request("GET", "https://fixture"), response=httpx.Response(self.status_code))


class FixtureClient:
    def __init__(self, responses: dict[str, FixtureResponse]) -> None:
        self.responses = responses

    async def get(self, url: str) -> FixtureResponse:
        return self.responses[url]


class ProviderActivationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_family_refresh_failure_preserves_other_provider_and_player_cache(self) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        cached = {'providers': {'FantasyCalc': {'9509': {'value': 10000}}},
                  'pick_quotes': {'DynastyProcess': []},
                  'provider_status': {name: {'status': 'healthy', 'last_refresh': stamp}
                                      for name in ('FantasyCalc', 'DynastyProcess')}}
        result = await refresh_public_market(FixtureClient({
            FANTASYCALC_URL: FixtureResponse(status=503)}), cached)
        self.assertEqual(result['providers'], cached['providers'])
        self.assertNotIn('FantasyCalc', result['pick_quotes'])
        self.assertEqual(result['provider_status']['FantasyCalc']['refresh_result'], 'cached_fallback')
        self.assertEqual(result['provider_status']['DynastyProcess'], cached['provider_status']['DynastyProcess'])
        self.assertEqual(result['pick_quotes']['DynastyProcess'], [])

    async def test_healthy_legacy_cache_materializes_missing_pick_family_once(self) -> None:
        cached = {'providers': {}, 'provider_status': {
            name: {'status': 'healthy', 'last_refresh': datetime.now(timezone.utc).isoformat()}
            for name in ('FantasyCalc', 'DynastyProcess')}}
        client = FixtureClient({
            FANTASYCALC_URL: FixtureResponse(json_value=[{'player': {
                'position': 'PICK', 'name': '2027 1st', 'sleeperId': 'FP_2027_1'}, 'value': 4000}]),
            DYNASTYPROCESS_VALUES_URL: FixtureResponse(text='player,pos,value_2qb,scrape_date\n2027 Early 1st,PICK,5000,2026-09-01\n'),
            DYNASTYPROCESS_IDS_URL: FixtureResponse(text='fantasypros_id,sleeper_id\n'),
        })
        result = await refresh_public_market(client, cached)
        self.assertEqual(len(result['pick_quotes']['FantasyCalc']), 1)
        self.assertEqual(result['pick_quotes']['FantasyCalc'][0]['pick_type'], 'generic_round')
        self.assertEqual(result['pick_quotes']['DynastyProcess'][0]['range'], 'EARLY')
        self.assertEqual(result['pick_quotes']['DynastyProcess'][0]['source_updated_at'], '2026-09-01T00:00:00+00:00')
        # A completed family, including a legitimately empty one, is not a cache miss.
        result['pick_quotes']['DynastyProcess'] = []
        replay = await refresh_public_market(FixtureClient({}), result)
        self.assertEqual(replay['pick_quotes'], result['pick_quotes'])
        for name in ('FantasyCalc', 'DynastyProcess'):
            self.assertEqual(replay['provider_status'][name], result['provider_status'][name])

    def test_player_and_market_api_use_same_current_normalized_price(self) -> None:
        platform = build_data_platform()
        data = {'players': self.players, 'market_data': {'providers': {
            'FantasyCalc': {'9509': {'value': 12000, 'confidence': 90}}}}}
        first = platform.player_report('9509', data)['consensus']
        self.assertEqual(first['value'], 1000)
        self.assertIsNone(first['agreement'])
        data['market_data']['providers']['FantasyCalc']['9509']['value'] = 0
        changed = platform.player_report('9509', data)['consensus']
        api = platform.aggregate('market', '9509', {'market_data': data['market_data']})
        self.assertEqual(changed['value'], 0)
        self.assertEqual(api.value, changed['value'])
        data['market_data']['providers']['FantasyCalc'] = {}
        missing = platform.player_report('9509', data)['consensus']
        self.assertIsNone(missing['value'])

    def setUp(self) -> None:
        self.players = {
            "9509": {"player_id": "9509", "full_name": "Bijan Robinson", "position": "RB", "team": "ATL", "age": 24, "status": "Active", "depth_chart_position": "RB", "depth_chart_order": 1, "metadata": None}
        }

    async def test_public_providers_normalize_to_canonical_sleeper_ids(self) -> None:
        fantasycalc = [{"player": {"id": 9833, "sleeperId": "9509"}, "value": 10213, "overallRank": 2, "positionRank": 1, "trend30Day": 178, "maybeTradeFrequency": .0076}]
        values = '"player","value_2qb","ecr_2qb","ecr_pos","fp_id"\n"Bijan Robinson",8262,10.2,1.1,"23133"\n'
        identities = "fantasypros_id,sleeper_id,name\n23133,9509,Bijan Robinson\n"
        result = await refresh_public_market(FixtureClient({FANTASYCALC_URL: FixtureResponse(json_value=fantasycalc), DYNASTYPROCESS_VALUES_URL: FixtureResponse(text=values), DYNASTYPROCESS_IDS_URL: FixtureResponse(text=identities)}))
        self.assertEqual(result["providers"]["FantasyCalc"]["9509"]["value"], 10213)
        self.assertEqual(result["providers"]["DynastyProcess"]["9509"]["value"], "8262")
        self.assertEqual(result["provider_status"]["FantasyCalc"]["records_retrieved"], 1)
        report = build_data_platform().player_report("9509", {"players": self.players, "market_data": result})
        # Incompatible DP cannot erase valid FC or contribute to its price/agreement.
        self.assertEqual(report["consensus"]["value"], 851)
        self.assertIsNone(report["consensus"]["agreement"])
        self.assertIsNone(result["providers"]["FantasyCalc"]["9509"]["source_updated_at"])
        self.assertEqual(result["providers"]["FantasyCalc"]["9509"]["retrieved_at"],
                         result["providers"]["FantasyCalc"]["9509"]["updated_at"])
        self.assertEqual(report["provider_details"]["FantasyCalc"]["fantasycalc_id"], 9833)

    async def test_empty_partial_failure_and_recovery_are_explicit(self) -> None:
        failures = {FANTASYCALC_URL: FixtureResponse(status=503), DYNASTYPROCESS_VALUES_URL: FixtureResponse(text="player,value_2qb,fp_id\n"), DYNASTYPROCESS_IDS_URL: FixtureResponse(text="fantasypros_id,sleeper_id\n")}
        prior = {"providers": {"FantasyCalc": {"9509": {"value": 10000}}}, "provider_status": {}}
        failed = await refresh_public_market(FixtureClient(failures), prior)
        self.assertEqual(failed["provider_status"]["FantasyCalc"]["refresh_result"], "cached_fallback")
        self.assertEqual(failed["providers"]["FantasyCalc"]["9509"]["value"], 10000)
        recovered = await refresh_public_market(FixtureClient({FANTASYCALC_URL: FixtureResponse(json_value=[]), DYNASTYPROCESS_VALUES_URL: failures[DYNASTYPROCESS_VALUES_URL], DYNASTYPROCESS_IDS_URL: failures[DYNASTYPROCESS_IDS_URL]}), {"providers": {}, "provider_status": {}})
        self.assertEqual(recovered["provider_status"]["FantasyCalc"]["status"], "healthy")
        self.assertEqual(recovered["provider_status"]["FantasyCalc"]["records_retrieved"], 0)

    def test_unsupported_providers_have_specific_reasons(self) -> None:
        catalog = provider_catalog()
        for name in ("Sleeper ADP", "Underdog ADP", "KeepTradeCut", "Projections"):
            self.assertFalse(catalog[name]["enabled"])
            self.assertTrue(catalog[name]["reason"])

    def test_sleeper_player_context_uses_real_metadata_and_explicit_gaps(self) -> None:
        data = {"players": self.players, "teams": [{"team_name": "Front Office One", "players": [{"id": "9509"}]}], "transactions": [{"adds": {"9509": 1}, "drops": None}], "trending_players": {"adds": [{"player_id": "9509", "count": 8}], "drops": []}}
        context = player_context("9509", data)
        self.assertEqual(context["metadata"]["depth_chart_role"], "RB")
        self.assertEqual(context["league"]["owned_by"], "Front Office One")
        self.assertEqual(context["league"]["trending_adds"], 8)
        self.assertIn("canonical_evidence", context["availability"]["production"])

    def test_projection_availability_uses_only_active_league_canonical_snapshot(self) -> None:
        data = {"players": self.players, "league": {"league_id": "A"},
                "projection_intelligence": {"league_id": "A", "season": 2026,
                    "week": 1, "projection_snapshot_id": "generation-a",
                    "players": {"9509": {"weekly_projected_points": 0.0,
                                          "source_freshness": "fresh"}}}}
        context = player_context("9509", data)
        self.assertIsNone(context["availability"]["projection"])
        self.assertEqual(context["projection_evidence"]["value"], 0.0)
        data["league"]["league_id"] = "B"
        other = player_context("9509", data)
        self.assertIsNone(other["projection_evidence"]["value"])
        self.assertIsNone(other["projection_evidence"]["snapshot_id"])
        self.assertIsNotNone(other["availability"]["projection"])


if __name__ == "__main__":
    unittest.main()
