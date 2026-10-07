"""Compare symmetry reduction against the exact pre-reduction assignment solver."""

import inspect
import random
import unittest
from unittest.mock import patch

from src.core.trade_intelligence import lineup


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(
        unittest.FunctionTestCase(test)
        for test in (
            test_repeated_slot_symmetry_preserves_complete_and_partial_assignments,
            test_eligibility_reuse_preserves_exact_pre_reuse_solver,
            test_lazy_tie_keys_preserve_pre_correction_assignments,
        )
    )


def test_lazy_tie_keys_preserve_pre_correction_assignments():
    source = inspect.getsource(lineup.optimal_legal_lineup)
    optimized = "                candidate_score = score + projection\n                current = updated.get(mask | bit)\n                if current is not None and candidate_score < current[0]:\n                    continue\n                # Tie keys matter only on equal scores. Building them for every\n                # losing/winning assignment added substantial profiled overhead.\n                if current is None or candidate_score > current[0] or (\n                        tuple((entry.slot, entry.asset_id) for entry in selected) + ((slot, asset_id),) <\n                        tuple((entry.slot, entry.asset_id) for entry in current[1])):\n                    updated[mask | bit] = (candidate_score,\n                        selected + (LineupEntry(slot, asset_id, label, position, projection),))\n"
    original = "                candidate = (score + projection, selected + (LineupEntry(slot, asset_id, label, position, projection),))\n                current = updated.get(mask | bit)\n                # Tie keys matter only on equal scores. Building them for every\n                # losing/winning assignment added substantial profiled overhead.\n                if current is None or candidate[0] > current[0] or (candidate[0] == current[0] and\n                        tuple((entry.slot, entry.asset_id) for entry in candidate[1]) <\n                        tuple((entry.slot, entry.asset_id) for entry in current[1])):\n                    updated[mask | bit] = candidate\n"
    assert optimized in source
    namespace = dict(vars(lineup))
    exec(source.replace(optimized, original), namespace)
    reference = namespace["optimal_legal_lineup"]
    rng = random.Random(521)
    for _ in range(100):
        players = [
            {
                "id": str(i),
                "position": rng.choice(["QB", "RB", "WR", "TE"]),
                "projected_points": rng.choice([None, 0, -1, 5, 5, 20.125, 25.375]),
            }
            for i in range(rng.randrange(2, 22))
        ]
        slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX"]
        assert lineup.optimal_legal_lineup(players, slots) == reference(players, slots)


def test_eligibility_reuse_preserves_exact_pre_reuse_solver():
    source = inspect.getsource(lineup.optimal_legal_lineup)
    optimized = "            for index, slot, bit in eligible_slots:\n                if mask & bit:\n"
    original = (
        "            for index, slot in enumerate(slots):\n"
        "                bit = 1 << index\n"
        "                if mask & bit or not _eligible(position, slot):\n"
    )
    assert optimized in source
    namespace = dict(vars(lineup))
    exec(source.replace(optimized, original), namespace)
    reference = namespace["optimal_legal_lineup"]
    rng = random.Random(520)
    for _ in range(80):
        players = [
            {
                "id": str(i),
                "position": rng.choice(["QB", "RB", "WR", "TE", "K"]),
                "projected_points": rng.choice([None, 0, -1, 5, 10.125, 20]),
                "roster_slot": rng.choice(["BN", "BN", "IR", "TAXI"]),
                "bye_week": rng.choice([2, 3]),
            }
            for i in range(rng.randrange(3, 25))
        ]
        slots = rng.choices(
            ["QB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX", "REC_FLEX"], k=8
        )
        expected = reference(players, slots, week=2)
        with patch.object(lineup, "_eligible", wraps=lineup._eligible) as eligibility:
            assert lineup.optimal_legal_lineup(players, slots, week=2) == expected
            assert eligibility.call_count <= len(players) * len(slots)
        assert lineup.optimal_legal_lineup(reversed(players), slots, week=2) == expected


def test_repeated_slot_symmetry_preserves_complete_and_partial_assignments():
    source = inspect.getsource(lineup.optimal_legal_lineup)
    guard = "                if index and slots[index - 1] == slot and not mask & (1 << (index - 1)):\n                    continue\n"
    assert guard in source
    namespace = dict(vars(lineup))
    exec(source.replace(guard, ""), namespace)
    reference = namespace["optimal_legal_lineup"]
    rng = random.Random(519)
    configurations = [
        ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "SUPER_FLEX"],
        ["WR", "WR", "WR", "FLEX", "FLEX"],
        ["QB", "QB", "TE", "TE", "SUPER_FLEX"],
    ]
    for index in range(60):
        players = [
            {
                "id": str(i),
                "position": rng.choice(["QB", "RB", "WR", "TE"]),
                "projected_points": rng.choice([None, 0, -1, 5, 5, 10, 20.125]),
            }
            for i in range(rng.randrange(3, 18))
        ]
        slots = configurations[index % len(configurations)]
        expected = reference(players, slots)
        assert lineup.optimal_legal_lineup(players, slots) == expected
        assert lineup.optimal_legal_lineup(reversed(players), slots) == expected
