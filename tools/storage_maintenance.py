"""Temporary maintenance ASGI entrypoint; deliberately imports no DTOS code.

An operator must explicitly select this entrypoint and wait for the former
application instance and its children to exit before moving readiness files.
It does not stop processes, migrate data, expose a shell, or read databases.
Restore the normal entrypoint only after storage and readiness verification.
Health endpoints report process liveness, NOT application readiness.
"""


async def app(scope, receive, send):
    if scope['type'] == 'lifespan':
        while True:
            event = await receive()
            if event['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif event['type'] == 'lifespan.shutdown':
                await send({'type': 'lifespan.shutdown.complete'})
                return
    elif scope['type'] == 'http':
        live = scope.get('path') in ('/health', '/healthz')
        body = b'{"status":"maintenance","application_ready":false}'
        headers = [(b'content-type', b'application/json'),
                   (b'cache-control', b'no-store'),
                   (b'content-length', str(len(body)).encode())]
        if not live:
            headers.append((b'retry-after', b'60'))
        await send({'type': 'http.response.start', 'status': 200 if live else 503,
                    'headers': headers})
        await send({'type': 'http.response.body',
                    'body': b'' if scope.get('method') == 'HEAD' else body})
    elif scope['type'] == 'websocket':
        await send({'type': 'websocket.close', 'code': 1013})
