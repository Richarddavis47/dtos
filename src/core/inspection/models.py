"""Versioned, presentation-neutral DINS inspection contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

INSPECTION_SCHEMA_VERSION = "2.0"


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


@dataclass(frozen=True)
class Viewport:
    name: str
    width: int
    height: int
    device_scale_factor: int = 1


VIEWPORTS = (
    Viewport("desktop", 1440, 1200),
    Viewport("tablet", 1024, 1366),
    Viewport("mobile", 390, 844),
)


@dataclass(frozen=True)
class DiscoveredPage:
    page_id: str
    page_name: str
    route: str
    source_route: str
    kind: str
    state: str
    inspection_mode: str
    excluded: bool = False
    exclusion_reason: str | None = None
    exclusion_code: str | None = None


@dataclass(frozen=True)
class ArtifactUrls:
    viewport_screenshot: str
    full_page_screenshot: str
    dom_snapshot: str
    accessibility_snapshot: str


@dataclass(frozen=True)
class VisualInspection:
    application_version: str
    application_build: int
    inspection_schema_version: str
    page_id: str
    page_name: str
    route: str
    canonical_url: str
    league_id: str | None
    viewport: Viewport
    artifact_urls: ArtifactUrls
    page_state: dict[str, Any]
    sections: tuple[dict[str, Any], ...]
    cards: tuple[dict[str, Any], ...]
    tables: tuple[dict[str, Any], ...]
    charts: tuple[dict[str, Any], ...]
    buttons: tuple[dict[str, Any], ...]
    links: tuple[dict[str, Any], ...]
    navigation: tuple[dict[str, Any], ...]
    forms: tuple[dict[str, Any], ...]
    expandable_regions: tuple[dict[str, Any], ...]
    empty_states: tuple[dict[str, Any], ...]
    loading_states: tuple[dict[str, Any], ...]
    error_states: tuple[dict[str, Any], ...]
    placeholder_actions: tuple[dict[str, Any], ...]
    disabled_actions: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    accessibility: dict[str, Any]
    geometry: dict[str, Any]
    styles: dict[str, Any]
    performance: dict[str, Any]
    network: dict[str, Any]
    interactions: tuple[dict[str, Any], ...]
    regressions: tuple[dict[str, Any], ...]
    metrics: dict[str, Any]


@dataclass(frozen=True)
class ReleaseManifest:
    version: str
    build: int
    commit_sha: str
    deployed_at: str | None
    generated_at: str | None
    inspection_schema_version: str
    status: str
    page_inventory: tuple[dict[str, Any], ...]
    pages_added: tuple[str, ...]
    pages_removed: tuple[str, ...]
    pages_changed: tuple[str, ...]
    semantic_contract_changes: tuple[str, ...]
    screenshot_artifact_urls: tuple[str, ...]
    visual_difference_results: tuple[dict[str, Any], ...]
    interaction_failures: tuple[dict[str, Any], ...]
    accessibility_regressions: tuple[dict[str, Any], ...]
    console_errors: tuple[dict[str, Any], ...]
    failed_network_requests: tuple[dict[str, Any], ...]
    stale_version_mismatches: tuple[str, ...]
    validation_outcome: str
