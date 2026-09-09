import unittest

from src.core.data_platform.evidence_availability import Availability, assess_availability


class EvidenceAvailabilityTests(unittest.TestCase):
    def assess(self, **changes):
        fields = dict(connected=True, applicable=True, value_present=True,
                      checked_at="2026-09-01T00:00:00Z", as_of="2026-09-02T00:00:00Z",
                      evidence_family="nflverse_open_performance")
        return assess_availability(**(fields | changes))

    def test_missing_and_unconnected_and_small_sample_differ(self):
        self.assertEqual(self.assess(value_present=False).state, Availability.UNAVAILABLE)
        self.assertEqual(self.assess(connected=False).state, Availability.NOT_CONNECTED)
        self.assertEqual(self.assess(sample_count=0).state, Availability.INSUFFICIENT_SAMPLE)
        self.assertEqual(self.assess(applicable=False).state, Availability.NOT_APPLICABLE)

    def test_real_zero_is_present_and_completed_history_does_not_expire(self):
        value = 0
        self.assertEqual(self.assess(value_present=value is not None).state, Availability.CACHED)
        self.assertEqual(self.assess(as_of="2030-09-01T00:00:00Z", completed_period=True).state, Availability.CACHED)
        self.assertEqual(self.assess(as_of="2030-09-01T00:00:00Z").state, Availability.STALE)

    def test_future_observation_is_not_historical_evidence(self):
        result = self.assess(as_of="2026-08-01T00:00:00Z")
        self.assertEqual(result.state, Availability.UNAVAILABLE)
        self.assertEqual(result.reason, "observation_after_as_of")
