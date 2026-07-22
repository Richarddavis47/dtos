"""First-class validation API shared by development and release tooling."""
from src.platform.validation.lifecycle import CleanupResult, TrackedServer, available_port, listening_pids
from src.platform.validation.process_detection import ProcessRecord, genuine_dtos_servers, is_dtos_server
from src.platform.validation.release import REQUIRED_DOCUMENTS, ValidationResult, ValidationStep, architecture_violations, default_steps, run_release_validation, validate_documentation
from src.platform.validation.routes import HttpEndpoint, RouteValidation, discover_http_endpoints, validate_routes

__all__ = ["CleanupResult", "HttpEndpoint", "ProcessRecord", "REQUIRED_DOCUMENTS", "RouteValidation", "TrackedServer", "ValidationResult", "ValidationStep", "architecture_violations", "available_port", "default_steps", "discover_http_endpoints", "genuine_dtos_servers", "is_dtos_server", "listening_pids", "run_release_validation", "validate_documentation", "validate_routes"]
