"""Validate DTOS route registration and OpenAPI contracts."""
from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from dtos_app import app  # noqa: E402
from validation.routes import HttpEndpoint, validate_routes  # noqa: E402

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
