"""Shared inspection credential and fail-closed operational ASGI boundary."""
from __future__ import annotations

import hmac
import os

from starlette.responses import JSONResponse

PREFIX = '/api/inspect/operations'
PRIVATE_HEADERS = {'Cache-Control': 'no-store, private', 'Vary': 'X-DTOS-Inspection-Auth',
                   'X-Content-Type-Options': 'nosniff'}
OPERATIONS = frozenset({'storage', 'projection-reachability', 'projection-inventory',
                        'fois-storage', 'retention', 'identity'})


def operations_path(path):
    return path == PREFIX or path.startswith(PREFIX + '/')


def inspection_authorized(scope):
    expected = os.getenv('DTOS_INSPECTION_AUTH_TOKEN', '').encode('utf-8')
    values = [value for key, value in scope.get('headers', ())
              if key.lower() == b'x-dtos-inspection-auth']
    # Exact opaque token, no Bearer parsing, trimming, query or cookie fallback.
    return bool(expected and len(values) == 1 and 0 < len(values[0]) <= 4096
                and all(33 <= byte <= 126 for byte in expected + values[0])
                and hmac.compare_digest(expected, values[0]))


class OperationalInspectionBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not operations_path(scope.get('path', '')):
            await self.app(scope, receive, send)
            return
        status, detail = None, None
        if not inspection_authorized(scope):
            status, detail = 401, 'Inspection authorization required'
        elif scope['method'] != 'GET':
            status, detail = 405, 'Read-only inspection requires GET'
        elif len(scope.get('query_string', b'')) > 128:
            status, detail = 400, 'Unsupported inspection parameters'
        elif scope.get('path', '').removeprefix(PREFIX + '/') not in OPERATIONS and scope.get('path') != PREFIX:
            status, detail = 404, 'Unsupported inspection operation'
        if status:
            await JSONResponse({'detail': detail}, status_code=status, headers=PRIVATE_HEADERS)(scope, receive, send)
            return

        async def private_send(message):
            if message['type'] == 'http.response.start':
                headers = [(k, v) for k, v in message.get('headers', ())
                           if k.lower() not in {name.lower().encode() for name in PRIVATE_HEADERS}]
                headers.extend((k.lower().encode(), v.encode()) for k, v in PRIVATE_HEADERS.items())
                message = {**message, 'headers': headers}
            await send(message)
        await self.app(scope, receive, private_send)
