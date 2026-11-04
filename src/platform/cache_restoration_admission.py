"""Pure arithmetic shared by restoration and its advisory metadata probe.

No telemetry, lifecycle, file or service access happens here.  The caller must
still obtain its own current inputs and, for actual work, the existing lease.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

MIB = 1024 * 1024
SERVICE_LIMIT = 2 * 1024 * MIB
CACHE_EXPANSION_FACTOR = 16
CACHE_MINIMUM_WORKING = 128 * MIB
CACHE_SAFETY = 128 * MIB


def restoration_admission(
    file_bytes: Any,
    memory: Mapping[str, Any] | None,
    fois_active: Any,
    *,
    fois_working_bytes: int,
    fois_safety_bytes: int,
    expansion_factor: int = CACHE_EXPANSION_FACTOR,
    minimum_working_bytes: int = CACHE_MINIMUM_WORKING,
    cache_safety_bytes: int = CACHE_SAFETY,
    service_limit_bytes: int = SERVICE_LIMIT,
) -> dict[str, Any]:
    """Describe the unchanged raw-headroom predicate without granting admission.

    The optional policy arguments preserve the existing restoration module's
    exported constants and test overrides.  They are server-owned, never request
    parameters.  Genuine zero usage/size is valid; bool is not numeric evidence.
    """
    sample = memory if isinstance(memory, Mapping) else {}
    used, limit = sample.get('cgroup_current_bytes'), sample.get('cgroup_limit_bytes')
    telemetry_valid = (type(used) is int and type(limit) is int and used >= 0 and limit > 0)
    file_valid = type(file_bytes) is int and file_bytes >= 0
    reservation_valid = type(fois_active) is bool
    working = max(minimum_working_bytes, file_bytes * expansion_factor) if file_valid else None
    safety = (
        max(fois_safety_bytes, cache_safety_bytes) if fois_active else cache_safety_bytes
    ) if reservation_valid else None
    fois_working = (fois_working_bytes if fois_active else 0) if reservation_valid else None
    fois_safety = (fois_safety_bytes if fois_active else 0) if reservation_valid else None
    required = working + safety + fois_working if file_valid and reservation_valid else None
    effective_limit = min(limit, service_limit_bytes) if telemetry_valid else None
    headroom = effective_limit - used if telemetry_valid else None
    if not file_valid:
        reason, admitted = 'unknown_file_size', None
    elif not reservation_valid:
        reason, admitted = 'unknown_reservation', None
    elif not telemetry_valid:
        reason, admitted = 'unknown_memory', None
    else:
        admitted = headroom >= required
        reason = 'sufficient_headroom' if admitted else 'insufficient_headroom'
    return {
        'telemetry_valid': telemetry_valid,
        'file_size_valid': file_valid,
        'reservation_valid': reservation_valid,
        'working_bytes': working,
        'cache_safety_bytes': cache_safety_bytes,
        'safety_bytes': safety,
        'fois_working_bytes': fois_working,
        'fois_safety_bytes': fois_safety,
        'required_bytes': required,
        'service_limit_bytes': service_limit_bytes,
        'effective_limit_bytes': effective_limit,
        'headroom_bytes': headroom,
        'would_admit': admitted,
        'reason': reason,
    }
