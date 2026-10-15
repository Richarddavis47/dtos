"""Bounded presentation over prepared diagnostic facts; no solving or source reads."""

from datetime import datetime, timezone
from html import escape
import json

from src.core.projection_intelligence.sleeper_provider import source_update_time


def source_presentation(evidence, identity=None, *, now=None):
    """Keep complete original clocks separate from the short, qualified range."""
    from src.core.intelligence.roster_diagnostics import _now

    now = now or _now()
    original = list(
        dict.fromkeys(str(t) for t in evidence.get("source_observations") or [])
    )
    valid, unknown = [], 0
    for stamp in original:
        normalized = source_update_time(stamp)
        parsed = datetime.fromisoformat(normalized) if normalized else None
        if parsed is None or parsed > now:
            unknown += 1
        else:
            valid.append(parsed)
    states = ", ".join(evidence.get("projection_freshness") or ["Unavailable"])
    parts = [
        f"Projection source observation: {states}",
        f"{len(valid)} distinct source observations",
    ]
    if valid:

        def label(value):
            return value.astimezone(timezone.utc).strftime("%b %d, %Y %H:%M UTC")

        parts.append(
            "Observed " + label(valid[0])
            if len(valid) == 1
            else "Earliest " + label(min(valid)) + "; latest " + label(max(valid))
        )
    if unknown or not original:
        parts.append(
            "Unknown, invalid or future source clocks; provenance is incomplete"
        )
    if evidence.get("refresh", {}).get("retained_publication"):
        parts.append(
            "Using retained projection evidence; latest refresh did not complete"
        )
    if evidence.get("conclusion_state") != "current":
        parts.append(
            "Numerical conclusions are "
            + str(evidence.get("conclusion_state") or "unavailable")
        )
    summary = (
        '<p class="diagnostic-source-summary">' + escape(" · ".join(parts)) + ".</p>"
    )
    clocks = "".join(
        "<li><time>" + escape(stamp) + "</time></li>" for stamp in original
    )
    facts = {
        "source_identity": identity or "Unavailable",
        **{
            key: value
            for key, value in evidence.items()
            if key != "source_observations"
        },
    }
    # All original fields remain inspectable, including retention/attempt clocks;
    # no internal solver objects or player dictionaries are dumped here.
    details = (
        '<details class="diagnostic-source-provenance"><summary>Detailed source provenance</summary>'
        "<p>Original source observations; retrieval and refresh attempts do not reset source age. Fresh before 1 hour; Aging from 1 hour; Stale from 6 hours.</p>"
        '<div style="max-height:24rem;overflow:auto;overflow-wrap:anywhere" tabindex="0" role="region" aria-label="Complete source observations">'
        + (
            "<ul>" + clocks + "</ul>"
            if clocks
            else "<p>Source observation times unavailable.</p>"
        )
        + '</div><details><summary>Source identity and qualifications</summary><pre style="max-height:24rem;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere">'
        + escape(json.dumps(facts, indent=2, default=str))
        + "</pre></details></details>"
    )
    return summary, details
