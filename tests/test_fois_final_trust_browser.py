"""Actual FOIS routes at phone and desktop sizes; controlled evidence only."""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.front_offices import create_front_offices_router
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult
from src.core.front_office_intelligence import build_league_model
from tests import test_fois_presentation as fois
from tests import test_fois_trust_browser as trust_browser
from tests.test_trade_intelligence import fixture_data


class FinalTrustBrowserTests(unittest.TestCase):
    def test_real_retained_category_only_and_unavailable_profiles(self):
        import dtos_app
        fixture = fois.FOISPresentationTests()
        fixture.setUp()
        try:
            score = FOISEngine().evaluate(FOISFacts('active-league', 'active-league:franchise:1', 'owner',
                tuple(SeasonResult(2023+n, 9, 5, 4, playoff=True, league_size=10) for n in range(3)),
                gm_id='category-gm', gm_name='Category Evidence Manager'))
            fixture.repository.save(replace(score, strengths=()), 'retained-generation')
            with fixture.repository._connection() as connection:
                payload = json.loads(connection.execute('SELECT payload FROM fois_scores_v2').fetchone()[0])
                payload.pop('evidence_integrity_version')
                connection.execute('UPDATE fois_scores_v2 SET payload=?', (json.dumps(payload),))
                connection.commit()
                before = [tuple(row) for row in connection.execute('SELECT * FROM fois_scores_v2')]
            empty = FOISEngine().evaluate(FOISFacts('active-league', 'active-league:franchise:2', 'other-owner', (), gm_id='empty-gm', gm_name='No History Manager'))
            fixture.repository.save(empty, 'empty-generation')
            with patch.object(fois, '_page', side_effect=dtos_app.page), fixture._client() as client:
                pages = {f'/fois/gms/{gm}': client.get(f'/fois/gms/{gm}').text for gm in ('category-gm', 'empty-gm')}
            def check(page, path, width):
                text = page.inner_text('[data-fois-strengths]')
                if path.endswith('category-gm'):
                    self.assertIn('Results findings are supported', text)
                    self.assertIn('overall strongest area', text)
                    self.assertIn('have not been revalidated', page.inner_text('body'))
                    self.assertIn(str(score.category_scores[0].normalized_score), page.inner_text('.card-grid'))
                    self.assertIn('3', page.inner_text('.card-grid'))
                else:
                    self.assertIn('accomplishments are unavailable', text)
                self.assertNotIn('No evidence-supported strength is established yet', text)
                control = page.get_by_text('Supporting evidence and limitations', exact=True)
                control.focus()
                page.keyboard.press('Enter')
                self.assertTrue(control.evaluate('e=>e.parentElement.open'))
                self.assertNotEqual(control.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                self.assertIn('Evidence confidence, not manager quality', page.inner_text('body'))
                page.keyboard.press('Enter')
                self.assertFalse(control.evaluate('e=>e.parentElement.open'))
            trust_browser.FOISTrustBrowserTests().inspect(pages, check)
            with fixture.repository._connection() as connection:
                after = [tuple(row) for row in connection.execute('SELECT * FROM fois_scores_v2')]
            self.assertIn(before[0], after)
        finally:
            fixture.tearDown()

    def test_actual_front_offices_without_complementary_needs(self):
        import dtos_app
        data = fixture_data()
        model = build_league_model(data)
        reports = {key: replace(row, decision=replace(row.decision, position_evaluations={k: replace(v, score=65) for k,v in row.decision.position_evaluations.items()})) for key,row in model.reports.items()}
        from src.core.front_office_intelligence.engine import _compatibility
        pairs = {key: _compatibility(data, reports[key[0]], reports[key[1]]) for key in model.compatibilities}
        model = replace(model, reports=reports, compatibilities=pairs)
        async def noop():
            return None
        app = FastAPI()
        app.include_router(create_front_offices_router(ensure_fresh=noop, require_data=lambda: data, page=dtos_app.page))
        from src.core.intelligence import intelligence_orchestrator
        intelligence = intelligence_orchestrator.analyze(data, 1)
        with patch('services.front_office_intelligence.intelligence_orchestrator.analyze', return_value=replace(intelligence, front_office_model=model)), TestClient(app) as client:
            response = client.get('/front-offices?front_office=1')
        self.assertEqual(response.status_code, 200)
        def check(page, path, width):
            disclosures = page.locator('details')
            for item in disclosures.all():
                item.evaluate('e=>e.open=true')
            text = page.inner_text('body')
            self.assertIn('No specific need-based negotiation angle', text)
            self.assertNotIn('addressing an observed roster need', text)
            self.assertIn('Complementary position needs', text)
            self.assertNotIn('Acceptance: ', text)
            control = page.get_by_text('Show Full Dossier Evidence', exact=True)
            control.focus()
            page.keyboard.press('Enter')
            self.assertFalse(control.evaluate('e=>e.parentElement.open'))
            page.keyboard.press('Enter')
            self.assertTrue(control.evaluate('e=>e.parentElement.open'))
            self.assertNotEqual(control.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
        trust_browser.FOISTrustBrowserTests().inspect({'/front-offices': response.text}, check)
