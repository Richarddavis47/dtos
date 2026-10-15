"""Readable current-week scenarios; retain full calculation precision internally."""

from html import escape


def evidence_html(diagnostic, players):
    names = {
        str(p.get("id") or p.get("player_id")): str(
            p.get("name") or p.get("full_name") or "Player name unavailable"
        )
        for p in players
    }
    rows = []
    scenarios = diagnostic.get("remove_one") or {}
    # Starter removal and largest supported losses first; all scenarios remain
    # available in one separate list, without dumping solver intermediates.
    ordered = sorted(
        scenarios.items(),
        key=lambda item: (
            item[0] not in (diagnostic.get("starting_ids") or []),
            -(item[1].get("lineup_loss") or 0),
            names.get(item[0], ""),
        ),
    )
    for pid, scenario in ordered:
        loss = scenario.get("lineup_loss")
        impact = (
            f"{loss:.2f} projected points" if loss is not None else "unavailable impact"
        )
        replacements = scenario.get("replacement_names") or []
        change = (
            (" Supported replacement: " + ", ".join(replacements) + ".")
            if replacements
            else " No starting-lineup substitution is required."
            if scenario.get("preserves_lineup")
            else " No additional usable replacement is established."
        )
        support = (
            " Starter and reserve support preserved."
            if scenario.get("preserves_lineup")
            and scenario.get("preserves_disjoint_reserve")
            else " Starter or reserve support changes; this is not established expendable depth."
        )
        rows.append(
            f"<li><strong>{escape(names.get(pid, 'Player name unavailable'))}</strong>: removing this player costs {escape(impact)}.{escape(change + support)}</li>"
        )
    visible = "".join(rows[:2])
    rest = (
        (
            "<details><summary>More removal scenarios</summary><ul>"
            + "".join(rows[2:])
            + "</ul></details>"
        )
        if len(rows) > 2
        else ""
    )
    exclusions = [
        e
        for e in diagnostic.get("eligibility") or []
        if e.get("excluded") or e.get("status") != "active"
    ]
    status = "".join(
        f"<li>{escape(e['name'])} · {escape(e.get('position') or 'Position unknown')}: {escape(e['reason'])}{' — excluded from usable cover' if e['excluded'] else ' — availability not verified'}.</li>"
        for e in exclusions
    )
    warnings = " ".join((diagnostic.get("evidence") or {}).get("limitations") or [])
    return (
        (f"<p>{escape(warnings)}</p>" if warnings else "")
        + (
            "<ul>" + visible + "</ul>"
            if visible
            else "<p>Supported removal scenarios unavailable.</p>"
        )
        + rest
        + ("<p>Availability</p><ul>" + status + "</ul>" if status else "")
    )
