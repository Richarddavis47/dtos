"""Render admitted Sleeper observations; no acquisition or scoring work."""
from html import escape
from src.core.player_value_projection.sleeper_actuals import actual_display

_REASONS = {
    'conflicting_sleeper_scores': 'Sleeper score records disagree; no value selected',
    'duplicate_starter_identity': 'Sleeper repeats this starter identity',
    'invalid_sleeper_score': 'Sleeper score is null or invalid',
    'invalid_alternate_score': 'An alternate Sleeper field is null or invalid; the explicit valid score is shown',
    'score_not_observed': 'No individual Sleeper score was supplied',
    'SOURCE_WEEK_UNAVAILABLE': 'The weekly source request failed',
    'INVALID_SOURCE_WEEK': 'The weekly source response could not be admitted',
    'compatible_sleeper_matchup_publication_unavailable': 'A compatible Sleeper league-season matchup publication is not prepared',
    'sleeper_scoring_provenance_unverified': 'The retained matchup publication does not verify the selected scoring context',
}


def _reason(value):
    return _REASONS.get(value, 'This observation cannot be verified from the retained Sleeper evidence')


def production_summary(production: dict | None) -> str | None:
    if not production:
        return None
    if production.get('authority') != 'sleeper-matchup-actuals-v1':
        return 'Compatible Sleeper actual results are not prepared. Non-Sleeper analysis and separate Career History observations do not replace authoritative fantasy results. A normal league refresh can prepare supported results when capacity permits.'
    row = next((w for w in production.get('windows') or [] if w['label'] == 'Season Average'), None)
    if not row:
        return None
    count, scored, value = row.get('observation_count'), row.get('scored_count'), row.get('fantasy_points')
    coverage = f'{scored} of {count} completed-week score observations have explicit, consistent Sleeper scores.'
    if not count:
        return 'No compatible completed-week Sleeper scores are retained for this player. Live weeks and absent matchup records do not supply completed results.'
    if value is not None:
        return f'{row.get("season")}: {actual_display(value)} fantasy points per score observation. {coverage} Observed total: {actual_display(row["observed_total"])}. This is not a games-played average or a full-season total.'
    return coverage + ' The dependent fantasy-point average and total are withheld because Sleeper score evidence is missing or contradictory.'


def production_panel(production: dict | None, *, refresh_failed: bool = False) -> str:
    summary = production_summary(production)
    if not summary:
        return ''
    retained = ('<p class="evidence-unavailable">The league refresh did not complete. These are retained observations, not newly revalidated results.</p>' if refresh_failed else '')
    rows = []
    for window in production.get('windows') or []:
        points = actual_display(window["fantasy_points"]) if window.get('fantasy_points') is not None else 'Withheld: incomplete or missing evidence'
        total = actual_display(window["observed_total"]) if window.get('observed_total') is not None else 'Withheld'
        rows.append('<tr><th scope="row">' + escape(window['label']) + '</th><td>'
                    + escape(str(window.get('season') or 'Unknown')) + '</td><td>'
                    + escape(', '.join(str(w) for w in window.get('weeks') or ()) or 'None retained')
                    + '</td><td>' + escape(f'{window.get("scored_count")}/{window.get("observation_count")}')
                    + '</td><td>' + points + '</td><td>' + total + '</td></tr>')
    observations = []
    for row in production.get('observations') or ():
        value = actual_display(row["points"]) if row.get('points') is not None else 'Not available'
        qualifications = [_reason(r) for r in row.get('reasons') or ()]
        if row.get('corrected'):
            qualifications.append('Sleeper score changed since the preceding retained publication')
        observations.append('<tr><th scope="row">' + str(int(row['week'])) + '</th><td>' + value
            + '</td><td>' + escape(str(row['state']) + ' · ' + str(row['scope']))
            + '</td><td>' + escape(str(row.get('retrieved_at') or 'Unknown') + ' · ' + ('current at retrieval' if row.get('freshness') == 'current' else str(row.get('freshness') or 'Unknown')))
            + '</td><td>' + escape('; '.join(qualifications) or 'Explicit Sleeper score; participation not established') + '</td></tr>')
    periods = '; '.join('Week ' + str(key) + ': ' + str(row.get('availability') or 'unknown')
        + (' — ' + _reason(row['reason']) if row.get('reason') else '')
        for key, row in (production.get('periods') or {}).items())
    usage = ''.join('<li>' + escape(str(row.get('season') or 'Unknown') + ' · ' + str(row['label'])
        + ' · ' + str(row.get('observation_count')) + ' NFLverse game observations · Targets: '
        + str(row.get('targets') if row.get('targets') is not None else 'Unknown')
        + ' · Carries: ' + str(row.get('carries') if row.get('carries') is not None else 'Unknown'))
        + '</li>' for row in production.get('usage_analysis') or () if row['label'] in {'Season Average','Previous Season Average'})
    usage = ('<details><summary>Separate NFLverse usage analysis</summary><p>These observed-game usage averages '
        'are not Sleeper fantasy results. They have their own sample; no missing scoring component is reconstructed.</p><ul>'
        + usage + '</ul></details>') if usage else ''
    notes = ''.join('<li>' + escape(str(note)) + '</li>' for note in production.get('limitations') or ())
    return ('<section class="card canonical-production" style="min-width:0;overflow-wrap:anywhere">'
            '<h3>Sleeper actual fantasy results · selected league</h3><p>' + escape(summary) + '</p>' + retained
            + '<p>Source: ' + escape(str(production.get('source') or 'Sleeper league matchup results'))
            + ' · League: ' + escape(str(production.get('league_id') or 'Unknown'))
            + ' · Preparation observed: ' + escape(str(production.get('updated_at') or 'Unknown')) + '</p>'
            '<p>Each window averages only its retained completed-week score observations. Missing periods are not zero. '
            'Live or unconfirmed results are shown separately below; they are not completed-week production. '
            'League regular-season and playoff observations are identified by the league’s own calendar; these labels do not claim NFL postseason coverage.</p>'
            '<div class="ds-table-wrap" tabindex="0" role="region" aria-label="Sleeper result windows">'
            '<table style="min-width:42rem;overflow-wrap:normal;word-break:normal"><caption>Completed-week observations: averages and observed totals</caption><thead><tr>'
            '<th>Window</th><th>Season</th><th>Observed weeks</th><th>Scored / observed</th>'
            '<th>Points per observation</th><th>Observed total</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
            '<details><summary>Weekly Sleeper scores and coverage</summary><p>' + escape(periods or 'Weekly acquisition coverage is not retained.') + '</p>'
            '<div class="ds-table-wrap" tabindex="0" role="region" aria-label="Weekly Sleeper results">'
            '<table style="min-width:42rem;overflow-wrap:normal;word-break:normal"><caption>Retained individual scores; team custom-point adjustments excluded</caption>'
            '<thead><tr><th>Week</th><th>Points</th><th>Result / period</th><th>Retrieval / freshness</th><th>Qualification</th></tr></thead><tbody>'
            + ''.join(observations) + '</tbody></table></div></details>' + usage + '<ul>' + notes + '</ul>'
            '<p>Non-Sleeper usage, fixed-reference valuation analysis, historical roster observations and forward Sleeper '
            'projections remain separate. No absent score, bye or DNP is reconstructed. Retained historical grades are not revalidated here.</p></section>')
