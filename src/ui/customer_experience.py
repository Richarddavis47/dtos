"""Bounded presentation helpers. No evidence acquisition or qualification."""
from datetime import date, datetime, timezone
from html import escape


def readable_time(value: object) -> str:
    """Format a supplied clock without inventing precision or a timezone."""
    raw = str(value or '').strip()
    if not raw:
        return 'Time not recorded'
    try:
        if len(raw) == 10:
            day = date.fromisoformat(raw)
            return f'{day:%b} {day.day}, {day.year}'
        clock = (datetime.strptime(raw, '%Y-%m-%d %H:%M UTC').replace(tzinfo=timezone.utc)
                 if raw.endswith(' UTC') else datetime.fromisoformat(raw.replace('Z', '+00:00')))
        if clock.tzinfo is None:
            return f'{clock:%b} {clock.day}, {clock.year} · {clock:%H:%M} (timezone not recorded)'
        clock = clock.astimezone(timezone.utc)
        return f'{clock:%b} {clock.day}, {clock.year} · {clock:%H:%M} UTC'
    except (ValueError, TypeError, OverflowError):
        return 'Time not recorded'


def source_details(body: str, *, summary: str = 'Calculations and sources') -> str:
    """Wrap already escaped renderer HTML; never inspect a private payload."""
    return ('<details class="cx-evidence"><summary>' + escape(summary)
            + '</summary><div class="cx-evidence-body">' + body + '</div></details>')


def plain_reason(value: object) -> str:
    """Translate explicit implementation phrases, preserving the actual gap.

    Callers must escape the returned text. Preserve the original in source detail.
    Never apply this to an API contract, qualification code or numerical value.
    """
    text = str(value or '')
    for before, after in (
        ('Compatible league/week/scoring projection publication unavailable.',
         'Projections are not ready for this league, week and scoring.'),
        ('compatible prepared publication', 'league data for this week'),
        ('compatible projection publication', 'projections for this league and week'),
        ('Canonical Market', 'Market value'),
        ('canonical Market', 'Market value'),
        ('disjoint reserve cover', 'different eligible backups'),
    ):
        text = text.replace(before, after)
    return text
