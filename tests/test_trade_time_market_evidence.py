"""Retained price -> shared selection -> completed trade disclosure."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import patch

from src.core.intelligence_memory.models import CheckpointTrigger, EvidenceCompleteness, ProvenanceType
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from tests import test_historical_tracker_phase2 as fixtures
from tests.test_market_observation_producer_identity import prepared


class TradeTimeMarketEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.TrackerPhase2Tests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        from src.core.historical_memory.read_model import HistoricalReadModelCache
        self.f.stack.enter_context(patch(
            "src.core.historical_memory.read_model.historical_read_model_cache", HistoricalReadModelCache()))
        self.boundary = self.f.graph().trade_dossier(fixtures.ROOT)['occurred_at']
        self.when = datetime.fromisoformat(self.boundary.replace('Z', '+00:00'))
        self.serial = 0

    def capture(self, asset='player:12506', *, seconds=-3600, value=400, metadata=None,
                kind='player', scope=fixtures.DAY):
        data, _ = prepared()
        stamp = (self.when + timedelta(seconds=seconds)).isoformat()
        evidence = []
        for r in CheckpointPipeline._market_observations(data, 'player:1'):
            extra = deepcopy(r.metadata)
            extra.update(metadata or {})
            evidence.append(replace(r, observed_at=stamp, raw_value=value, normalized_value=value, metadata=extra))
        self.serial += 1
        self.f.fixture.service.capture(trigger=CheckpointTrigger.TRADE_EXECUTION, asset_id=asset,
            asset_type=kind, timestamp=stamp, season=self.when.year, provenance=ProvenanceType.LIVE_CAPTURED,
            league_id=scope, event_id='disposable-distinct-'+str(self.serial), market_value=value,
            confidence=90, completeness=EvidenceCompleteness.COMPLETE, observations=tuple(evidence))
        return stamp.replace("+00:00", "Z")

    def row(self, asset='DTOS-P-12506'):
        d = self.f.graph().trade_dossier(fixtures.ROOT)
        return next(r for r in d['trade_time_intelligence']['assets'] if r['asset_id'] == asset)

    def test_newer_incompatible_does_not_hide_older_compatible_quote(self):
        older = self.capture()
        data, _ = prepared()
        semantics = deepcopy(CheckpointPipeline._market_observations(data, 'player:1')[0].metadata['comparison_semantics'])
        semantics['value_scale'] = 'native_units'
        self.capture(seconds=-60, value=800, metadata={'comparison_semantics': semantics})
        row = self.row()
        self.assertEqual(row['value'], 400)
        self.assertEqual((row['observed_at'], row['quote_age_seconds']), (older, 3600))

    def test_newer_foreign_scope_does_not_hide_compatible_quote(self):
        self.capture()
        self.capture(seconds=-60, value=800, metadata={'league_id': fixtures.ARK})
        self.assertEqual(self.row()['value'], 400)

    def test_foreign_only_raw_evidence_is_not_exposed(self):
        self.capture(metadata={'league_id': fixtures.ARK, 'private_marker': 'foreign-private-quote'})
        row = self.row()
        self.assertIsNone(row['value'])
        self.assertIsNone(row['retained_observation'])
        response = self.f.client.get('/trades/history/'+fixtures.ROOT)
        self.assertNotIn('foreign-private-quote', response.text)
        self.assertIn('different league context', response.text)

    def test_foreign_future_quote_is_not_exposed_as_raw_evidence(self):
        self.capture(seconds=1, metadata={'league_id':fixtures.ARK,'private_marker':'future-private-quote'})
        row = self.row()
        self.assertIsNone(row['value'])
        self.assertIsNone(row['retained_observation'])
        response = self.f.client.get('/trades/history/'+fixtures.ROOT)
        self.assertNotIn('future-private-quote',response.text)

    def test_unavailable_retained_metadata_withholds_without_error(self):
        self.capture()
        with self.f.fixture.memory._connect() as c:
            for row in c.execute('SELECT observation_id,provider_evidence_json FROM global_market_observations').fetchall():
                data=json.loads(row['provider_evidence_json'])
                for e in data:
                    e['metadata']='unsupported legacy metadata'
                c.execute('UPDATE global_market_observations SET provider_evidence_json=? WHERE observation_id=?',
                    (json.dumps(data),row['observation_id']))
        response=self.f.client.get('/trades/history/'+fixtures.ROOT)
        self.assertEqual(response.status_code,200)
        self.assertIn('unavailable source metadata',response.text)

    def test_known_asset_identity_mismatch_cannot_enter(self):
        self.capture(metadata={'asset_id': 'player:other'})
        self.assertIsNone(self.row()['value'])

    def test_pick_aliases_select_latest_compatible_before_winner(self):
        self.capture('pick:2026:2:7', kind='pick', value=100)
        self.capture('pick:2026:2:7', kind='future_pick', seconds=-60, value=200,
                     metadata={'asset_id':'pick:2026:2:8'})
        row = self.row(fixtures.PICK)
        self.assertEqual(row['value'], 100)
        self.assertIn('originally', row['asset_name'])

    def test_same_instant_conflicting_prices_are_unknown(self):
        self.capture(value=100)
        self.capture(value=800)
        row = self.row()
        self.assertIsNone(row['value'])
        self.assertIn('unique latest', row['admission_reason'])

    def test_conflict_between_pick_aliases_is_unknown(self):
        self.capture('pick:2026:2:7', kind='pick', value=100)
        self.capture('pick:2026:2:7', kind='future_pick', value=800)
        self.assertIsNone(self.row(fixtures.PICK)['value'])

    def test_post_trade_observation_is_excluded(self):
        self.capture(seconds=1)
        self.assertIsNone(self.row()['value'])
        self.assertIn('not decision-time eligible', self.row()['admission_reason'])

    def test_retained_unknown_later_or_ambiguous_knowledge_is_not_replaced(self):
        for clock in [None, '', 'not-a-time', self.boundary[:10],
                      (self.when+timedelta(seconds=1)).isoformat()]:
            with self.subTest(clock=clock):
                self.capture(value=100+self.serial*30)
                # Existing historical/legacy records, not a new provider claim.
                with self.f.fixture.memory._connect() as c:
                    for r in c.execute('SELECT observation_id,provider_evidence_json FROM global_market_observations').fetchall():
                        evidence=json.loads(r['provider_evidence_json'])
                        for e in evidence:
                            e['metadata']['source_knowledge_at']=clock
                        c.execute('UPDATE global_market_observations SET provider_evidence_json=? WHERE observation_id=?',
                                  (json.dumps(evidence),r['observation_id']))
                self.assertIsNone(self.row()['value'])

    def test_later_publication_is_excluded_and_earlier_quote_survives(self):
        self.capture(value=100)
        self.capture(seconds=-60, value=800, metadata={'published_at':(self.when+timedelta(seconds=1)).isoformat()})
        self.assertEqual(self.row()['value'], 100)

    def test_old_individual_value_remains_dated_not_package_freshness(self):
        self.capture(seconds=-30*86400, value=275)
        row = self.row()
        self.assertEqual((row['value'],row['quote_age_seconds'],row['match_state']), (275,30*86400,'DATED_ESTIMATE'))
        response = self.f.client.get('/trades/history/'+fixtures.ROOT)
        self.assertIn('30 days before the trade',response.text)
        self.assertIn('Package totals are not shown',response.text)
        self.assertIn('Dated estimate',response.text)
        self.assertIn('FantasyCalc',response.text)

    def test_zero_is_supported_and_exact_instant_is_distinct(self):
        self.capture(seconds=0,value=0)
        row=self.row()
        self.assertEqual((row['value'],row['quote_age_seconds'],row['match_state']),(0,0,'EXACT'))
        response=self.f.client.get('/trades/history/'+fixtures.ROOT)
        self.assertIn('Exact recorded observation',response.text)
        self.assertIn('Observed at the recorded trade instant',response.text)

    def test_subsecond_age_does_not_claim_the_trade_instant(self):
        self.capture(seconds=-0.25)
        row = self.row()
        self.assertEqual((row['quote_age_seconds'],row['match_state']),(0.25,'DATED_ESTIMATE'))
        response = self.f.client.get('/trades/history/'+fixtures.ROOT)
        self.assertIn('Less than a second before the trade',response.text)
        self.assertNotIn('Observed at the recorded trade instant',response.text)

    def test_partial_values_survive_without_package_claim(self):
        self.capture(value=321)
        response=self.f.client.get('/trades/history/'+fixtures.ROOT)
        self.assertEqual(response.status_code,200)
        self.assertIn('321.0',response.text)
        self.assertIn('Value withheld',response.text)
        self.assertIn('No quote in available exact asset/context evidence',response.text)
        self.assertNotIn('Complete comparable decision-time Market evidence is available',response.text)

    def test_conversion_does_not_price_the_original_pick(self):
        self.capture('player:13346',value=600)
        graph=self.f.graph()
        self.assertIsNotNone(graph.trade_timeline(fixtures.ROOT)['branches'])
        self.assertIsNone(self.row(fixtures.PICK)['value'])

    def test_reads_and_disclosures_do_not_acquire_or_persist(self):
        self.capture()
        memory=self.f.fixture.memory
        with memory._connect() as c:
            before=c.execute('SELECT * FROM global_market_observations ORDER BY observation_id').fetchall()
        with patch.object(memory,'put_sparse',side_effect=AssertionError('write on read')):
            for _ in range(3):
                self.assertEqual(self.f.client.get('/trades/history/'+fixtures.ROOT).status_code,200)
        with memory._connect() as c:
            self.assertEqual([tuple(r) for r in before],
                [tuple(r) for r in c.execute('SELECT * FROM global_market_observations ORDER BY observation_id')])
