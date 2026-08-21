"""Human-first formatting for canonical DTOS intelligence contracts."""
from __future__ import annotations

from html import escape
from typing import Any, Iterable

_STATUS_LABELS = {
    "completed_with_pending": "Completed with pending season",
    "complete": "Complete", "completed": "Completed", "running": "In progress",
    "pending": "Pending", "resolved": "Verified",
    "unresolved": "Identity not verified", "failed": "Needs attention",
    "unsupported": "Not currently available",
}


def league_is_preseason(data: dict[str, Any]) -> bool:
    """Recognize an explicit or evidence-backed pre-kickoff league state."""
    if data.get("preseason"):
        return True
    if int(data.get("week") or 0) > 1:
        return False
    teams = data.get("teams") or []
    if not teams:
        return False
    no_results = all(
        int(team.get("wins") or 0) == 0
        and int(team.get("losses") or 0) == 0
        and int(team.get("ties") or 0) == 0
        and float(team.get("points_for") or 0) == 0
        for team in teams
    )
    no_matchup_scoring = all(
        float(side.get("points") or 0) == 0
        for sides in (data.get("matchups") or {}).values()
        for side in (sides or [])
    )
    return no_results and no_matchup_scoring


def human_status(value: Any, *, fallback: str = "Not yet available") -> str:
    if value is None or str(value).strip() == "":
        return fallback
    raw = str(value).strip()
    return _STATUS_LABELS.get(raw.casefold(), raw.replace("_", " ").title())


def available(value: Any, *, reason: str = "Not yet available") -> str:
    return reason if value is None or value == "" else str(value)


def numeric_evidence(value: Any, *, reason: str = "Not yet available") -> str:
    """Format numeric evidence without turning an absent value into zero."""
    if value is None or value == "":
        return reason
    return str(value)


def projection_coverage_count(coverage: Any) -> int:
    """Return the contributing projection count from a compact coverage value."""
    if isinstance(coverage, int):
        return max(0, coverage)
    if isinstance(coverage, str):
        head = coverage.partition("/")[0].strip()
        return max(0, int(head)) if head.isdigit() else 0
    return 0


def projection_presentation_value(total: Any, coverage: Any) -> Any | None:
    """Preserve an available zero while withholding a zero-coverage aggregate."""
    return total if projection_coverage_count(coverage) > 0 else None


def matchup_game_state(data: dict[str, Any], sides: list[dict[str, Any]]) -> str:
    """Return the shared presentation state for matchup score evidence."""
    if league_is_preseason(data):
        return "pregame"
    statuses = {
        str(side.get("status") or side.get("game_status") or "").casefold()
        for side in sides
    }
    if statuses & {"final", "complete", "completed"}:
        return "final"
    if any(float(side.get("points") or 0) != 0 for side in sides):
        return "in-game"
    return "pregame"


def record_evidence(
    wins: Any,
    losses: Any,
    ties: Any = 0,
    *,
    season_started: bool,
) -> str:
    """Return a real record only after competitive scoring has started."""
    if not season_started:
        return "Regular-season record not started"
    if wins is None or losses is None:
        return "Record unavailable"
    return f"{int(wins)}-{int(losses)}-{int(ties or 0)}"


def matchup_score_hierarchy(
    *,
    actual: Any,
    pregame: Any,
    state: str,
    live_projected_final: Any = None,
) -> tuple[tuple[str, str], ...]:
    """Return score rows ordered by the evidence appropriate to game state."""
    normalized = state.casefold().replace("_", "-")
    if normalized in {"pregame", "not-started", "not started"}:
        return (("Pregame projection", numeric_evidence(pregame, reason="Projection unavailable")),)
    if normalized in {"final", "complete", "completed"}:
        rows = [("Final actual", numeric_evidence(actual, reason="Final score unavailable"))]
        rows.append(("Pregame projection", numeric_evidence(
            pregame, reason="Projection unavailable",
        )))
        return tuple(rows)
    rows = [("Actual", numeric_evidence(actual, reason="Live score unavailable"))]
    if live_projected_final not in (None, ""):
        rows.append(("Live projected final", str(live_projected_final)))
    rows.append(("Pregame projection", numeric_evidence(
        pregame, reason="Projection unavailable",
    )))
    return tuple(rows)


def exact_rank(value: Any, total: Any = None) -> str:
    if value in (None, "", 0, "0"):
        return "Not ranked — insufficient evidence"
    suffix = f" of {total}" if total not in (None, "", 0, "0") else ""
    return f"#{value}{suffix}"


def historical_availability(progress: dict[str, Any] | None) -> str:
    progress = progress or {}
    completed = _season_span(progress.get("completed_seasons") or [])
    pending = _season_span(progress.get("pending_seasons") or [])
    parts = ([f"{completed} complete"] if completed else [])
    if pending:
        parts.append(f"{pending} pending provider evidence")
    return "; ".join(parts) or "Historical evidence is not yet available"


def technical_details(rows: Iterable[tuple[str, Any]], *, summary: str = "Technical Details") -> str:
    items = "".join(
        f"<dt>{escape(str(label))}</dt><dd><code>{escape(available(value))}</code></dd>"
        for label, value in rows
    )
    return f'<details class="technical-details"><summary>{escape(summary)}</summary><dl>{items}</dl></details>'


def event_label(value: Any) -> str:
    return human_status(value)


def matchup_state(*, left: float, right: float, week: int, season_started: bool = True) -> str:
    if not season_started or (week <= 1 and left == 0 and right == 0):
        return "Not Started"
    return "Tied" if left == right else "Live"


def _season_span(values: Iterable[Any]) -> str:
    seasons = sorted({int(value) for value in values if str(value).isdigit()})
    if len(seasons) > 1 and seasons == list(range(seasons[0], seasons[-1] + 1)):
        return f"{seasons[0]}–{seasons[-1]}"
    return ", ".join(str(value) for value in seasons)
