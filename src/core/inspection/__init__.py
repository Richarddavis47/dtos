"""Public contracts for the DTOS AI Inspection System (DINS)."""
from importlib import import_module

# Browser capture needs models/storage only. Importing the package must not
# also retain the server's FOIS/Brain/valuation dependency graph in that worker.
_EXPORT_MODULES = {
    "engine": ("InspectionEngine",),
    "discovery": ("discover_pages", "excluded_current_trade_pages", "uncovered_public_routes", "unsupported_dynamic_patterns"),
    "models": ("INSPECTION_SCHEMA_VERSION", "VIEWPORTS", "PageInspection", "VisualInspection"),
    "storage": ("InspectionArtifactStore",),
    "publication": ("GitHubPublicationResolver",),
    "live": ("LIVE_INSPECTION_SCHEMA_VERSION", "LiveInspection", "PublicSurface", "public_surface_registry"),
}


def __getattr__(name):
    for module, names in _EXPORT_MODULES.items():
        if name in names:
            value = getattr(import_module(f"{__name__}.{module}"), name)
            globals()[name] = value
            return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))

__all__ = [
    "INSPECTION_SCHEMA_VERSION", "VIEWPORTS", "InspectionArtifactStore",
    "InspectionEngine", "PageInspection", "VisualInspection", "discover_pages",
    "excluded_current_trade_pages",
    "uncovered_public_routes", "unsupported_dynamic_patterns", "GitHubPublicationResolver",
    "LIVE_INSPECTION_SCHEMA_VERSION", "LiveInspection", "PublicSurface",
    "public_surface_registry",
]
