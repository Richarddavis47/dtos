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
        ('Review the acquisition-price relationship and available evidence; long-term intrinsic improvement is unavailable.',
         'Compare the Market cost and available lineup evidence. A long-term value forecast is not available.'),
        ('No measured counterargument crossed the unified evidence boundary.',
         'The evidence does not establish an additional drawback.'),
        ('Supported dimensions are published separately; no ambiguous overall grade is manufactured.',
         'DTOS shows individual strengths separately; an overall grade is not calculated for this evidence.'),
        ('Compatible league/week/scoring projection publication unavailable.',
         'Projections are not ready for this league, week and scoring.'),
        ('compatible prepared publication', 'league data for this week'),
        ('compatible projection publication', 'projections for this league and week'),
        ('Canonical Market', 'Market value'),
        ('canonical Market', 'Market value'),
        ('disjoint reserve cover', 'different eligible backups'),
        ('No legitimate bilateral construction clears the current constraints.',
         'No offers met the requirements for both teams in this search.'),
        ('legal-replacement production falls', 'projected points from eligible backups fall'),
        ('legal-replacement production improves', 'projected points from eligible backups improve'),
        ('legal-replacement production declines', 'projected points from eligible backups decline'),
        ('legal-replacement production', 'projected points from eligible backups'),
    ):
        text = text.replace(before, after)
    return text
