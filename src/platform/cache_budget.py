"""Fail-closed cache publication budgets; never delete unclassified evidence.

Limits govern newly published cache bytes, including atomic replacement scratch.
Expiry controls reuse, not permission to destroy a possibly irreplaceable file.
Eviction requires a separately verified refetchability/ownership classification.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
import shutil
import time

MIB = 1024 * 1024


class CacheAdmissionError(OSError):
    pass


@dataclass(frozen=True)
class CacheBudget:
    maximum_entry_bytes: int
    maximum_aggregate_bytes: int
    maximum_age_seconds: int
    maximum_generations: int = 1
    reserve_bytes: int = 128 * MIB


JSON_BUDGET = CacheBudget(64 * MIB, 256 * MIB, 30 * 86400)
SEASON_BUDGET = CacheBudget(2 * MIB, 64 * MIB, 365 * 86400)
# The retained full-universe read model already exceeds 64 MiB (about 76 MiB
# before this release). Permit a bounded 128 MiB generation, not an unbounded
# SQLite file; aggregate admission covers three resident generations plus one
# replacement candidate. The existing journal/headroom reservation still applies.
MARKET_BUDGET = CacheBudget(128 * MIB, 512 * MIB, 0)
SEASON_LEAGUE_BYTES = 8 * MIB
SEASON_COUNT = 6


def json_family(base):
    """Respect configured cache roots/names; do not include unrelated JSON."""
    base = Path(base)
    if not base.parent.exists():
        return []
    return [p for p in base.parent.iterdir() if p.is_file() and not p.is_symlink()
            and (p.name == base.name or (p.name.startswith(base.stem + '.')
                 and p.name.endswith(base.suffix)))]


def inspect(target, *, entries, budget, incoming_bytes, now=None):
    """Read-only admission plan. Never allocate a giant file to discover limits."""
    target = Path(target)
    if target.is_symlink():
        raise CacheAdmissionError('Cache target must not be a symlink')
    incoming_bytes = int(incoming_bytes)
    if incoming_bytes < 0:
        raise ValueError('Negative cache publication size')
    now = time.time() if now is None else now
    paths = set(map(Path, entries))
    measured = {path: path.stat() for path in paths}
    total = sum(s.st_size for s in measured.values())
    replacing = measured[target].st_size if target in measured else 0
    expected = total - replacing + incoming_bytes
    parent = target.parent
    while not parent.exists():
        parent = parent.parent
    free = shutil.disk_usage(parent).free
    reasons = []
    if incoming_bytes > budget.maximum_entry_bytes:
        reasons.append('CACHE_ENTRY_BUDGET_EXCEEDED')
    if expected > budget.maximum_aggregate_bytes:
        reasons.append('CACHE_AGGREGATE_BUDGET_EXCEEDED')
    if free < budget.reserve_bytes + incoming_bytes:
        reasons.append('CACHE_REPLACEMENT_HEADROOM_INSUFFICIENT')
    return {'admitted': not reasons, 'reasons': reasons, 'current_bytes': total,
            'expected_bytes': expected, 'replacement_peak_bytes': total + incoming_bytes,
            'expired_entries': sum(now - s.st_mtime > budget.maximum_age_seconds for s in measured.values()),
            'free_bytes': free, 'maximum_generations': budget.maximum_generations}


def require(target, *, entries, budget, incoming_bytes):
    result = inspect(target, entries=entries, budget=budget, incoming_bytes=incoming_bytes)
    if not result['admitted']:
        raise CacheAdmissionError(','.join(result['reasons']))
    return result


def reusable(path, budget, *, now=None):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        return False
    state = path.stat()
    age = (time.time() if now is None else now) - state.st_mtime
    return 0 <= age <= budget.maximum_age_seconds and state.st_size <= budget.maximum_entry_bytes


def require_season(target, root, incoming_bytes, *, excluded=()):
    target, root = Path(target), Path(root)
    excluded = set(map(Path, excluded))
    paths = [p for p in root.glob('*/*.json.gz') if p.is_file() and not p.is_symlink() and p not in excluded]
    require(target, entries=paths, budget=SEASON_BUDGET, incoming_bytes=incoming_bytes)
    local = [p for p in paths if p.parent == target.parent and p != target]
    if len(local) + 1 > SEASON_COUNT:
        raise CacheAdmissionError('SEASON_COUNT_REQUIRES_VERIFIED_REFETCH_EVICTION')
    if sum(p.stat().st_size for p in local) + incoming_bytes > SEASON_LEAGUE_BYTES:
        raise CacheAdmissionError('SEASON_LEAGUE_BUDGET_EXCEEDED')


@contextmanager
def json_admission(target, base, incoming_bytes):
    from src.platform.storage_gate import database_gate
    with database_gate(Path(base).parent / '.json-cache-quota', exclusive=True):
        require(target, entries=json_family(base), budget=JSON_BUDGET, incoming_bytes=incoming_bytes)
        yield


@contextmanager
def season_admission(target, root, incoming_bytes):
    from src.platform.storage_gate import database_gate
    with database_gate(Path(root) / '.season-cache-quota', exclusive=True):
        require_season(target, root, incoming_bytes)
        yield


@contextmanager
def market_admission(target):
    """Reserve one maximum-sized build; preserve last-valid on rejection.

    Market age is governed by manifest compatibility, not a fabricated TTL.
    The quota never includes canonical Market history or provenance databases.
    """
    from src.platform.storage_gate import database_gate
    target = Path(target)
    marker = '.asset-market-'
    pattern = target.name.split(marker)[0] + marker + '*' if marker in target.name else '*' + target.name + '*'
    with database_gate(target.parent / '.market-readiness-quota', exclusive=True):
        candidates = set(target.parent.glob(pattern)) | set(target.parent.glob('.' + pattern))
        entries = [p for p in candidates if p.is_file()]
        report = require(target, entries=entries, budget=MARKET_BUDGET,
                         incoming_bytes=MARKET_BUDGET.maximum_entry_bytes)
        # SQLite DELETE journaling may temporarily duplicate a full candidate.
        if report['free_bytes'] < MARKET_BUDGET.reserve_bytes + 2 * MARKET_BUDGET.maximum_entry_bytes:
            raise CacheAdmissionError('MARKET_ATOMIC_BUILD_HEADROOM_INSUFFICIENT')
        yield MARKET_BUDGET
