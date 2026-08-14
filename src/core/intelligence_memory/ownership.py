"""Formal DTOS data-ownership classification."""
from __future__ import annotations


DATA_OWNERSHIP = {
    "provider_facts": {
        "owner": "sleeper_or_external_provider",
        "retention": "disposable_cache",
        "categories": (
            "settings", "scoring", "users", "rosters", "matchups", "standings",
            "playoffs", "drafts", "transactions", "trades", "waivers",
            "traded_picks", "current_status", "current_projections",
        ),
    },
    "dtos_intelligence": {
        "owner": "dtos",
        "retention": "permanent_compact",
        "categories": (
            "intelligence_checkpoints", "fois_scores", "decision_provenance",
            "projection_outcomes", "point_in_time_market_evidence", "pick_lineage",
        ),
    },
    "shared_global": {
        "owner": "provider_or_dtos_model",
        "retention": "shared_cache_or_deduplicated_checkpoint",
        "categories": ("nfl_player_catalog", "nfl_events", "provider_metadata"),
    },
    "system_metadata": {
        "owner": "dtos",
        "retention": "permanent_small",
        "categories": ("league_references", "checksums", "cache_metadata", "model_versions"),
    },
    "legacy_historical_memory": {
        "owner": "mixed",
        "retention": "preserved_pending_reversible_migration",
        "categories": (
            "redundant_provider_records", "read_models", "import_checkpoints",
            "irreplaceable_external_evidence", "quality_metadata",
        ),
    },
}
