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


def human_status(value: Any, *, fallback: str = "Not yet available") -> str:
    if value is None or str(value).strip() == "":
        return fallback
    raw = str(value).strip()
    return _STATUS_LABELS.get(raw.casefold(), raw.replace("_", " ").title())


def available(value: Any, *, reason: str = "Not yet available") -> str:
    return reason if value is None or value == "" else str(value)


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
