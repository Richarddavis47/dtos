"""Validate DTOS route registration and OpenAPI contracts."""
from __future__ import annotations

from dtos_app import app
from app_metadata import VERSION
from src.core.inspection import unsupported_dynamic_patterns
from src.platform.validation.routes import HttpEndpoint, validate_routes

REQUIRED_GET_PATHS = (
    "/",
    "/market",
    "/commissioner",
    "/teams",
    "/front-offices",
    "/api/front-offices",
    "/trades",
    "/api/trades",
    "/matchups",
    "/transactions",
    "/picks",
    "/settings",
    "/api/status",
    "/api/market",
    "/api/market/assets",
    "/api/market/search",
    "/api/market/trending",
    "/api/market/health",
    "/api/platform/health",
    "/api/intelligence",
    "/api/league",
    "/api/players",
    "/api/history/assets",
    "/api/history/coverage",
    "/api/history/transactions",
    "/api/search",
    "/search",
    "/api/inspect",
    "/api/inspect/site-map",
    "/api/inspect/health",
    "/api/inspect/live",
    "/api/inspect/live/health",
    "/api/inspect/live/visual",
    "/api/inspect/live/visual/health",
    "/api/inspect/schema",
    "/api/inspect/market",
    "/api/inspect/visual/pages",
    "/api/inspect/releases/current",
)


def main() -> int:
    required = tuple(HttpEndpoint("GET", path) for path in REQUIRED_GET_PATHS)
    result = validate_routes(app.routes, required)
    result.require_valid()

    schema = app.openapi()
    documented = schema.get("paths") or {}
    missing_openapi = sorted(path for path in REQUIRED_GET_PATHS if path not in documented)
    if missing_openapi:
        raise AssertionError("missing OpenAPI paths: " + ", ".join(missing_openapi))
    unsupported = unsupported_dynamic_patterns(app.routes)
    if unsupported:
        raise AssertionError("public HTML routes lack DINS fixture metadata: " + ", ".join(unsupported))
    if schema.get("info", {}).get("version") != VERSION:
        raise AssertionError("OpenAPI and centralized application versions differ.")

    print(
        f"Route validation passed: {len(result.endpoints)} method registrations, "
        f"no duplicates, {len(documented)} OpenAPI paths, all required endpoints present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
