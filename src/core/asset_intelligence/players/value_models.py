"""Transparent player value calculations."""
from __future__ import annotations

from src.core.asset_intelligence.models import AssetContext, AssetEvaluation, Evidence, PlayerProfile



def canonical_evidence(profile: PlayerProfile, context: AssetContext | None) -> tuple[Evidence, ...]:
    """Prepared facts are not inferred from placeholder model values."""
    rows = []
    if context is not None and context.canonical_production is not None:
        from src.core.player_value_projection.canonical_production import prepared_production_context
        production = prepared_production_context(context.canonical_production,
            league_id=context.league_id, player_id=profile.player_id)
        for label in ("Season Average", "Previous Season Average"):
            window = next((row for row in production.windows if row.label == label), None)
            value = window.fantasy_points if window is not None else None
            rows.append(Evidence(label, str(value) if value is not None else "Unavailable", 0,
                "Canonical NFL game evidence scored under the selected league rules; previous seasons are not current production.",
                production.source, value is not None))
        window = next((row for row in production.windows if row.label == "Season Average"), None)
        for label, value in (("Targets per game", window.targets if window else None),
                             ("Carries per game", window.carries if window else None)):
            rows.append(Evidence(label, str(value) if value is not None else "Unavailable", 0,
                "Derived from the same canonical production records; missing usage is not zero.",
                production.source, value is not None))
    else:
        rows.append(Evidence("Canonical production", "Not prepared", 0,
            "Canonical production has not been prepared for this context.", "Canonical evidence", False))
    snapshot = context.canonical_projection if context is not None else None
    projection = None
    if snapshot:
        if str(snapshot.get("league_id") or "") != context.league_id:
            raise ValueError("Canonical projection belongs to another league.")
        projection = (snapshot.get("players") or {}).get(profile.player_id)
    points = projection.get("weekly_projected_points") if projection is not None and snapshot.get("week") is not None and projection.get("week") == snapshot.get("week") else None
    rows.append(Evidence("Canonical weekly projection", str(points) if points is not None else "Unavailable", 0,
        "Published Sleeper projection; not an actual NFL result or a dynasty value.", "Sleeper canonical projection", points is not None))
    return tuple(rows)


def dynasty_value(profile: PlayerProfile, context: AssetContext) -> AssetEvaluation:
    return AssetEvaluation("Intrinsic dynasty utility", None, 0,
        "Long-term scalar unavailable; demonstrated quality, opportunity and longevity remain separate.",
        canonical_evidence(profile, context),
        ("Age, team status and league format alone do not establish a dynasty price.",))


def redraft_value(profile: PlayerProfile, context: AssetContext | None = None) -> AssetEvaluation:
    return AssetEvaluation("Season utility", None, 0,
        "Weekly evidence is disclosed at its actual horizon, not converted into a season-value score.",
        canonical_evidence(profile, context),
        ("No annualization or availability-based score substitutes for canonical weekly projection.",))


def market_value(dynasty: AssetEvaluation) -> AssetEvaluation:
    return AssetEvaluation("Market price", None, 0, "External Market evidence must be supplied by the active consensus adapter.",
        (), ("Missing external price is unavailable, not a neutral baseline.",), scale_maximum=1000)


def team_fit(profile: PlayerProfile, context: AssetContext, dynasty: AssetEvaluation, redraft: AssetEvaluation) -> AssetEvaluation:
    return AssetEvaluation("Team-specific fit", None, 0,
        "A validated fit aggregate is unavailable; roster context does not manufacture a player value.",
        (Evidence("Selected franchise", str(context.active_front_office_id), 0,
            "Fit is scoped to the selected league and franchise.", "Canonical context"),),
        ("Price, weekly points and production quality are not interchangeable fit scores.",))
