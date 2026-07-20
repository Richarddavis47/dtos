"""DTOS transaction history routes."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from typing import Any, Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def create_transactions_router(
    *,
    ensure_fresh: EnsureFresh,
    require_data: RequireData,
    page: PageRenderer,
) -> APIRouter:
    """Create the Transactions router using shared app dependencies."""
    router = APIRouter()

    @router.get("/transactions", response_class=HTMLResponse)
    async def transactions_page() -> HTMLResponse:
        await ensure_fresh()
        txs = require_data()["transactions"]
        cards: list[str] = []

        for tx in txs:
            created = tx.get("created")
            date = (
                datetime.fromtimestamp(created / 1000, tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M UTC"
                )
                if created
                else "—"
            )
            tx_type = str(tx.get("type") or "Transaction").replace("_", " ").title()
            status = str(tx.get("status") or "")
            payload = json.dumps(tx, indent=2)[:5000]
            cards.append(
                f'<div class="card"><h3>{escape(tx_type)}</h3>'
                f'<div class="muted">{escape(date)} · {escape(status)}</div>'
                f'<pre>{escape(payload)}</pre></div>'
            )

        body = '<h2>Latest Week Transactions</h2><div class="grid">' + "".join(cards) + "</div>"
        return page("Transactions", body)

    return router
