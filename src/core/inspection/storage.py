"""Versioned, public-safe storage for pre-generated DINS artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app_metadata import BUILD_NUMBER, VERSION
from src.core.inspection.models import INSPECTION_SCHEMA_VERSION


class InspectionArtifactStore:
    def __init__(self, root: Path, public_base_url: str = "") -> None:
        self.root = root
        self.public_base_url = public_base_url.rstrip("/")

    @property
    def namespace(self) -> str:
        return f"v{VERSION}-b{BUILD_NUMBER}-s{INSPECTION_SCHEMA_VERSION}"

    @property
    def current_root(self) -> Path:
        return self.root / self.namespace

    def artifact_url(self, relative: str) -> str:
        safe = relative.replace("\\", "/").lstrip("/")
        return f"{self.public_base_url}/inspection-artifacts/{self.namespace}/{safe}"

    def read_json(self, relative: str) -> dict[str, Any] | None:
        path = (self.current_root / relative).resolve()
        if self.current_root.resolve() not in path.parents:
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def manifest(self) -> dict[str, Any] | None:
        return self.read_json("manifest.json")

    def page(self, page_id: str, viewport: str) -> dict[str, Any] | None:
        return self.read_json(f"pages/{page_id}/{viewport}.json")

    def releases(self) -> tuple[dict[str, Any], ...]:
        rows = []
        if not self.root.exists():
            return ()
        for path in sorted(self.root.glob("*/manifest.json"), reverse=True):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(row, dict):
                rows.append(row)
        return tuple(rows)
