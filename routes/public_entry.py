"""Source-independent public presentation. No league or account data is consumed."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from src.ui.public_welcome import render_welcome


PUBLIC_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
}


def create_public_entry_router() -> APIRouter:
    router = APIRouter(tags=["public-entry"])
    # One small immutable artifact, prepared before request handling. No account,
    # Market, runtime acquisition or fixture file access on an anonymous read.
    document = render_welcome()

    @router.get("/welcome", response_class=HTMLResponse)
    @router.head("/welcome", response_class=HTMLResponse, include_in_schema=False)
    async def welcome() -> HTMLResponse:
        return HTMLResponse(document, headers=PUBLIC_HEADERS)

    @router.api_route("/welcome/", methods=["GET", "HEAD"], include_in_schema=False)
    async def canonical_welcome() -> RedirectResponse:
        return RedirectResponse("/welcome", status_code=303, headers=PUBLIC_HEADERS)

    return router
