"""DTOS league settings routes."""
from __future__ import annotations

from html import escape
from typing import Any, Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app_metadata import BUILD_NUMBER, VERSION, repository_metadata
from src.core.data_platform import data_platform


EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def create_settings_router(
    *,
    ensure_fresh: EnsureFresh,
    require_data: RequireData,
    page: PageRenderer,
) -> APIRouter:
    """Create the League Settings router using shared app dependencies."""
    router = APIRouter()

    @router.get("/settings", response_class=HTMLResponse)
    async def settings_page() -> HTMLResponse:
        await ensure_fresh()
        data = require_data()
        branch, commit = repository_metadata()
        scoring_rows = "".join(
            f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>"
            for key, value in sorted(data["scoring_settings"].items())
        )
        setting_rows = "".join(
            f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>"
            for key, value in sorted(data["league_settings"].items())
        )
        positions = " ".join(
            f'<span class="pill">{escape(str(position))}</span>'
            for position in data["roster_positions"]
        )
        provider_rows = "".join(
            f"<tr><td>{escape(str(name))}</td><td>{escape(str(row['status'].value))}</td><td>{escape(str(row['licensing_tier'].value))}</td><td>{escape(str(row['freshness']))}</td><td>{escape(str(row['next_refresh'] or 'Not scheduled'))}</td></tr>"
            for name, row in sorted(data_platform.health()["providers"].items())
        )
        body = f"""
<h2>League Configuration</h2>
<div class="grid">
  <div class="card"><h3>Roster Positions</h3><p>{positions}</p></div>
  <div class="card">
    <h3>Front Office</h3>
    <table><tbody>
      <tr><td>DTOS version</td><td>{escape(VERSION)}</td></tr>
      <tr><td>Build</td><td>{BUILD_NUMBER}</td></tr>
      <tr><td>Git branch</td><td>{escape(branch)}</td></tr>
      <tr><td>Latest commit</td><td>{escape(commit)}</td></tr>
    </tbody></table>
  </div>
</div>
<div class="grid">
  <div class="card"><h3>Scoring Settings</h3><table><tbody>{scoring_rows}</tbody></table></div>
  <div class="card"><h3>League Settings</h3><table><tbody>{setting_rows}</tbody></table></div>
</div>
<div class="card"><h3>Provider Health</h3><p class="muted">Provider status and licensing are explicit. Disabled sources do not block DTOS.</p><table><thead><tr><th>Provider</th><th>Status</th><th>Licensing</th><th>Freshness</th><th>Next Refresh</th></tr></thead><tbody>{provider_rows}</tbody></table></div>
"""
        return page("League Settings", body)

    return router
