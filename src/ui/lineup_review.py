"""Accessible presentation of a prepared review, never a lineup submission."""

from html import escape
from src.core.intelligence.lineup_review import timestamp


def local_check_time(value):
    instant = timestamp(value)
    if instant is None:
        return "Not recorded"
    return (f'<time data-lineup-local-time datetime="{instant.isoformat()}">'
            f'{instant.strftime("%a %b %d, %H:%M UTC")}</time>')


def _primary_panel(review):
    if not review or review.get("state") == "no_improvement":
        return ""
    active = bool(review.get("actionable"))
    heading = "Higher-projected lineup available" if active else "Lineup comparison"
    gain = review.get("gain")
    points = (
        f"<p><b>+{gain:.2f} projected points</b> among supported players · Week {review['week']}.</p>"
        if gain is not None and gain > 0
        else ""
    )
    if (
        gain is not None
        and gain > 0
        and review.get("baseline_kind") == "named_starter_subtotal"
    ):
        points += (
            f"<p>Compared with {review['baseline']:.2f} projected points from the named starters; "
            f"{review['empty_slots']} submitted slot(s) are empty. This is a subtotal, not a complete lineup projection.</p>"
        )
    changes = ""
    if active:

        def name(player):
            return escape(player["name"]) + (
                f" ({escape(player['position'])})" if player.get("position") else ""
            )

        changes = (
            "<ul>"
            + "".join(
                f"<li>{escape(change['slot'])}: {name(change['in'])} instead of {name(change['out'])}.</li>"
                for change in review["changes"]
            )
            + "</ul>"
        )
        changes += "<p>Apply these changes together in Sleeper. DTOS has not changed your lineup.</p>"
        checked = local_check_time(review["observed_at"])
        changes += f"<p>Roster checked {checked} · roster and projection checks within 15 minutes.</p>"
        changes += (
            f"<details><summary>Check times and limitations</summary><p>Roster retrieved {escape(review['observed_at'])}; projections prepared "
            f"{escape(review['projection_observed_at'])}. These are retrieval/preparation times, not a guaranteed provider update time. "
            "Only supported player projections are compared. This alert expires at the first affected kickoff or when either check becomes 15 minutes old.</p></details>"
        )
    deadline = (
        f' data-review-until="{escape(review["valid_until"])}" data-review-checked-at="{escape(review["verified_at"])}"'
        if active
        else ""
    )
    return (
        f'<section class="lineup-review" data-lineup-review="{review["state"]}"{deadline} aria-label="Lineup review">'
        f"<h3>{heading}</h3>{points}<div data-review-current><p>{escape(review['reason'])}</p>{changes}</div>"
        '<p data-review-expired role="status" aria-live="polite" hidden>This lineup check has expired. Reload to recheck game locks and evidence before changing your lineup.</p>'
        '<p><a class="button" href="https://sleeper.com/" rel="noopener noreferrer">Review in Sleeper</a></p></section>'
    )


def fallback_panel(fallback):
    if not fallback:
        return ""
    if not fallback.get("moves"):
        return f'<section class="lineup-review"><h3>Lineup fallback</h3><p>{escape(fallback["reason"])}</p></section>'
    starter = escape(fallback["starter"])
    moves = fallback["moves"]
    def slot_name(slot):
        return escape("Superflex" if slot in {"SUPER_FLEX", "SUPERFLEX"} else slot)
    slot, backup, _ = moves[0]
    if len(moves) == 1:
        plan = f"<p>If {starter} is ruled out, {escape(backup)} can cover {slot_name(slot)}.</p>"
    else:
        plan = f"<p>If {starter} is ruled out, make these moves together.</p><ul>"
        plan += "".join(f"<li>{slot_name(slot)}: {escape(incoming)} in for {escape(outgoing)}.</li>"
                        for slot, incoming, outgoing in moves) + "</ul>"
    note = " A required game starts before the starter’s game." if fallback["earlier_game"] else ""
    return (
        f'<section class="lineup-review" data-lineup-review="fallback" data-review-until="{escape(fallback["valid_until"])}"'
        f' data-review-checked-at="{escape(fallback["verified_at"])}" aria-label="Lineup fallback">'
        f'<h3>Lineup fallback</h3><div data-review-current>{plan}'
        f'<p>Decide before {local_check_time(fallback["kickoff_deadline"])} game lock.{note} '
        f'Recheck by {local_check_time(fallback["valid_until"])}.</p></div>'
        '<p data-review-expired role="status" aria-live="polite" hidden>'
        'This fallback check has expired. Check Sleeper before making any lineup changes.</p>'
        '<p><a class="button" href="https://sleeper.com/" rel="noopener noreferrer">Review in Sleeper</a></p></section>'
    )


def lineup_recheck_panel(recheck, fallback):
    if not recheck:
        return fallback_panel(fallback)
    return (
        f'<div class="lineup-recheck" id="lineup-recheck" data-lineup-recheck-scope="{escape(recheck["scope"])}"'
        f' data-lineup-observed="{escape(recheck["observed_at"] or "")}"'
        f' data-lineup-has-fallback="{str(bool(fallback)).lower()}">'
        + fallback_panel(fallback)
        + '<div class="lineup-recheck-controls">'
        f'<p>Submitted lineup last checked: {local_check_time(recheck["observed_at"])}.</p>'
        '<button type="button" class="btn" data-lineup-recheck hidden>Recheck lineup</button>'
        '<p data-lineup-recheck-status role="status" tabindex="-1" hidden></p></div></div>'
    )


def review_panel(review, *, recheck=None):
    return _primary_panel(review) + lineup_recheck_panel(recheck, (review or {}).get("fallback"))
