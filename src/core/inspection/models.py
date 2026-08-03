"""Versioned, presentation-neutral DINS inspection contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

INSPECTION_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class InspectionElement:
    key: str
    title: str
    component_type: str
    data: dict[str, Any]
    status: str = "available"


@dataclass(frozen=True)
class InspectionTable:
    key: str
    title: str
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    status: str = "available"


@dataclass(frozen=True)
class InspectionAction:
    key: str
    label: str
    action: str
    enabled: bool
    placeholder: bool = False


@dataclass(frozen=True)
class InspectionLink:
    label: str
    route: str
    relationship: str


@dataclass(frozen=True)
class PageMetrics:
    section_count: int
    card_count: int
    table_count: int
    chart_count: int
    button_count: int
    navigation_count: int
    link_count: int
    empty_state_count: int
    placeholder_action_count: int
    warning_count: int
    table_row_count: int


@dataclass(frozen=True)
class PageInspection:
    application_version: str
    inspection_schema_version: str
    page_name: str
    route: str
    sections: tuple[InspectionElement, ...]
    cards: tuple[InspectionElement, ...]
    tables: tuple[InspectionTable, ...]
    charts: tuple[InspectionElement, ...]
    buttons: tuple[InspectionAction, ...]
    navigation: tuple[InspectionLink, ...]
    links: tuple[InspectionLink, ...]
    empty_states: tuple[str, ...]
    placeholder_actions: tuple[InspectionAction, ...]
    warnings: tuple[str, ...]
    page_metrics: PageMetrics
    last_updated: str | None
