import unittest

from src.core.data_platform.identity_crosswalk import crosswalk_resolver


class IdentityCrosswalkTests(unittest.TestCase):
    def test_exact_id_enrichment_never_name_match(self):
        resolver, report = crosswalk_resolver({"1": {"full_name": "Same Name"}}, [
            {"sleeper_id": "1", "gsis_id": "00-1"},
            {"sleeper_id": "2", "gsis_id": "00-2", "name": "Same Name"}])
        self.assertEqual(resolver.resolve("00-1", "GSIS").dtos_id, "1")
        self.assertIsNone(resolver.resolve("00-2", "GSIS"))
        self.assertEqual(report["unknown_sleeper_rows"], 1)

    def test_conflicts_fail_closed_in_both_directions(self):
        resolver, report = crosswalk_resolver({"1": {"gsis_id": "00-1"}, "2": {}}, [
            {"sleeper_id": "1", "gsis_id": "00-2"},
            {"sleeper_id": "2", "gsis_id": "00-1"}])
        self.assertIsNone(resolver.resolve("00-1", "GSIS"))
        self.assertIsNone(resolver.resolve("00-2", "GSIS"))
        self.assertEqual(report["ambiguous_players"], 1)
        self.assertEqual(report["ambiguous_gsis_ids"], 1)
        self.assertEqual(resolver.resolve("1", "Sleeper").dtos_id, "1")

    def test_duplicate_rows_and_names_do_not_change_join_generation(self):
        rows = [{"sleeper_id": "1", "gsis_id": "00-1"}]
        a, _ = crosswalk_resolver({"1": {"full_name": "Before"}}, rows)
        b, _ = crosswalk_resolver({"1": {"full_name": "After"}}, rows * 2)
        self.assertEqual(a.mapping_fingerprint("GSIS"), b.mapping_fingerprint("GSIS"))
