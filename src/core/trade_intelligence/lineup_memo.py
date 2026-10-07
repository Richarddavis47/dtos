"""Bounded reuse of exact lineup mathematics, never canonical evidence or prices."""
from collections import OrderedDict
from dataclasses import fields, is_dataclass
from hashlib import sha256
import json
from sys import getsizeof
from threading import RLock
from time import monotonic, perf_counter

from .lineup import optimal_legal_lineup


def _bytes(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = getsizeof(value)
    if is_dataclass(value):
        size += getsizeof(value.__dict__)
        size += sum(_bytes(getattr(value, field.name), seen) for field in fields(value))
    elif isinstance(value, (tuple, list)):
        size += sum(_bytes(item, seen) for item in value)
    return size


class LineupStore:
    """TTL/LRU with conservative retained-byte and entry caps; no worker creation."""
    def __init__(self, *, max_bytes=32 * 1024 * 1024, max_entries=8192, ttl=180, clock=monotonic):
        self.max_bytes, self.max_entries = max(0, max_bytes), max(0, max_entries)
        self.ttl, self.clock = max(0, ttl), clock
        self.entries = OrderedDict()
        self.retained_bytes = 0
        self.lock = RLock()

    def get(self, key):
        with self.lock:
            entry = self.entries.get(key)
            if entry is None:
                return None
            value, expiry, size = entry
            if expiry <= self.clock():
                self.retained_bytes -= size
                del self.entries[key]
                return None
            self.entries.move_to_end(key)
            return value

    def put(self, key, value):
        # Include dictionary/LRU bookkeeping and conservatively count shared
        # result objects for each entry. Oversize/disabled caches retain nothing.
        size = _bytes(key) + _bytes(value) + 256
        if not self.max_entries or not self.ttl or size > self.max_bytes:
            return
        with self.lock:
            old = self.entries.pop(key, None)
            if old is not None:
                self.retained_bytes -= old[2]
            while self.entries and (len(self.entries) >= self.max_entries or self.retained_bytes + size > self.max_bytes):
                _, entry = self.entries.popitem(last=False)
                self.retained_bytes -= entry[2]
            self.entries[key] = (value, self.clock() + self.ttl, size)
            self.retained_bytes += size

    def clear(self):
        with self.lock:
            self.entries.clear()
            self.retained_bytes = 0

    def expire(self):
        with self.lock:
            now = self.clock()
            for key, (_, expiry, size) in list(self.entries.items()):
                if expiry <= now:
                    del self.entries[key]
                    self.retained_bytes -= size

    def status(self):
        with self.lock:
            return {'entries': len(self.entries), 'retained_bytes': self.retained_bytes,
                    'maximum_bytes': self.max_bytes, 'maximum_entries': self.max_entries,
                    'ttl_seconds': self.ttl}


lineup_store = LineupStore()


class SearchLineupMemo:
    """Request counters over session/league/generation-scoped immutable results.

    Every mathematical input participates in the key, including names, exclusion
    state, projections, slots and week-specific bye eligibility. Week provenance
    stays outside the immutable math result. Neither intent nor prices affect solving.
    Publication/ownership/scoring changes additionally change the search scope.
    """
    def __init__(self, scope, store=lineup_store):
        self.scope, self.store = scope, store
        self.store.expire()
        self.hits = self.misses = 0
        self.seconds = 0.0

    def solve(self, players, positions, *, week=None):
        started = perf_counter()
        players, positions = list(players), list(positions)
        # The solver's only direct use of week is excluding known byes. Identical
        # projections/eligibility in two weeks have exactly the same math result;
        # generation, week IDs and confidence remain in the caller's evidence.
        mathematical_players = [{k: v for k, v in player.items() if k != 'bye_week'} |
                                {'_known_bye': week is not None and player.get('bye_week') == week}
                                for player in players]
        digest = sha256(json.dumps((mathematical_players, positions), sort_keys=True,
                                  separators=(',', ':')).encode()).digest()
        key = (self.scope, digest)
        value = self.store.get(key)
        if value is None:
            self.misses += 1
            value = optimal_legal_lineup(players, positions, week=week)
            self.store.put(key, value)
        else:
            self.hits += 1
        self.seconds += perf_counter() - started
        return value

    def status(self):
        return {'lineup_hits': self.hits, 'lineup_misses': self.misses,
                'lineup_seconds': self.seconds, 'lineup_cache': self.store.status(),
                'scope': 'account_session_league_generation_and_exact_math_inputs',
                'candidate_results_retained': 0, 'workers_created': 0}
