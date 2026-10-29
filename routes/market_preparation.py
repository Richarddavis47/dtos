"""Cheap account-bound readiness observation; no analytics acquisition."""
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from services.contextual_navigation import navigation_context
from services.market_preparation import presentation


def create_market_preparation_router(*, observer):
    router = APIRouter(tags=['asset-market'])

    @router.get('/static/js/market_preparation.js', include_in_schema=False)
    async def script():
        return Response(
            (Path(__file__).resolve().parents[1] / 'static/js/market_preparation.js').read_text(encoding='utf-8'),
            media_type='text/javascript', headers={'Cache-Control': 'no-cache'},
        )

    @router.get('/api/account/market-preparation')
    async def status():
        context = navigation_context()
        return JSONResponse(
            dict(scope=context['scope'], **presentation(observer())) if context else {'status': 'authentication_required'},
            status_code=200 if context else 401,
            headers={'Cache-Control': 'no-store, private', 'Vary': 'Cookie'},
        )

    return router
