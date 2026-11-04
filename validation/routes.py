"""FastAPI/Starlette route validation using stable route capabilities."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True, order=True)
class HttpEndpoint:
    method: str
    path: str


@dataclass(frozen=True)
class RouteValidation:
    endpoints: tuple[HttpEndpoint, ...]
    duplicates: tuple[HttpEndpoint, ...]
    missing: tuple[HttpEndpoint, ...]
    invalid: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not (self.duplicates or self.missing or self.invalid)

    def require_valid(self) -> None:
        if self.valid:
            return
        problems = []
        if self.duplicates:
            problems.append("duplicate endpoints: " + ", ".join(f"{item.method} {item.path}" for item in self.duplicates))
        if self.missing:
            problems.append("missing endpoints: " + ", ".join(f"{item.method} {item.path}" for item in self.missing))
        problems.extend(self.invalid)
        raise AssertionError("; ".join(problems))


def _children(route: Any) -> tuple[Any, ...]:
    """Return nested route objects without depending on concrete router classes."""
    direct = getattr(route, "routes", None)
    if direct is not None:
        try:
            return tuple(direct)
        except TypeError:
            return ()
    original = getattr(route, "original_router", None)
    nested = getattr(original, "routes", None)
    if nested is not None:
        try:
            return tuple(nested)
        except TypeError:
            return ()
    app = getattr(route, "app", None)
    nested = getattr(app, "routes", None)
    if nested is not None:
        try:
            return tuple(nested)
        except TypeError:
            return ()
    return ()


def discover_http_endpoints(routes: Iterable[Any]) -> tuple[HttpEndpoint, ...]:
    """Recursively discover HTTP endpoints and ignore unsupported route containers."""
    discovered: list[HttpEndpoint] = []
    active: set[int] = set()

    def visit(route: Any, prefix: str = "") -> None:
        identity = id(route)
        if identity in active:
            return
        active.add(identity)
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if isinstance(path, str) and methods:
            full_path = prefix + path
            discovered.extend(HttpEndpoint(str(method).upper(), full_path) for method in methods)
        else:
            include_context = getattr(route, "include_context", None)
            include_prefix = getattr(include_context, "prefix", "")
            own_prefix = path if isinstance(path, str) else include_prefix if isinstance(include_prefix, str) else ""
            child_prefix = prefix + own_prefix
            for child in _children(route):
                visit(child, child_prefix)
        active.remove(identity)

    for item in routes:
        visit(item)
    return tuple(sorted(discovered))


def validate_routes(routes: Iterable[Any], required: Iterable[HttpEndpoint] = ()) -> RouteValidation:
    endpoints = discover_http_endpoints(routes)
    counts = Counter(endpoints)
    duplicates = tuple(sorted(endpoint for endpoint, count in counts.items() if count > 1))
    unique = set(endpoints)
    missing = tuple(sorted(set(required) - unique))
    invalid = tuple(
        f"invalid endpoint registration: {endpoint.method} {endpoint.path}"
        for endpoint in endpoints
        if not endpoint.path.startswith("/") or not endpoint.method or endpoint.method != endpoint.method.upper()
    )
    return RouteValidation(endpoints, duplicates, missing, invalid)
