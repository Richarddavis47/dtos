"""Storage review budgets: alerts, never canonical-data deletion authority."""
from dataclasses import dataclass

MIB = 1024 * 1024


@dataclass(frozen=True)
class StorageSample:
    measured_at_seconds: float
    file_bytes: int
    rows: int
    current_intelligence_bytes: int
    rebuildable_cache_bytes: int
    canonical_history_bytes: int
    orphaned_provenance_rows: int = 0
    retention_violations: int = 0


def review(current: StorageSample, *, previous: StorageSample | None = None,
           annual_start: StorageSample | None = None,
           expected_row_growth: int = 0, expected_byte_growth: int = 0):
    """Caller supplies measured per-league bytes and admitted write envelopes.

    No extrapolation from a short observation into a claimed annual measurement.
    Baselines are a bounded caller-owned sample, not a new metrics history store.
    """
    reasons = []
    if current.current_intelligence_bytes > 50 * MIB:
        reasons.append('CURRENT_INTELLIGENCE_REVIEW')
    if current.rebuildable_cache_bytes > 64 * MIB:
        reasons.append('REBUILDABLE_CACHE_REVIEW')
    if current.orphaned_provenance_rows:
        reasons.append('ORPHANED_PROJECTION_PROVENANCE')
    if current.retention_violations:
        reasons.append('RETENTION_RULE_VIOLATION')
    if previous is not None:
        if current.measured_at_seconds <= previous.measured_at_seconds:
            raise ValueError('Storage review requires increasing measurement time')
        if current.rows - previous.rows > expected_row_growth:
            reasons.append('UNEXPECTED_ROW_GROWTH')
        if current.file_bytes - previous.file_bytes > expected_byte_growth:
            reasons.append('UNEXPECTED_FILE_GROWTH')
    if annual_start is not None:
        if current.measured_at_seconds <= annual_start.measured_at_seconds:
            raise ValueError('Historical-growth baseline must precede measurement')
        if current.canonical_history_bytes - annual_start.canonical_history_bytes > 50 * MIB:
            reasons.append('HISTORICAL_GROWTH_REVIEW')
    return {'status': 'review_required' if reasons else 'within_review_budgets',
            'reasons': reasons, 'canonical_deletion_authorized': False}
