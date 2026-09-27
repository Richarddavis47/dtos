"""Canonical forward-production intelligence."""

__all__ = ["projection_service"]


def __getattr__(name):
    # Codec/retention tooling must not initialize the configured application
    # database merely by importing this package. Preserve the public service
    # export, initializing it only when a consumer explicitly requests it.
    if name == 'projection_service':
        from src.core.projection_intelligence.service import projection_service
        return projection_service
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
