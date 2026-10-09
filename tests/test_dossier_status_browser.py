"""Status typography on actual /players routes, including Scout's Bo Nix case."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.transactions import create_transactions_router
from src.core.data_platform import data_platform
from src.core.data_platform.storage import SnapshotWarehouse
from tests.test_canonical_asset_facts import facts_fixture
from tests import test_technical_details_browser as technical


class DossierStatusBrowserTests(unittest.TestCase):
    def test_actual_bo_nix_dossier_status_cards(self):
        import dtos_app
        data = facts_fixture()
        # Real identity, deliberately absent utility evidence: no fabricated zero.
        data['players']['11563'] = {'full_name': 'Bo Nix', 'position': 'QB', 'team': 'DEN'}
        data['market_data']['providers']['FantasyCalc']['11563'] = deepcopy(data['market_data']['providers']['FantasyCalc']['4984'])
        async def fresh():
            pass
        app = FastAPI()
        app.include_router(create_transactions_router(ensure_fresh=fresh, require_data=lambda: data,
            refresh_transactions=fresh, state={}, page=dtos_app.page))
        with patch.object(data_platform, 'warehouse', SnapshotWarehouse()), TestClient(app) as client:
            response = client.get('/players/11563')
            self.assertEqual(response.status_code, 200)
            numeric = client.get('/players/10225')
            self.assertEqual(numeric.status_code, 200)
        measurements = []
        helper = technical.TechnicalDetailsBrowserTests()
        def inspect(page, width):
            cards = page.locator('article.ai-value')
            self.assertEqual(cards.count(), 4)
            statuses = cards.locator(':scope > b').filter(has_text='Unavailable')
            if page.url.endswith('/11563'):
                self.assertEqual(statuses.count(), 3)
                self.assertEqual(statuses.evaluate_all("rows=>rows.map(el=>el.previousElementSibling.textContent)"),
                    ['Intrinsic dynasty utility', 'Season utility', 'Team-specific fit'])
            else:
                self.assertTrue(any(text.replace('.', '', 1).isdigit() for text in cards.locator(':scope > b').all_text_contents()))
            geometry = statuses.evaluate_all('''rows=>rows.map(el=>{
                const range=document.createRange();range.selectNodeContents(el);
                const style=getComputedStyle(el),card=el.closest('article');
                return {text:el.textContent,lines:[...range.getClientRects()].map(r=>({x:r.x,y:r.y,width:r.width,height:r.height})),
                    cardWidth:card.getBoundingClientRect().width,valueWidth:el.getBoundingClientRect().width,
                    wordBreak:style.wordBreak,overflowWrap:style.overflowWrap,
                    columns:getComputedStyle(card.parentElement).gridTemplateColumns};
            })''')
            measurements.append({'viewport':width,'document':page.evaluate('document.documentElement.scrollWidth'),'values':geometry})
            Path('.validation/dossier-status/geometry.json').parent.mkdir(parents=True,exist_ok=True)
            Path('.validation/dossier-status/geometry.json').write_text(json.dumps(measurements,indent=2))
            capture = os.environ.get('DTOS_DOSSIER_CAPTURE')
            if capture:
                Path(capture).mkdir(parents=True, exist_ok=True)
                cards.first.scroll_into_view_if_needed()
                page.screenshot(path=str(Path(capture) / f'dossier-{page.url.rsplit("/",1)[-1]}-{width}.png'))
            for row in geometry:
                self.assertEqual(row['text'], 'Unavailable')
                self.assertEqual(len({round(line['y'],1) for line in row['lines']}), 1, row)
                for line in row['lines']:
                    self.assertLessEqual(line['x'] + line['width'], width + 1)
            for card in cards.all():
                value = card.locator(':scope > b')
                value_box = value.bounding_box()
                label_box = card.locator(':scope > span').bounding_box()
                self.assertGreaterEqual(value_box['y'], label_box['y'] + label_box['height'])
                self.assertLessEqual(value_box['x'] + value_box['width'], card.bounding_box()['x'] + card.bounding_box()['width'])
                # Real evidence disclosure remains available and inspectable.
                card.locator('summary').first.click()
                self.assertTrue(card.locator('details').first.evaluate('el=>el.open'))
            helper.assert_bounded(page, width)
            print(f'Real dossier {page.url.rsplit("/",1)[-1]}: {width}px, status intact, labels separate, page bounded')
        helper.browse({'/players/11563':response.text, '/players/10225':numeric.text},inspect)
