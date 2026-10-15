"""Disposable projection of completed canonical searches; never discovers trades."""

from contextlib import contextmanager
from collections import OrderedDict
from copy import deepcopy
from hashlib import sha256
import json
from threading import RLock
from time import monotonic

from services.trade_workspace_context import workspace_context
from services.trade_search_policy import ELIGIBLE, classify, supported_exploration

MAX_ENTRIES = 24
MAX_BYTES = 2_097_152
MAX_AGE = 900
_entries = OrderedDict()
_lock = RLock()
_inflight = set()


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _semantic(value):
    # Retrieval clock churn is not a new price/roster/projection publication.
    if isinstance(value, dict):
        return {
            k: _semantic(v)
            for k, v in value.items()
            if k
            not in {
                "retrieved_at",
                "fetched_at",
                "last_sync",
                "synced_at",
                "last_synced_at",
                "generated_at",
            }
        }
    if isinstance(value, (list, tuple)):
        return [_semantic(v) for v in value]
    return value


def source_identity(data):
    from services.trade_intelligence import _trade_projection_service
    from src.core.projection_intelligence.service import canonical_projection_identity
    from src.core.valuation.normalization import capture_market_publication

    market, coherent = capture_market_publication(data.get("market_data") or {})
    if not coherent:
        return None
    league_id = str((data.get("league") or {}).get("league_id") or "")
    projection = canonical_projection_identity(
        _trade_projection_service(data).snapshot(), league_id
    )
    # Expire retained diagnostic explanations at source-age/refresh boundaries
    # without discovery or any legal-lineup computation on a Home read.
    from src.core.intelligence.roster_diagnostics import _qualification

    reader = _trade_projection_service(data)
    diagnostic_evidence = _qualification(
        data,
        reader.snapshot(),
        tuple((data.get("league") or {}).get("roster_positions") or ()),
        projection_reader=reader,
    )
    return _digest(
        (
            _semantic(
                {
                    key: data.get(key)
                    for key in (
                        "league",
                        "week",
                        "season",
                        "teams",
                        "players",
                        "team_strength",
                        "competitive_windows",
                        "fois",
                        "fois_evidence",
                        "intelligence_evidence",
                    )
                }
            ),
            _semantic(market),
            projection,
            {
                "projection_freshness": diagnostic_evidence["projection_freshness"],
                "conclusion_state": diagnostic_evidence["conclusion_state"],
                "retained_publication": bool(
                    diagnostic_evidence["refresh"].get("retained_publication")
                ),
            },
            "bilateral_trade_v3/home_projection_v1/legal-roster-diagnostics-v1",
        )
    )


def constraints(protected=(), excluded=()):
    if any(
        not isinstance(ids, (list, tuple))
        or len(ids) > 256
        or any(not isinstance(i, str) or not i or len(i) > 256 for i in ids)
        for ids in (protected, excluded)
    ):
        raise ValueError("invalid_exact_protections")
    return tuple(sorted(set(protected))), tuple(sorted(set(excluded)))


def cache_key(data, roster_id, strategy, protected=(), excluded=()):
    identity = source_identity(data)
    if identity is None:
        return None
    return (
        workspace_context(data, roster_id)["binding"],
        identity,
        strategy or "",
        *constraints(protected, excluded),
    )


def _purge():
    for key in list(_entries):
        if monotonic() - _entries[key][0] > MAX_AGE:
            del _entries[key]


def publish(key, result, payload):
    if (
        key is None
        or payload.get("recommendation_filter") not in (None, "", "all")
        or payload.get("excluded_recommendation_families")
    ):
        return
    protected, excluded = constraints(
        payload.get("protected_assets") or [], payload.get("excluded_assets") or []
    )
    chosen, families, packages = [], set(), set()
    for exploratory, rows in (
        (False, result.get("results") or []),
        (True, result.get("exploratory_results") or []),
    ):
        for raw in rows:
            e, p = raw.get("evaluation") or {}, raw.get("proposal") or {}
            if not supported_exploration(e) or (
                not exploratory
                and (
                    classify(e) not in ELIGIBLE
                    or e.get("recommendation")
                    not in ("SMASH ACCEPT", "WORTH PURSUING", "FAIR / OPTIONAL")
                )
            ):
                continue
            sent, received = p.get("assets_sent") or [], p.get("assets_received") or []
            if (
                not sent
                or not received
                or set(sent) & (set(protected) | set(excluded))
                or set(received) & set(excluded)
            ):
                continue
            package = (
                p.get("partner_roster_id"),
                tuple(sorted(sent)),
                tuple(sorted(received)),
            )
            family = raw.get("family_id") or package
            if family in families or package in packages:
                continue
            families.add(family)
            packages.add(package)
            row = deepcopy(raw)
            row.pop("variants", None)
            row["exploration"] = exploratory
            row["home_source_identity"] = key[1]
            row["home_assessment_strategy"] = key[2]
            row["home_offer"] = _digest((key, package))[:40]
            chosen.append(row)
            if len(chosen) == 4:
                break
        if len(chosen) == 4:
            break
    encoded = json.dumps(
        {
            "rows": chosen,
            "state": result.get("result_state"),
            "reason": result.get("quiet_state"),
            "source_identity": key[1],
        },
        default=str,
    ).encode()
    if len(encoded) > MAX_BYTES:
        return
    with _lock:
        _purge()
        _entries[key] = (monotonic(), encoded)
        _entries.move_to_end(key)
        while (
            len(_entries) > MAX_ENTRIES
            or sum(len(v[1]) for v in _entries.values()) > MAX_BYTES
        ):
            _entries.popitem(last=False)


def read(key):
    with _lock:
        _purge()
        item = _entries.get(key)
        if item is None:
            stale = key is not None and any(k[0] == key[0] for k in _entries)
            return {
                "rows": [],
                "state": "STALE SOURCE OR INTENT" if stale else "NOT SEARCHED",
                "reason": "Earlier results no longer match the current source, strategy or protections."
                if stale
                else "Find supported opportunities using the existing bounded search.",
            }
        _entries.move_to_end(key)
        return json.loads(item[1])


def health():
    with _lock:
        _purge()
        return {
            "entries": len(_entries),
            "bytes": sum(len(v[1]) for v in _entries.values()),
            "max_entries": MAX_ENTRIES,
            "max_bytes": MAX_BYTES,
            "max_age_seconds": MAX_AGE,
        }


@contextmanager
def search_slot(binding):
    """One explicit Home search at a time; cancellation cannot spawn a loop."""
    from services.trade_intelligence import TradeInputError

    with _lock:
        if _inflight:
            raise TradeInputError(
                "search_busy",
                "Another Home search is still completing. Your draft is unchanged; try again shortly.",
            )
        _inflight.add(binding)
    try:
        yield
    finally:
        with _lock:
            _inflight.discard(binding)
