"""Regression tests for mixed FastAPI and Starlette route collections."""
from __future__ import annotations

import unittest
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, FastAPI, WebSocket
from starlette.routing import Mount, Route, Router, WebSocketRoute

from validation.routes import HttpEndpoint, discover_http_endpoints, validate_routes


async def endpoint(request):
    return None


async def websocket_endpoint(websocket: WebSocket):
    return None


class NoMethods:
    pass


class RouteValidationTests(unittest.TestCase):
    def test_release_route_validation_entry_point_executes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-m", "tools.validation.validate_routes"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Route validation passed", result.stdout)
        self.assertIn("no duplicates", result.stdout)
        self.assertIn("OpenAPI paths", result.stdout)
        source = (root / "tools/validation/validate_routes.py").read_text(encoding="utf-8")
        self.assertNotIn("sys.path", source)

    def test_single_apiroute_is_discovered(self) -> None:
        router = APIRouter(prefix="/single")
        router.add_api_route("/item", endpoint, methods=["POST"])
        endpoints = set(discover_http_endpoints(router.routes))
        self.assertEqual(endpoints, {HttpEndpoint("POST", "/single/item")})

    def test_apiroute_included_and_nested_routers_are_discovered(self) -> None:
        nested = APIRouter()

        @nested.get("/child")
        async def child():
            return {}

        parent = APIRouter(prefix="/parent")
        parent.include_router(nested)
        app = FastAPI()
        app.include_router(parent)
        endpoints = set(discover_http_endpoints(app.routes))
        self.assertIn(HttpEndpoint("GET", "/parent/child"), endpoints)

    def test_deeply_nested_prefixes_propagate_to_canonical_path(self) -> None:
        leaf = APIRouter()
        leaf.add_api_route("/leaf", endpoint, methods=["POST"])
        middle = APIRouter(prefix="/middle")
        middle.include_router(leaf, prefix="/inner")
        outer = APIRouter(prefix="/outer")
        outer.include_router(middle)
        app = FastAPI()
        app.include_router(outer, prefix="/api")
        endpoints = set(discover_http_endpoints(app.routes))
        self.assertIn(HttpEndpoint("POST", "/api/outer/middle/inner/leaf"), endpoints)

    def test_mounts_are_traversed_and_websockets_are_ignored(self) -> None:
        mounted = Router(routes=[Route("/asset", endpoint, methods=["GET"]), WebSocketRoute("/socket", websocket_endpoint)])
        routes = [Mount("/static", app=mounted), NoMethods()]
        endpoints = set(discover_http_endpoints(routes))
        self.assertIn(HttpEndpoint("GET", "/static/asset"), endpoints)
        self.assertNotIn(HttpEndpoint("GET", "/static/socket"), endpoints)

    def test_objects_without_methods_are_ignored(self) -> None:
        self.assertEqual(discover_http_endpoints([NoMethods(), object()]), ())

    def test_automatic_head_and_mixed_methods_match_framework_table(self) -> None:
        endpoints = set(discover_http_endpoints([Route("/mixed", endpoint, methods=["GET", "POST"])]))
        self.assertEqual(endpoints, {HttpEndpoint("GET", "/mixed"), HttpEndpoint("HEAD", "/mixed"), HttpEndpoint("POST", "/mixed")})

    def test_duplicate_get_head_and_post_remain_independent_failures(self) -> None:
        routes = [Route("/same", endpoint, methods=["GET", "POST"]), Route("/same", endpoint, methods=["GET", "POST"])]
        result = validate_routes(routes, (HttpEndpoint("POST", "/required"),))
        self.assertFalse(result.valid)
        self.assertEqual(result.duplicates, (HttpEndpoint("GET", "/same"), HttpEndpoint("HEAD", "/same"), HttpEndpoint("POST", "/same")))
        self.assertEqual(result.missing, (HttpEndpoint("POST", "/required"),))
        with self.assertRaises(AssertionError):
            result.require_valid()

    def test_duplicate_routes_inside_included_router_are_detected(self) -> None:
        nested = APIRouter()
        nested.add_api_route("/same", endpoint, methods=["POST"])
        nested.add_api_route("/same", endpoint, methods=["POST"])
        app = FastAPI()
        app.include_router(nested, prefix="/nested")
        result = validate_routes(app.routes)
        self.assertEqual(result.duplicates, (HttpEndpoint("POST", "/nested/same"),))


if __name__ == "__main__":
    unittest.main()
