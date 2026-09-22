"""One deterministic, escaped hierarchy; no intelligence interpretation."""
from html import escape

from src.core.explanations import Availability, Explanation


_UNAVAILABLE = {
    Availability.UNAVAILABLE: 'Unavailable',
    Availability.NOT_APPLICABLE: 'Not applicable',
    Availability.NO_COMPARABLE_EVIDENCE: 'No comparable evidence',
}


def explanation_panel(view: Explanation, *, evidence_groups=()) -> str:
    def statements(title, rows):
        if not rows:
            return ''
        items = ''.join(f'<li>{escape(row.text)}</li>' for row in rows)
        return f'<h4>{escape(title)}</h4><ul>{items}</ul>'

    def render_evidence(rows):
        return ''.join(
            '<li>' + escape(item.label) + ': <strong>'
            + escape(_UNAVAILABLE.get(item.availability, item.display or ''))
            + '</strong> <span>(' + escape(item.kind.value)
            + ('; partial' if item.availability == Availability.PARTIAL else '')
            + ')</span></li>' for item in rows)
    grouped_keys = [key for _, keys in evidence_groups for key in keys]
    if len(grouped_keys) != len(set(grouped_keys)) or not set(grouped_keys).issubset({e.key for e in view.evidence}):
        raise ValueError('Presentation groups require unique existing evidence')
    evidence = render_evidence(item for item in view.evidence if item.key not in grouped_keys)
    grouped = ''.join('<details><summary style="min-height:44px;cursor:pointer">' + escape(title)
                      + '</summary><ul>' + render_evidence(item for item in view.evidence if item.key in keys)
                      + '</ul></details>' for title, keys in evidence_groups if keys)
    advanced = statements('Detail', view.advanced)
    # No raw source payloads, private paths or inspection links are exposed.
    # Unit/scope/method identities remain on the view for trusted adapters.
    return (
        '<section class="dtos-explanation" aria-label="' + escape(view.subject, quote=True) + '">'
        '<h3>' + escape(view.subject) + '</h3><p>' + escape(view.conclusion.text) + '</p>'
        + statements('Why', view.why)
        + statements('Trade-off / risk', view.tradeoffs)
        + statements('Evidence confidence', view.confidence)
        + ('<details><summary style="min-height:44px;cursor:pointer;overflow-wrap:anywhere">Supporting evidence and limitations</summary>'
           + ('<h4>Key evidence</h4><ul>' + evidence + '</ul>' if evidence else '')
           + statements('Limitations', view.limitations) + grouped + advanced + '</details>'
           if evidence or grouped or view.limitations or advanced else '')
        + '</section>'
    )
