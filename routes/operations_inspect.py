"""Private fixed operations over configured stores, with no user SQL/path inputs."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from src.platform import operational_inspection as evidence
from src.platform.inspection_security import (
    OPERATIONS,
    PREFIX,
    PRIVATE_HEADERS,
    inspection_authorized,
)
from tools.projection_reachability import InspectionLimit

# One diagnostic at a time per worker. Heavy graph scans also have a cooldown.
_DIAGNOSTIC_LOCK = Lock()
_NEXT_GRAPH_READ = 0.0
GRAPH_COOLDOWN_SECONDS = 5.0
MAX_RESPONSE_BYTES = 256 * 1024


def _authorize(request: Request):
    if not inspection_authorized(request.scope):
        raise HTTPException(401, 'Inspection authorization required', headers=PRIVATE_HEADERS)


def _sanitize_graph(report):
    # Analyzer errors may include malformed payload keys/unknown table names.
    # Keep the logical error count and approved reason codes, never raw errors.
    allowed = {'MISSING_SNAPSHOT', 'HORIZON_SCOPE_MISMATCH', 'SELF_REFERENCE_WEEK_MISMATCH',
               'NESTED_HORIZON', 'HEAD_LEAGUE_MISMATCH', 'PREVIOUS_HEAD_LEAGUE_MISMATCH',
               'MISSING_PLAYER_STATE', 'UNKNOWN_TABLE_REQUIRES_REVIEW'}
    if report['unresolved_references']:
        errors = []
        for row in report['unresolved_references']:
            error = {'reason': row['reason'] if row.get('reason') in allowed else 'INVALID_PROJECTION_RECORD'}
            for key in ('snapshot_id', 'state_id', 'parent'):
                value = row.get(key)
                if isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value):
                    error[key] = value
            if type(row.get('source_observation_id')) is int:
                error['source_observation_id'] = row['source_observation_id']
            errors.append(error)
        report['unresolved_references'] = errors
        report.pop('report_sha256')
        report['report_sha256'] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    return report


def create_operations_inspection_router(*, stores=None):
    router = APIRouter(prefix=PREFIX, tags=['private operations inspection'],
                       dependencies=[Depends(_authorize)], include_in_schema=False)

    @router.get('')
    def catalog(request: Request):
        if request.query_params:
            raise HTTPException(400, 'Unsupported inspection parameters', headers=PRIVATE_HEADERS)
        return JSONResponse({'schema': 'dtos-operations-v1', 'operations': sorted(OPERATIONS),
                             'read_only': True}, headers=PRIVATE_HEADERS)

    @router.get('/{operation}')
    def inspect(operation: str, request: Request):
        global _NEXT_GRAPH_READ
        if operation not in OPERATIONS:
            raise HTTPException(404, 'Unsupported inspection operation', headers=PRIVATE_HEADERS)
        allowed = {'limit', 'offset'} if operation == 'projection-inventory' else set()
        params = list(request.query_params.multi_items())
        if (len(request.scope.get('query_string', b'')) > 128 or len(params) > 2
                or any(k not in allowed for k, _ in params) or len({k for k, _ in params}) != len(params)):
            raise HTTPException(400, 'Unsupported inspection parameters', headers=PRIVATE_HEADERS)
        limit, offset = 50, 0
        if allowed:
            try:
                values = dict(params)
                if any(not v.isascii() or not v.isdigit() for v in values.values()):
                    raise ValueError
                limit, offset = int(values.get('limit', '50')), int(values.get('offset', '0'))
                if not 1 <= limit <= 100 or not 0 <= offset <= 4096:
                    raise ValueError
            except ValueError:
                raise HTTPException(400, 'Inventory bounds: limit 1..100, offset 0..4096', headers=PRIVATE_HEADERS) from None
        if not _DIAGNOSTIC_LOCK.acquire(blocking=False):
            raise HTTPException(429, 'Inspection busy', headers={**PRIVATE_HEADERS, 'Retry-After': '5'})
        try:
            graph = operation in {'projection-inventory', 'projection-reachability'}
            if graph and time.monotonic() < _NEXT_GRAPH_READ:
                raise HTTPException(429, 'Graph inspection cooling down', headers={**PRIVATE_HEADERS, 'Retry-After': '5'})
            if graph:
                _NEXT_GRAPH_READ = time.monotonic() + GRAPH_COOLDOWN_SECONDS
            budget = evidence.Budget(time.monotonic() + (10 if graph else 3))
            selected = stores or evidence.InspectionStores.configured()
            if operation == 'identity':
                result = evidence.identity()
            elif operation == 'storage':
                result = evidence.storage(selected, budget)
            elif operation == 'projection-reachability':
                result = _sanitize_graph(evidence.projection(selected, budget))
            elif operation == 'projection-inventory':
                result = evidence.projection(selected, budget, inventory=(offset, limit, []))
                result['report'] = _sanitize_graph(result['report'])
                # Validate typed, size-bounded scalar fields only.
                for row in result['snapshots']:
                    for value in row.values():
                        if isinstance(value, str) and len(value) > 128:
                            raise InspectionLimit('Inventory scalar budget exceeded')
                        if value is not None and type(value) not in {str, int, bool}:
                            raise InspectionLimit('Invalid inventory scalar')
            elif operation == 'fois-storage':
                result = evidence.fois_storage(selected, budget)
            else:
                result = evidence.retention(selected, budget)
            budget.check()
            response = JSONResponse(result, headers=PRIVATE_HEADERS)
            if len(response.body) > MAX_RESPONSE_BYTES:
                raise InspectionLimit('Inspection response budget exceeded')
            return response
        except (InspectionLimit, sqlite3.Error, OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
            raise HTTPException(503, 'Inspection unavailable or budget exceeded', headers=PRIVATE_HEADERS) from None
        finally:
            _DIAGNOSTIC_LOCK.release()

    return router
