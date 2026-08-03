"""Versioned provider registry and compliance classifications."""
from __future__ import annotations

import os
from copy import deepcopy
from typing import Any


PROVIDER_REGISTRY_VERSION = "1.0"
EVIDENCE_CONTRACT_VERSION = "1.0"

_REGISTRY: tuple[dict[str, Any], ...] = (
    {"provider_id": "fantasycalc", "provider_name": "FantasyCalc", "evidence_category": "observed_transactions", "evidence_family": "fantasycalc_observed_market", "official_source_url": "https://fantasycalc.com/", "acquisition_method": "Approved public JSON endpoint", "authentication": "none", "compliance_status": "approved_enabled", "redistribution": "derived_and_attributed", "production_eligible": True, "formats": ["superflex", "1QB", "PPR"], "league_types": ["dynasty"], "scoring_formats": ["PPR"], "asset_types": ["player"], "refresh_schedule": "24h", "expected_freshness_hours": 36, "normalization_method": "provider-distribution percentile", "identity_matching_method": "Sleeper ID", "default_reliability_prior": 65},
    {"provider_id": "dynastyprocess", "provider_name": "DynastyProcess", "evidence_category": "market_rankings", "evidence_family": "fantasypros_derived_market", "official_source_url": "https://github.com/dynastyprocess/data", "acquisition_method": "Official open-data CSV", "authentication": "none", "compliance_status": "approved_enabled", "redistribution": "open_data_attributed", "production_eligible": True, "formats": ["superflex", "1QB"], "league_types": ["dynasty"], "scoring_formats": ["PPR"], "asset_types": ["player", "pick"], "refresh_schedule": "24h", "expected_freshness_hours": 48, "normalization_method": "provider-distribution percentile", "identity_matching_method": "FantasyPros-to-Sleeper open ID map", "default_reliability_prior": 60, "depends_on": ["fantasypros"]},
    {"provider_id": "fantasypros", "provider_name": "FantasyPros", "evidence_category": "expert_consensus", "evidence_family": "fantasypros_derived_market", "official_source_url": "https://api.fantasypros.com/", "acquisition_method": "Official authenticated API", "authentication": "FANTASYPROS_API_KEY", "compliance_status": "approved_credentials_required", "redistribution": "license_dependent", "production_eligible": False, "formats": ["licensed configuration"], "league_types": ["dynasty", "redraft"], "scoring_formats": ["licensed configuration"], "asset_types": ["player"], "refresh_schedule": "daily when licensed", "expected_freshness_hours": 36, "normalization_method": "rank percentile and tier dispersion", "identity_matching_method": "FantasyPros ID map", "default_reliability_prior": 50},
    {"provider_id": "keeptradecut", "provider_name": "KeepTradeCut", "evidence_category": "market_rankings", "evidence_family": "ktc_crowd_market", "official_source_url": "https://keeptradecut.com/", "acquisition_method": "No approved machine interface", "authentication": "none", "compliance_status": "unsupported_no_public_interface", "redistribution": "not_approved", "production_eligible": False, "formats": [], "league_types": ["dynasty"], "scoring_formats": [], "asset_types": ["player", "pick"], "refresh_schedule": "disabled", "expected_freshness_hours": None, "normalization_method": "not configured", "identity_matching_method": "not configured", "default_reliability_prior": 0},
    {"provider_id": "sleeper_trades", "provider_name": "Sleeper League Trade Market", "evidence_category": "observed_transactions", "evidence_family": "sleeper_league_observed", "official_source_url": "https://docs.sleeper.com/", "acquisition_method": "Official Sleeper API and retained historical memory", "authentication": "none", "compliance_status": "approved_enabled", "redistribution": "aggregate_only", "production_eligible": True, "formats": ["active league settings"], "league_types": ["dynasty"], "scoring_formats": ["active league settings"], "asset_types": ["player", "pick", "package"], "refresh_schedule": "with Sleeper sync", "expected_freshness_hours": 2, "normalization_method": "quality-weighted package evidence", "identity_matching_method": "Sleeper canonical IDs", "default_reliability_prior": 60},
    {"provider_id": "league_local", "provider_name": "DTOS League-Local Market", "evidence_category": "league_local_evidence", "evidence_family": "sleeper_league_observed", "official_source_url": "https://docs.sleeper.com/", "acquisition_method": "Derived from active-league cached actions", "authentication": "none", "compliance_status": "approved_enabled", "redistribution": "private_aggregate_only", "production_eligible": True, "formats": ["active league settings"], "league_types": ["dynasty"], "scoring_formats": ["active league settings"], "asset_types": ["player", "pick", "package"], "refresh_schedule": "with Sleeper sync", "expected_freshness_hours": 2, "normalization_method": "league-isolated demand adjustment", "identity_matching_method": "Sleeper canonical IDs", "default_reliability_prior": 55, "depends_on": ["sleeper_trades"]},
    {"provider_id": "nflverse", "provider_name": "nflverse", "evidence_category": "performance_and_projections", "evidence_family": "nflverse_open_performance", "official_source_url": "https://github.com/nflverse", "acquisition_method": "Approved open releases through Historical Memory", "authentication": "none", "compliance_status": "approved_enabled", "redistribution": "open_data_attributed", "production_eligible": True, "formats": ["NFL statistics"], "league_types": ["all"], "scoring_formats": ["raw performance"], "asset_types": ["player", "identity"], "refresh_schedule": "published release cadence", "expected_freshness_hours": 168, "normalization_method": "performance evidence only", "identity_matching_method": "GSIS and cross-provider IDs", "default_reliability_prior": 70},
    {"provider_id": "dtos_historical", "provider_name": "DTOS Historical Model", "evidence_category": "dtos_derived", "evidence_family": "dtos_intrinsic", "official_source_url": "https://github.com/Richarddavis47/dtos", "acquisition_method": "Internal deterministic model", "authentication": "none", "compliance_status": "approved_enabled", "redistribution": "derived", "production_eligible": True, "formats": ["league-aware"], "league_types": ["dynasty"], "scoring_formats": ["league-aware"], "asset_types": ["player", "pick"], "refresh_schedule": "with model generation", "expected_freshness_hours": 24, "normalization_method": "independent intrinsic model", "identity_matching_method": "Canonical Asset Universe", "default_reliability_prior": 60},
    {"provider_id": "mfl_trades", "provider_name": "MFL Transaction History", "evidence_category": "observed_transactions", "evidence_family": "mfl_observed", "official_source_url": "https://api.myfantasyleague.com/", "acquisition_method": "Future approved adapter", "authentication": "optional league credentials", "compliance_status": "development_only", "redistribution": "undetermined", "production_eligible": False, "formats": [], "league_types": ["dynasty"], "scoring_formats": [], "asset_types": ["player", "pick"], "refresh_schedule": "disabled", "expected_freshness_hours": None, "normalization_method": "not configured", "identity_matching_method": "MFL ID", "default_reliability_prior": 40},
    {"provider_id": "fleaflicker_trades", "provider_name": "Fleaflicker Transaction History", "evidence_category": "observed_transactions", "evidence_family": "fleaflicker_observed", "official_source_url": "https://www.fleaflicker.com/", "acquisition_method": "Future approved adapter", "authentication": "undetermined", "compliance_status": "development_only", "redistribution": "undetermined", "production_eligible": False, "formats": [], "league_types": ["dynasty"], "scoring_formats": [], "asset_types": ["player", "pick"], "refresh_schedule": "disabled", "expected_freshness_hours": None, "normalization_method": "not configured", "identity_matching_method": "Fleaflicker ID", "default_reliability_prior": 40},
)


def provider_registry(runtime_status: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    statuses = runtime_status or {}
    rows = deepcopy(list(_REGISTRY))
    for row in rows:
        compliance = {
            "fantasycalc": ("Attributed non-commercial use; written permission required for commercial use.", "Daily caching is encouraged by provider terms."),
            "dynastyprocess": ("GPL-3.0 open-data repository; preserve source and attribution.", "Weekly publication cadence."),
            "fantasypros": ("API key and license tier required; commercial redistribution requires a separate agreement.", "Provider-assigned authenticated API limits."),
            "keeptradecut": ("No approved public interface or redistribution permission.", "Not applicable; disabled."),
            "sleeper_trades": ("Official free read-only API; provider terms and attribution apply.", "Stay below 1,000 API calls per minute."),
            "league_local": ("Private active-league derivation; aggregates only.", "Uses existing Sleeper synchronization."),
            "nflverse": ("CC-BY-4.0 releases; dataset-specific attribution applies.", "Published release cadence."),
            "dtos_historical": ("Internal deterministic evidence.", "Local generation only."),
        }.get(row["provider_id"], ("Access and redistribution not yet approved.", "Disabled until reviewed."))
        row.setdefault("license_or_usage_right_status", compliance[0])
        row.setdefault("rate_limits", compliance[1])
        row.setdefault("historical_coverage", "Provider-defined; measured at ingestion")
        row.setdefault("pick_coverage", "supported" if "pick" in row["asset_types"] else "not supplied")
        runtime = statuses.get(row["provider_name"]) or statuses.get(row["provider_id"]) or {}
        credentials_configured = bool(os.getenv(str(row["authentication"]))) if row["authentication"] not in {"none", "optional league credentials", "undetermined"} else False
        row.update({
            "credentials_configured": credentials_configured,
            "current_availability": runtime.get("status") or ("waiting" if row["compliance_status"] == "approved_enabled" else "disabled"),
            "last_successful_refresh": runtime.get("last_refresh") if runtime.get("status") == "healthy" else None,
            "last_attempted_refresh": runtime.get("last_refresh"),
            "record_count": int(runtime.get("records_retrieved") or 0),
            "coverage_percentage": 0.0,
            "error_state": runtime.get("reason"),
            "status_explanation": runtime.get("reason") or _explanation(row),
        })
    return rows


def _explanation(row: dict[str, Any]) -> str:
    status = row["compliance_status"]
    if row["provider_id"] == "keeptradecut":
        return "Unavailable — no approved provider integration. DTOS will not scrape or call undocumented endpoints."
    if status == "approved_credentials_required":
        return "Official credentials and suitable production/redistribution rights are required; no secret is configured or exposed."
    if status == "development_only":
        return "Adapter extension point only; production ingestion is disabled until access, terms, identity, and redistribution are approved."
    return "Approved evidence source; runtime health and coverage determine its effective weight."
