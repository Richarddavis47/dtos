"""First-class validation API shared by development and release tooling."""
from src.platform.validation.lifecycle import CleanupResult, TrackedServer, available_port, listening_pids
from src.platform.validation.process_detection import ProcessRecord, genuine_dtos_servers, is_dtos_server
from src.platform.validation.routes import HttpEndpoint, RouteValidation, discover_http_endpoints, validate_routes

__all__ = ["CleanupResult", "HttpEndpoint", "ProcessRecord", "RouteValidation", "TrackedServer", "available_port", "discover_http_endpoints", "genuine_dtos_servers", "is_dtos_server", "listening_pids", "validate_routes"]
