"""Render-compatible DTOS entry point.

The application implementation now lives in ``dtos_app.py`` so future
modules can be migrated into ``routes/`` and ``services/`` without changing
Render's existing ``uvicorn main:app`` start command.
"""
from dtos_app import app

__all__ = ["app"]
