"""Plain-language recent carries and targets; source detail stays optional."""

from html import escape
from datetime import datetime

from src.ui.customer_experience import readable_time

_REASONS = {
    "completed_week_boundary_unknown": "The completed NFL week is not confirmed for this comparison.",
    "six_observations_not_available": "Six eligible regular-season game observations are not retained.",
    "game_observations_missing": "Game records are missing within or after the recent sample; absent records are not zero.",
    "stat_fields_missing": "Some selected games do not report this statistic; missing values are not zero.",
    "conflicting_stat_records": "Retained records disagree about this statistic.",
    "game_type_unknown": "Some retained records do not confirm the game type.",
    "game_week_unknown": "Some retained records do not confirm the week.",
    "game_identity_unknown": "Some retained records do not confirm the game or historical team.",
    "game_order_or_identity_conflict": "The selected game identities or order cannot be reconciled.",
    "league_season_unknown": "The selected league season is not confirmed.",
    "usage_not_retained": "Game-level carries and targets are not prepared yet.",
}


def _number(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _dates(games):
    first, last = (datetime.fromisoformat(games[i]["date"]) for i in (0, -1))

    def label(d):
        return d.strftime("%b") + " " + str(d.day)

    return f"{label(first)} – {label(last)}, {last.year} UTC"


def workload_panel(usage: dict) -> str:
    comparison = usage.get("recent_workload") or {}
    parts = []
    for metric, item in comparison.get("metrics", {}).items():
        label = metric.title()
        if item["status"] == "supported":
            before, after, delta = (
                item["previous_average"],
                item["recent_average"],
                item["difference"],
            )
            verb = (
                "increased"
                if delta > 0
                else "decreased"
                if delta < 0
                else "were unchanged"
            )
            sentence = (
                f"{label} {verb} from {_number(before)} to {_number(after)} per observed game."
                if delta
                else f"{label} were unchanged at {_number(after)} per observed game."
            )
            parts.append(
                "<p><b>"
                + escape(sentence)
                + "</b> "
                + escape(
                    "Difference: "
                    + ("+" if delta > 0 else "")
                    + _number(delta)
                    + " per observed game."
                )
                + "</p>"
            )
        else:
            parts.append(
                "<p><b>"
                + label
                + " comparison unavailable.</b> "
                + escape(_REASONS[item["reasons"][0]])
                + "</p>"
            )
    if not parts:
        reasons = comparison.get("reasons") or [
            usage.get("reason", "six_observations_not_available")
        ]
        parts.append(
            "<p>"
            + escape(
                _REASONS.get(
                    reasons[0],
                    "A recent workload comparison is not supported by the retained evidence.",
                )
            )
            + "</p>"
        )
    if comparison.get("unobserved_weeks"):
        parts.append(
            "<p>Unobserved weeks: "
            + escape(", ".join(map(str, comparison["unobserved_weeks"])))
            + ".</p>"
        )
    previous, recent = comparison.get("previous") or [], comparison.get("recent") or []
    if previous and recent:
        parts.append(
            "<p>Previous 3: "
            + escape(_dates(previous))
            + "<br>Latest 3: "
            + escape(_dates(recent))
            + "</p>"
        )
    if "teams_changed" in comparison.get("qualifications", []):
        parts.append(
            "<p>The sample spans an NFL team change. These observations do not establish why workload changed.</p>"
        )
    receipt = usage.get("source_check") or {}
    if receipt and receipt.get("status") != "complete":
        parts.append(
            "<p>The latest source update did not complete. These are retained observations.</p>"
        )
    parts.append(
        '<p class="muted">Observed regular-season games, not complete season coverage or a forecast.</p>'
    )
    records = previous + recent or (usage.get("games") or [])[-6:]
    rows = []
    for row in records:
        rows.append(
            "<li>"
            + escape(
                " · ".join(
                    (
                        str(row.get("date") or "Date not retained"),
                        "Week " + str(row.get("week")),
                        str(row.get("team") or "Team not retained"),
                        "Carries: "
                        + str(
                            row.get("carries")
                            if row.get("carries") is not None
                            else "Unknown"
                        ),
                        "Targets: "
                        + str(
                            row.get("targets")
                            if row.get("targets") is not None
                            else "Unknown"
                        ),
                    )
                )
            )
            + (
                "<br><small>"
                + escape(
                    "Game: "
                    + str(row["game_id"])
                    + " · First eligible knowledge: "
                    + ", ".join(row.get("knowledge_boundaries") or [])
                )
                + "</small>"
                if row.get("game_id")
                else ""
            )
            + "</li>"
        )
    totals = "; ".join(
        key.title()
        + ": "
        + str(usage.get(key) if usage.get(key) is not None else "Unknown")
        for key in ("carries", "targets")
    )
    detail = (
        "<p>Source: nflverse player statistics, separate from Sleeper fantasy scores. "
        "The latest six eligible observations form two consecutive samples of three. "
        "Zeros are included; missing fields are not skipped. Live and later weeks are excluded by the admitted NFL completed-week boundary. "
        "Missing game records block comparison unless a complete retained schedule establishes a bye. "
        "A game observation does not establish snaps, routes, injury status or future performance.</p>"
        "<p>Retained usage totals: "
        + escape(totals)
        + " · "
        + escape(str(usage.get("sample_count", 0)))
        + " source game observations. Totals have their own retained sample.</p>"
        "<p>Last source check: "
        + escape(readable_time(receipt.get("checked_at")))
        + " · "
        + escape(str(receipt.get("status") or "No receipt retained"))
        + "</p><ul>"
        + "".join(rows)
        + "</ul>"
        "<p>Comparison generation: <code>"
        + escape(str(comparison.get("generation") or "Unknown"))
        + "</code></p>"
    )
    return (
        '<section class="card recent-workload" style="min-width:0;overflow-wrap:anywhere" aria-labelledby="recent-workload-title">'
        '<h3 id="recent-workload-title">Recent carries and targets</h3>'
        + "".join(parts)
        + "<details><summary>Game samples and sources</summary>"
        + detail
        + "</details></section>"
    )
