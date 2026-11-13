"""Real prepared Market/dossier routes: useful facts first, evidence on demand."""
from copy import deepcopy
from html.parser import HTMLParser
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.test_current_production_coverage import ProductionViewFixture


class _DefaultText(HTMLParser):
    """Approximate native closed disclosures for text assertions, not visual proof."""
    def __init__(self):
        super().__init__()
        self.details = []
        self.summary = 0
        self.ignored = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'details':
            self.details.append('open' in dict(attrs))
        elif tag == 'summary':
            self.summary += 1
        elif tag in {'style', 'script'}:
            self.ignored += 1

    def handle_endtag(self, tag):
        if tag == 'details':
            self.details.pop()
        elif tag == 'summary':
            self.summary -= 1
        elif tag in {'style', 'script'}:
            self.ignored -= 1

    def handle_data(self, text):
        visible = all(self.details) or (self.summary and all(self.details[:-1]))
        if not self.ignored and (not self.details or visible):
            self.parts.append(text)


def default_text(html):
    view = _DefaultText()
    view.feed(html)
    return ' '.join(view.parts)


class CustomerMarketPlayerExperienceTests(unittest.TestCase):
    def fixture(self):
        return ProductionViewFixture(self)

    def page(self, fixture, path):
        response = fixture.f.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_player_leads_with_results_and_actions_not_forecast_placeholders(self):
        f = self.fixture()
        html = self.page(f, '/players/1?front_office=4')
        text = default_text(html)
        self.assertIn('Sleeper actual fantasy results', text)
        self.assertIn('18.00 fantasy points per score observation', text)
        self.assertNotIn('A reliable multi-season outlook is not available', text)
        self.assertNotIn('A full-season forecast is not available', text)
        self.assertNotIn('Current Season', text)
        self.assertNotIn('2-Year Outlook', text)
        self.assertNotIn('Long-Term Outlook', text)
        self.assertNotIn('Data Availability', text)
        self.assertIn('Forecast limits', html)
        self.assertIn('not a games-played average', text)
        self.assertIn('Market and player sources', text)
        self.assertIn('Viewing for', text)

    def test_missing_model_stays_explicit_in_optional_evidence(self):
        f = self.fixture()
        html = self.page(f, '/players/1?front_office=4')
        self.assertIn('DTOS does not publish unsupported season or multi-year forecasts', html)
        self.assertIn('A reliable multi-season outlook is not available', html)
        self.assertIn('A full-season forecast is not available', html)
        self.assertNotIn('Opportunity Analysis', html)

    def test_market_exposes_supported_value_and_actuals_before_model_details(self):
        f = self.fixture()
        html = self.page(f, '/market?selected=player%3A1&front_office=4')
        text = default_text(html)
        self.assertIn('Market value:', text)
        self.assertIn('18.00 fantasy points per score observation', text)
        self.assertIn('Open player', text)
        self.assertNotIn('Intrinsic', text)
        self.assertNotIn('Rebuilder', text)
        self.assertNotIn('Canonical Market', text)
        self.assertNotIn('canonical dossier', text)
        self.assertNotIn('Download Market movement data (JSON)', text)
        self.assertIn('href="/api/market/trending"', html)
        self.assertIn('Full market evidence table', html)

    def test_exact_source_zero_and_negative_remain_unmodified(self):
        f = self.fixture()
        for value, display in ((0, '0.00'), (-2.125, '-2.13')):
            with self.subTest(value=value):
                for week in f.f.data['season_matchups']['weeks'].values():
                    for row in week['rows']:
                        row['players_points']['1'] = value
                        row['starters_points'] = [value]
                f.republish_actuals()
                for path in ('/players/1', '/market?selected=player%3A1'):
                    text = default_text(self.page(f, path))
                    self.assertIn(display + ' fantasy points per score observation', text)
                api = f.api()
                self.assertEqual(api['observations'][0]['points'], value)
                self.assertEqual(api['windows'][3]['fantasy_points'], value)

    def test_partial_and_failed_refresh_keep_material_qualification_visible(self):
        f = self.fixture()
        f.f.data['season_matchups']['weeks']['1']['rows'][0]['starters_points'] = [999]
        f.republish_actuals()
        f.f.state['last_error'] = 'disposable failed source update'
        for path in ('/players/1', '/market?selected=player%3A1'):
            html = self.page(f, path)
            text = default_text(html)
            self.assertIn('7 of 8 completed-week score observations', text)
            self.assertIn('are withheld', text)
            self.assertIn('retained observations, not newly revalidated', text)
            self.assertIn('Sleeper score records disagree', html)
        self.assertIsNone(f.api()['windows'][3]['fantasy_points'])

    def projection(self, fixture, row):
        data = fixture.f.data
        pin = dict(league_id=data['league']['league_id'], season=int(data['league']['season']),
                   scoring_settings=data['scoring_settings'], week=data['week'],
                   horizon_generation='disposable-player-view',
                   horizon_snapshot_ids={str(data['week']): 'leaf'}, projection_snapshot_id='leaf')
        snapshot = dict(pin, players={'1': deepcopy(row)})
        return SimpleNamespace(snapshot=lambda: snapshot, week_snapshot=lambda week, **kwargs: snapshot)

    def test_selected_market_keeps_source_availability_beside_supported_zero(self):
        f = self.fixture()
        row = dict(player_id='1', canonical_projection=0, sleeper_web_display_projection='0.00',
                   availability='out', nfl_team_state='assigned')
        reader = self.projection(f, row)
        with patch('routes.market.projection_service', reader):
            html = self.page(f, '/market?selected=player%3A1')
        text = default_text(html)
        self.assertIn('0.00', text)
        self.assertIn('Listed OUT at preparation', text)
        self.assertIn('excluded from current-week playable lineup cover', text)
        self.assertNotIn('Weekly projection unavailable.', text)
        self.assertEqual(reader.snapshot()['players']['1'], row)

    def test_selected_market_explains_the_specific_source_gap_not_generic_missing(self):
        f = self.fixture()
        row = dict(player_id='1', canonical_projection=None,
                   missing_projection_reason='NO_SCORING_STATISTICS')
        reader = self.projection(f, row)
        with patch('routes.market.projection_service', reader):
            html = self.page(f, '/market?selected=player%3A1')
        self.assertIn('a player-week record exists, but contains no usable scoring statistics', default_text(html))
        self.assertNotIn('0.00 projected points', default_text(html))
        self.assertIn('18.00 fantasy points per score observation', default_text(html))
        self.assertIsNone(reader.snapshot()['players']['1']['canonical_projection'])

    def test_reading_disclosures_changes_no_source_or_state(self):
        f = self.fixture()
        before = deepcopy(f.f.data)
        values = f.api()
        # Existing fixture guards reject provider/sync/history acquisition.
        self.page(f, '/market?selected=player%3A1&offset=0&limit=25')
        self.page(f, '/players/1?from_market=%2Fmarket%3Fselected%3Dplayer%253A1&market_league=' + str(f.f.data['league']['league_id']))
        self.assertEqual(f.f.data, before)
        self.assertEqual(f.api(), values)
