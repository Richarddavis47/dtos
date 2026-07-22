"""Compatibility import for the first-class validation lifecycle API."""
from src.platform.validation.lifecycle import CleanupResult, TrackedServer, available_port, listening_pids

__all__ = ["CleanupResult", "TrackedServer", "available_port", "listening_pids"]
