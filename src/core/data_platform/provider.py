"""Provider SDK and declarative provider adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.core.data_platform.models import DataEnvelope, ProviderMetadata


class DataProvider(ABC):
    """Public provider SDK. Adapters return standardized envelopes only."""

    metadata: ProviderMetadata

    @abstractmethod
    def fetch(self, key: str, context: dict[str, Any]) -> DataEnvelope:
        """Fetch one data key without leaking provider-specific contracts."""


class UnavailableProvider(DataProvider):
    def __init__(self, metadata: ProviderMetadata, reason: str) -> None:
        self.metadata = metadata
        self.reason = reason

    def fetch(self, key: str, context: dict[str, Any]) -> DataEnvelope:
        raise RuntimeError(self.reason)
