"""FOIS flight reuse preserves canonical historical evidence and isolation."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import src.core.intelligence  # noqa: F401 -- canonical application import boundary
from src.core.historical_franchise_state import HistoricalFranchiseStateService
from src.core.historical_intelligence import HistoricalIntelligenceService
from src.core.intelligence_memory.checkpoint_flight import (
    CheckpointGenerationChanged, CheckpointReadFlight, checkpoint_read_flight,
)
from src.core.intelligence_memory.models import (
    CheckpointTrigger, EvidenceCompleteness, IntelligenceCheckpoint, ProvenanceType,
)
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from tests.test_historical_franchise_state import FixtureStore


class CheckpointFlightTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = IntelligenceCheckpointStore(Path(self.directory.name) / "checkpoints.sqlite3")
        for asset, value in (("player-old", 5000), ("player-new", 6000), ("player-stay", 2000)):
            self.put(asset, "2025-09-20T00:00:00Z", value)

    def put(self, asset, when, value):
        self.store.put_sparse(IntelligenceCheckpoint(
            checkpoint_id=f"{asset}-{when}", asset_id=asset, asset_type="player",
            timestamp=when, season=2025, trigger_type=CheckpointTrigger.TRADE_EXECUTION,
            provenance_type=ProvenanceType.LIVE_CAPTURED, league_id="league-a",
            market_value=value, confidence=90, evidence_completeness=EvidenceCompleteness.COMPLETE,
            model_version="fixture-v1", related_event_id=f"trade-{when}",
        ), market_context_id="player:global")

    def evaluate(self, reader, league="league-a", as_of="2025-12-31T00:00:00Z", event_suffix="1"):
        from src.core.historical_transaction_intelligence import HistoricalTransactionIntelligenceService
        facts = FixtureStore(league)
        trade = next(row for row in facts.rows if row["entity_type"] == "trade")
        trade["source_record_id"] = f"trade-{event_suffix}"
        history = HistoricalIntelligenceService(facts, checkpoint_reader=reader)
        service = HistoricalTransactionIntelligenceService(history, HistoricalFranchiseStateService(history))
        event = history.transaction_history(league)[0]
        return service.evaluate_trade(league, event.event_id, as_of=as_of)

    def test_equivalent_bilateral_results_boundaries_and_isolation(self):
        self.put("player-new", "2025-11-01T00:00:00Z", 9000)
        with checkpoint_read_flight(self.store) as reader:
            results = []
            for league, boundary, transaction in (
                ("league-a", "2025-10-02T00:00:00Z", "1"),
                ("league-b", "2025-12-31T00:00:00Z", "2"),
                ("league-a", "2025-12-31T00:00:00Z", "3"),
            ):
                canonical = self.evaluate(self.store, league, boundary, transaction)
                cached = self.evaluate(reader, league, boundary, transaction)
                self.assertEqual(asdict(cached), asdict(canonical))
                self.assertTrue(all(side.franchise_id.startswith(league + ":") for side in cached.sides))
                results.append(cached)
            self.assertNotEqual(results[0].event_id, results[2].event_id)
            self.assertGreater(reader.cache_hits, reader.storage_reads)
            self.assertEqual(reader.global_market_checkpoints(asset_id="missing"), [])
            reads = reader.storage_reads
            self.assertEqual(reader.global_market_checkpoints(asset_id="missing"), [])
            self.assertEqual(reader.storage_reads, reads)

    def test_no_hindsight_and_new_generation(self):
        with checkpoint_read_flight(self.store) as reader:
            old = self.evaluate(reader)
            generation = reader.generation
        self.put("player-new", "2025-11-01T00:00:00Z", 99999)
        with checkpoint_read_flight(self.store) as reader:
            new = self.evaluate(reader)
            self.assertNotEqual(generation, reader.generation)
            self.assertEqual([asdict(s.process) for s in old.sides], [asdict(s.process) for s in new.sides])
            self.assertEqual(asdict(new), asdict(self.evaluate(self.store)))

    def test_concurrent_write_discards_flight_and_tears_down(self):
        with self.assertRaises(CheckpointGenerationChanged):
            with checkpoint_read_flight(self.store) as reader:
                before = reader.global_market_checkpoints(asset_id="player-new")
                self.put("player-new", "2025-11-01T00:00:00Z", 9000)
                self.assertEqual(before, reader.global_market_checkpoints(asset_id="player-new"))
        self.assertTrue(reader.closed)
        self.assertEqual(reader.retained_bytes, 0)
        with self.assertRaises(RuntimeError):
            reader.global_market_checkpoints(asset_id="player-new")

    def test_reference_and_method_changes_invalidate_generation(self):
        with checkpoint_read_flight(self.store) as reader:
            generation = reader.generation
        with self.store._connect() as connection:
            connection.execute("UPDATE intelligence_checkpoints SET knowledge_state='related_player_impact:fixture'")
        with checkpoint_read_flight(self.store) as reader:
            self.assertNotEqual(generation, reader.generation)
            generation = reader.generation
            self.assertIn("fixture", reader.global_market_checkpoints(asset_id="player-new")[0].relationship_evidence)
        with self.store._connect() as connection:
            connection.execute("UPDATE global_market_observations SET normalization_version='next-method'")
        with checkpoint_read_flight(self.store) as reader:
            self.assertNotEqual(generation, reader.generation)

    def test_bounded_cache_eviction_and_mutation_cannot_contaminate(self):
        with checkpoint_read_flight(self.store) as flight:
            reader = CheckpointReadFlight(self.store, flight.connection, max_entries=1)
            for asset in ("player-new", "player-old", "player-new"):
                self.assertEqual(reader.global_market_checkpoints(asset_id=asset), self.store.global_market_checkpoints(asset_id=asset))
                self.assertLessEqual(len(reader.cache), 1)
            self.assertEqual(reader.storage_reads, 3)
            rows = reader.global_market_checkpoints(asset_id="player-new")
            rows.clear()
            self.assertEqual(len(reader.global_market_checkpoints(asset_id="player-new")), 1)

    def test_restart_cross_process_generation_and_output_determinism(self):
        with checkpoint_read_flight(self.store) as reader:
            expected = json.loads(json.dumps({"generation": reader.generation, "rows": [asdict(row) for row in reader.global_market_checkpoints(asset_id="player-new")]}))
        code = (
            "import json,sys; from pathlib import Path; from dataclasses import asdict; "
            "from src.core.intelligence_memory.store import IntelligenceCheckpointStore; "
            "from src.core.intelligence_memory.checkpoint_flight import checkpoint_read_flight; "
            "s=IntelligenceCheckpointStore(Path(sys.argv[1])); "
            "\nwith checkpoint_read_flight(s) as r: print(json.dumps({'generation':r.generation,'rows':[asdict(x) for x in r.global_market_checkpoints(asset_id='player-new')]}))"
        )
        result = subprocess.run([sys.executable, "-c", code, str(self.store.path)], capture_output=True, text=True, timeout=20, check=True)
        self.assertEqual(json.loads(result.stdout), expected)

    def test_ipc_generation_change_cannot_replace_last_valid_publication(self):
        from src.core.fois.process_execution import _validate_and_publish
        from src.core.fois.repository import FOISRepository

        root = Path(self.directory.name)
        repository = FOISRepository(root / "published.sqlite3")
        working = FOISRepository(root / "candidate.sqlite3")
        before = repository.path.read_bytes()
        with checkpoint_read_flight(self.store) as reader:
            generation = reader.generation
        self.put("player-new", "2025-11-01T00:00:00Z", 9000)
        with patch("src.core.intelligence_memory.intelligence_checkpoint_store", self.store):
            with self.assertRaises(CheckpointGenerationChanged):
                _validate_and_publish(working.path, repository, "league-a", 0, generation)
        self.assertEqual(repository.path.read_bytes(), before)
        self.assertTrue(working.path.exists())
