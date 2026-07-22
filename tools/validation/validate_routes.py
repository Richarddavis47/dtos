"""Validate DTOS route registration and OpenAPI contracts."""
from __future__ import annotations

from dtos_app import app
from src.platform.validation.routes import HttpEndpoint, validate_routes

REQUIRED_GET_PATHS = (
    "/",
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
    "/api/platform/health",
    "/api/intelligence",
    "/api/league",
    "/api/players",
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

    print(
        f"Route validation passed: {len(result.endpoints)} method registrations, "
        f"no duplicates, {len(documented)} OpenAPI paths, all required endpoints present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
