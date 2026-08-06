"""Strict durable-storage boundary for Historical League Memory."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class HistoricalStorageStatus:
    required: bool
    healthy: bool
    reason: str
    root: str
    database: str
    mounted: bool
    writable: bool
    contained: bool

    def public(self) -> dict[str, object]:
        """Return operational state without disclosing host-specific paths."""
        result = asdict(self)
        result["root"] = "configured durable storage" if self.required else "local storage"
        result["database"] = "historical database"
        return result


def validate_historical_storage(
    *, database: Path, root: Path, required: bool,
) -> HistoricalStorageStatus:
    """Validate containment, mount identity, and write access without fallback."""
    resolved_database = database.expanduser().resolve(strict=False)
    resolved_root = root.expanduser().resolve(strict=False)
    contained = resolved_database != resolved_root and resolved_database.is_relative_to(
        resolved_root
    )

    if not required:
        return HistoricalStorageStatus(
            required=False, healthy=True,
            reason="Durable historical storage is optional in this environment.",
            root=str(resolved_root), database=str(resolved_database),
            mounted=os.path.ismount(resolved_root), writable=True,
            contained=contained,
        )

    if not contained:
        return HistoricalStorageStatus(
            required=True, healthy=False,
            reason="Historical database is not contained beneath the required durable-storage root.",
            root=str(resolved_root), database=str(resolved_database),
            mounted=False, writable=False, contained=False,
        )
    if not resolved_root.is_dir():
        return HistoricalStorageStatus(
            required=True, healthy=False,
            reason="Required durable-storage mount is absent.",
            root=str(resolved_root), database=str(resolved_database),
            mounted=False, writable=False, contained=True,
        )

    mounted = os.path.ismount(resolved_root)
    if not mounted:
        return HistoricalStorageStatus(
            required=True, healthy=False,
            reason="Configured historical storage exists but is not a mounted filesystem.",
            root=str(resolved_root), database=str(resolved_database),
            mounted=False, writable=False, contained=True,
        )

    probe = resolved_root / f".dtos-write-probe-{uuid4().hex}"
    try:
        descriptor = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(descriptor, b"dtos")
        os.fsync(descriptor)
        os.close(descriptor)
        probe.unlink()
    except OSError as exc:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        return HistoricalStorageStatus(
            required=True, healthy=False,
            reason=f"Required durable storage is not writable: {type(exc).__name__}.",
            root=str(resolved_root), database=str(resolved_database),
            mounted=True, writable=False, contained=True,
        )

    return HistoricalStorageStatus(
        required=True, healthy=True,
        reason="Durable historical storage is mounted and writable.",
        root=str(resolved_root), database=str(resolved_database),
        mounted=True, writable=True, contained=True,
    )
