"""Rendered evidence transitions: no saved-profile/current-rank mixing."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
import unittest
import re
from unittest.mock import AsyncMock, patch

from services.team_assessment_presentation import weekly_comparison, MODEL_NOTE


class AssessmentCoverageTests(unittest.TestCase):
    def diagnostic(self):
        return dict(league_id='fixture', week=9, projection_generation='g', required_slot_count=10,
                    teams={'1': dict(optimal_points=153.3408, optimal_ids=list(range(10)),
                                     evidence=dict(calculation_supported=True, conclusion_state='current', limitations=[])),
                           '2': dict(optimal_points=None, evidence={})})

    def test_coherent_current_zero_and_missing(self):
        card = NS(league_id='fixture', roster_id=1, starting_lineup=NS(rank=99))
        d = self.diagnostic()
        text = weekly_comparison(card, 9, diagnostics=d)
        for value in ['153.34 points', '10/10', '#1 among 1', '1 of 2']:
            self.assertIn(value, text)
        self.assertNotIn('Provisional', text)
        d['teams']['1']['optimal_points'] = 0
        self.assertIn('0.00 points', weekly_comparison(card, 9, diagnostics=d))
        for wrong in [None, {**d, 'week': 8}, {**d, 'league_id': 'other'}, {**d, 'projection_generation': None}]:
            text = weekly_comparison(card, 9, diagnostics=wrong)
            self.assertIn('matching prepared comparison', text)
            self.assertNotIn('#', text)

    def test_effective_qualification_and_incomplete_evidence(self):
        card = NS(league_id='fixture', roster_id=1)
        d = self.diagnostic()
        e = d['teams']['1']['evidence']
        e.update(conclusion_state='provisional', limitations=['Latest refresh did not complete.'])
        self.assertIn('Provisional', weekly_comparison(card, 9, diagnostics=d))
        self.assertIn('Latest refresh did not complete.', weekly_comparison(card, 9, diagnostics=d))
        e['calculation_supported'] = False
        self.assertNotIn('#1', weekly_comparison(card, 9, diagnostics=d))
        self.assertNotIn('153.34', weekly_comparison(card, 9, diagnostics=d))

    def test_rendered_current_availability_aging_and_failed_refresh(self):
        from tests.test_my_team_outlook_http import MyTeamOutlookHTTPTests
        from routes.home import create_home_router
        from fastapi.responses import HTMLResponse
        from src.core.intelligence.roster_diagnostics import diagnostic_store
        f = MyTeamOutlookHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        data = f.data
        reader = f.f.f.source.reader
        for team in data['teams']:
            for p in team['players']:
                p['status'] = 'Active'
                data['players'][p['id']]['status'] = 'Active'
        f.f.publish(datetime.now(timezone.utc).isoformat())
        saved = deepcopy(data['team_strength'])
        f.client.app.include_router(create_home_router(ensure_fresh=AsyncMock(), require_data=lambda: data,
            page=lambda title, body: HTMLResponse(body), generation_provider=lambda: self.id()))

        def pages():
            own = f.client.get('/teams/1')
            home = f.client.get('/')
            self.assertEqual(own.status_code, 200)
            self.assertEqual(home.status_code, 200)
            return (own.text.split('id="my-team-outlook-lead"', 1)[1].split('id="full-roster"', 1)[0],
                    home.text.split('<h2>Projected lineup comparison</h2>', 1)[1].split('Open team assessments', 1)[0])

        current = pages()
        for text in current:
            self.assertIn('slots', text)
            self.assertIn('#', text)
            self.assertNotIn('Provisional', text)
        from src.core.intelligence.roster_diagnostics import prepared_diagnostics
        diag = prepared_diagnostics(data, reader.snapshot())
        points = diag['teams']['1']['optimal_points']
        for text in current:
            self.assertIn(f'{points:.2f}', text)
        # Do not republish the saved horizon: availability alone changes.
        player = data['teams'][0]['players'][0]
        player['status'] = 'Out'
        data['players'][player['id']]['status'] = 'Out'
        changed = pages()
        diag = prepared_diagnostics(data, reader.snapshot())
        for text in changed:
            if diag is None:
                self.assertTrue('matching prepared comparison' in text or 'evidence is not prepared' in text)
                self.assertNotIn('#', text)
            else:
                self.assertIn(f"{diag['teams']['1']['optimal_points']:.2f}", text)
                values = [r['optimal_points'] for r in diag['teams'].values()
                          if r.get('optimal_points') is not None and r['evidence']['calculation_supported']]
                expected = 1 + sum(p > diag['teams']['1']['optimal_points'] for p in values)
                self.assertEqual(tuple(map(int, re.search(r'#(\d+) (?:of|among) (\d+) comparable', text).groups())),
                                 (expected, len(values)))
        self.assertEqual(data['team_strength'], saved)
        # Restore current availability, then requalify the very same publication.
        player['status'] = 'Active'
        data['players'][player['id']]['status'] = 'Active'
        future = datetime.now(timezone.utc) + timedelta(days=10)
        with patch('src.core.intelligence.roster_diagnostics._now', return_value=future):
            for text in pages():
                self.assertIn('Provisional', text)
                self.assertIn('retained numerical evidence is provisional', text)
                self.assertIn(f'{points:.2f}', text)
        with patch.object(reader, 'refresh_evidence', return_value={'retained_publication': True}):
            for text in pages():
                self.assertIn('Provisional', text)
                self.assertIn('latest refresh did not complete', text)
                self.assertIn(f'{points:.2f}', text)
        self.assertEqual(data['team_strength'], saved)
        self.assertIn('validated overall team grade', MODEL_NOTE)
        # A prepared-cache miss never runs an optimizer to render the page.
        with patch.object(diagnostic_store, 'get', return_value=None):
            for index, text in enumerate(pages()):
                lead = text.split('</summary>', 1)[0] if index == 0 else text
                if index == 0:
                    self.assertIn('Comparison pending:', lead)
                    self.assertIn('current availability and source evidence need matching preparation', lead)
                else:
                    self.assertIn('This week’s lineup comparison is not ready.', lead)
                    self.assertIn('Current projections and player availability are needed.', lead)
                self.assertNotIn('#', lead)

    def test_rendered_incomplete_lineup_retains_known_coverage_on_both_surfaces(self):
        from tests.test_my_team_outlook_http import MyTeamOutlookHTTPTests
        from routes.home import create_home_router
        from fastapi.responses import HTMLResponse
        f = MyTeamOutlookHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        data = f.data
        data['league']['roster_positions'] = ['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'FLEX', 'K', 'DEF']
        diagnostic = self.diagnostic()
        diagnostic.update(league_id=data['league']['league_id'], week=data['week'])
        diagnostic['teams']['1'].update(optimal_points=None, optimal_ids=list(range(9)),
            lineup_limitations=['Required starting positions lack compatible eligible projections: DEF.'])
        diagnostic['teams']['1']['evidence'].update(conclusion_state='unavailable')
        diagnostic['teams']['2'] = dict(optimal_points=140, optimal_ids=list(range(10)),
            evidence=dict(calculation_supported=True, conclusion_state='current', limitations=[]))
        f.client.app.include_router(create_home_router(ensure_fresh=AsyncMock(), require_data=lambda: data,
            page=lambda title, body: HTMLResponse(body), generation_provider=lambda: self.id()))
        # Inject an already-prepared diagnostic at the presentation boundary.
        # These are disposable contracts, not a claim of live league coverage.
        with patch('routes.teams.prepared_comparison', return_value=diagnostic), patch(
                'services.team_headquarters.prepared_comparison', return_value=diagnostic):
            own = f.client.get('/teams/1')
            home = f.client.get('/')
        self.assertEqual(own.status_code, 200)
        self.assertEqual(home.status_code, 200)
        lead = own.text.split('id="my-team-outlook-lead"', 1)[1].split('</summary>', 1)[0]
        detail = own.text.split('id="my-team-outlook"', 1)[1].split('id="full-roster"', 1)[0]
        home_comparison = home.text.split('<h2>Projected lineup comparison</h2>', 1)[1].split('Open team assessments', 1)[0]
        # Home also has a complete second team. Isolate the incomplete first row.
        first_home = home_comparison.split('Team 1</a>:', 1)[1].split('</p>', 1)[0]
        for text in [lead, detail, first_home]:
            self.assertIn('9/10 slots covered', text)
            self.assertIn('1 of 2 league teams comparable', text)
            self.assertIn('incomplete', text.lower())
            self.assertNotIn('153.34', text)
            self.assertNotRegex(text, r'#\d+ (?:of|among) \d+ comparable')
        for text in [detail, first_home]:
            self.assertIn('prepared but the legal lineup is incomplete', text)
            self.assertIn('total and rank are withheld', text)
            self.assertIn('DEF', text)
            self.assertNotIn('matching prepared comparison is not available', text)
        # Never invent a particular missing slot when no limitation names it.
        diagnostic['teams']['1']['lineup_limitations'] = []
        text = weekly_comparison(NS(league_id=data['league']['league_id'], roster_id=1),
                                 data['week'], diagnostics=diagnostic)
        self.assertNotIn('DEF', text)
        self.assertIn('9/10', text)
