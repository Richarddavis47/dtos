"""Render pinned canonical production facts without source or scoring work."""
from html import escape


def _stat_name(key: str) -> str:
    return {'st_ff': 'player special-teams forced fumbles (st_ff)',
            'st_fum_rec': 'player special-teams fumble recoveries (st_fum_rec)'}.get(key, key)


def production_summary(production: dict | None) -> str | None:
    if not production:
        return None
    row = next((w for w in production.get('windows') or [] if w['label'] == 'Season Average'), None)
    if not row:
        return None
    count, scored = row.get('observation_count'), row.get('scored_count')
    value = row.get('fantasy_points')
    if count is None and value is None:
        return 'The saved canonical production summary lacks observation coverage metadata. A normal league refresh can prepare current evidence when capacity and source evidence permit. Missing production is not zero.'
    if count == 0:
        return 'No canonical current-season NFL game observations are retained in this prepared context. Separate Career History roster observations do not fill this gap.'
    season = str(row.get('season') or 'selected season')
    coverage = (f'{scored} of {count} observations have complete league scoring.'
                if count is not None and scored is not None else
                f'{count} canonical game observations; the fully scored count was not retained.' if count is not None else
                'Observation coverage was not retained in this older preparation.')
    if value is not None:
        return f'{season}: {value:,.2f} fantasy points per observed game. {coverage} This is an observed sample, not a full-season total.'
    missing = row.get('missing_components') or ()
    why = (' Missing applicable scoring statistics: ' + ', '.join(_stat_name(key) for key in missing) + '.' if missing else
           ' The saved diagnostic does not identify individual missing statistics.')
    return f'{season}: {coverage} The fantasy-point average is withheld because scoring is incomplete.' + why


def production_panel(production: dict | None, *, refresh_failed: bool = False) -> str:
    summary = production_summary(production)
    if not summary:
        return ''
    retained = ('<p class="evidence-unavailable">The league refresh did not complete. These are retained observations, not newly revalidated production.</p>' if refresh_failed else '')
    rows = []
    for window in production.get('windows') or []:
        value = window.get('fantasy_points')
        points = f'{value:,.2f}' if value is not None else 'Withheld: incomplete or missing scoring'
        count, scored = window.get('observation_count'), window.get('scored_count')
        coverage = (f'{scored}/{count}' if count is not None and scored is not None else
                    f'Unknown/{count}' if count is not None else 'Unknown')
        weeks = ', '.join(str(w) for w in window.get('weeks') or ()) or 'Not retained'
        missing = ', '.join(window.get('missing_components') or ())
        rows.append('<tr><th scope="row">' + escape(window['label']) + '</th><td>'
                    + escape(str(window.get('season') or 'Unknown')) + '</td><td>' + escape(weeks)
                    + '</td><td>' + escape(coverage) + '</td><td>' + points + '</td><td>'
                    + escape(missing or ('None' if value is not None else 'Specific fields not retained')) + '</td></tr>')
    notes = ''.join('<li>' + escape(str(note)) + '</li>' for note in production.get('limitations') or ())
    return ('<section class="card canonical-production" style="min-width:0;overflow-wrap:anywhere">'
            '<h3>Observed NFL production · selected league scoring</h3><p>' + escape(summary) + '</p>' + retained
            + '<p>Windows average retained game observations, not calendar weeks. Byes, DNPs and missing '
            'weeks are not inserted as zero. Complete scoring means all applicable scoring components '
            'are supported for that sample; it does not establish full-season acquisition or final game status.</p>'
            '<p>Source: ' + escape(str(production.get('source') or 'Canonical production'))
            + ' · Latest knowledge boundary across these windows: ' + escape(str(production.get('updated_at') or 'Unknown')) + '</p>'
            '<div class="ds-table-wrap" tabindex="0" role="region" aria-label="Canonical production observations">'
            '<table><caption>Prepared observation coverage and per-game averages</caption><thead><tr>'
            '<th>Window</th><th>Season</th><th>Observed weeks</th><th>Fully scored / observed</th>'
            '<th>Fantasy points per observation</th><th>Missing statistics</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div><ul>' + notes + '</ul>'
            '<p>Career History contains separate Sleeper roster-week observations. Those points are not '
            'substituted here. Forward Sleeper projections are also separate. The knowledge timestamp is not a provider publication date or a new source check.</p></section>')
