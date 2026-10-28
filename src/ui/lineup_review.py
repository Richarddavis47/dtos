"""Accessible presentation of a prepared review, never a lineup submission."""
from html import escape
from services.lineup_review import timestamp


def review_panel(review):
    if not review or review.get('state') == 'no_improvement':
        return ''
    active = bool(review.get('actionable'))
    heading = 'Higher-projected lineup available' if active else 'Lineup comparison'
    gain = review.get('gain')
    points = (f'<p><b>+{gain:.2f} projected points</b> among supported players · Week {review["week"]}.</p>'
              if gain is not None and gain > 0 else '')
    changes = ''
    if active:
        def name(player):
            return escape(player['name']) + (f' ({escape(player["position"])})' if player.get('position') else '')
        changes = '<ul>' + ''.join(f'<li>{escape(change["slot"])}: {name(change["in"])} instead of {name(change["out"])}.</li>'
                                   for change in review['changes']) + '</ul>'
        changes += '<p>Apply these changes together in Sleeper. DTOS has not changed your lineup.</p>'
        checked = timestamp(review['observed_at']).strftime('%H:%M UTC')
        changes += f'<p>Roster checked {checked} · roster and projection checks within 15 minutes.</p>'
        changes += (f'<details><summary>Check times and limitations</summary><p>Roster retrieved {escape(review["observed_at"])}; projections prepared '
                    f'{escape(review["projection_observed_at"])}. These are retrieval/preparation times, not a guaranteed provider update time. '
                    'Only supported player projections are compared. This alert expires at the first affected kickoff or when either check becomes 15 minutes old.</p></details>')
    deadline = f' data-review-until="{escape(review["valid_until"])}"' if active else ''
    return (f'<section class="lineup-review" data-lineup-review="{review["state"]}"{deadline} aria-label="Lineup review">'
            f'<h3>{heading}</h3>{points}<div data-review-current><p>{escape(review["reason"])}</p>{changes}</div>'
            '<p data-review-expired hidden>This lineup check has expired. Reload to recheck game locks and evidence before changing your lineup.</p>'
            '<p><a class="button" href="https://sleeper.com/" rel="noopener noreferrer">Review in Sleeper</a></p></section>')
