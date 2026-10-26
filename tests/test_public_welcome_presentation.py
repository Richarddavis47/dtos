"""Public presentation consumes only the reviewed fictional fixture."""
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from src.ui.public_welcome import render_welcome


class PublicDocument(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.text = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, value):
        self.text.append(value)


class PublicWelcomePresentationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((Path(__file__).resolve().parents[1] / 'src/ui/public_demo_data.json').read_text())

    def test_one_public_document_has_three_disclosures_and_existing_destinations(self):
        source = render_welcome(self.fixture)
        doc = PublicDocument(source)
        self.assertEqual(source.count('<!doctype html>'), 1)
        self.assertEqual(sum(tag == 'h1' for tag, attrs in doc.elements), 1)
        self.assertIn(('html', {'lang': 'en'}), doc.elements)
        self.assertEqual(next(attrs for tag, attrs in doc.elements if tag == 'main')['id'], 'main')
        demos = [attrs for tag, attrs in doc.elements if tag == 'details' and attrs.get('class') == 'pw-demo']
        self.assertEqual([row['id'] for row in demos], ['demo-team', 'demo-trade', 'demo-values'])
        self.assertIn('open', demos[0])
        self.assertNotIn('open', demos[1])
        self.assertNotIn('open', demos[2])
        # Negative tabindex on details suppresses native summary Tab stops in Chromium.
        self.assertFalse(any((attrs.get('tabindex') or '').startswith('-')
                             for tag, attrs in doc.elements if tag == 'details'))
        self.assertFalse(any(tag in {'script', 'form', 'input', 'iframe', 'img', 'video'} for tag, attrs in doc.elements))
        self.assertFalse(any(key.startswith('on') for tag, attrs in doc.elements for key in attrs))
        destinations = {attrs['href'] for tag, attrs in doc.elements if tag == 'a'}
        self.assertEqual(destinations, {'#main', '#demo', '#demo-team', '#demo-trade', '#demo-values',
                                        '/welcome', '/account/sign-in', '/account/create', '/account/recover'})
        self.assertNotIn('/api/', source)
        self.assertNotIn('dtos_session', source)
        self.assertNotIn('csrf_token', source)
        self.assertLessEqual(len(source.encode('utf-8')), 65_536)

    def test_frozen_facts_and_public_qualification_are_visible_without_a_script(self):
        source = render_welcome(self.fixture)
        doc = PublicDocument(source)
        text = ' '.join(doc.text)
        for title in ('Understand Your Team', 'Make Better Trades', 'Build Your Own DTOS',
                      'You Send', 'You Receive', 'Neutral DTOS', 'Custom DTOS'):
            self.assertIn(title, text)
        self.assertEqual(source.count('Demonstration data · fictional league · not current player advice.'), 3)
        self.assertIn('same hypothetical offer', text)
        self.assertIn(self.fixture['team']['name'], text)
        for side in ('active', 'partner'):
            self.assertIn(self.fixture['trade'][side]['name'], text)
            self.assertIn(self.fixture['trade'][side]['benefit'], text)
            self.assertIn(self.fixture['trade'][side]['cost'], text)
        self.assertIn(self.fixture['trade']['qualification'], text)
        self.assertIn(self.fixture['personal']['cohort_label'], text)
        self.assertIn('Unpriced future picks remain capital facts', text)
        self.assertIn(f"Week {self.fixture['week']}: projected lineup #{self.fixture['team']['comparison_rank']}", text)
        self.assertIn('This is not official standing.', text)
        for pick in self.fixture['team']['capital']:
            self.assertIn(pick['label'], text)
            self.assertIn(pick['original_franchise'], text)
            self.assertIn(pick['current_owner'], text)
        self.assertIn('Account creation is available.', text)
        self.assertIn('controlled beta with limited capacity', text)
        self.assertIn('not a prediction that the other manager will accept', text)
        self.assertNotIn('invite-only', text.lower())

    def test_mapping_render_is_deterministic_independent_and_starts_no_io(self):
        before = deepcopy(self.fixture)
        with patch('pathlib.Path.read_text', side_effect=AssertionError('No source read for explicit frozen data')), \
             patch('socket.create_connection', side_effect=AssertionError('No network')), \
             patch('sqlite3.connect', side_effect=AssertionError('No persistent access')):
            first = render_welcome(self.fixture)
            for _ in range(8):
                self.assertEqual(render_welcome(self.fixture), first)
        self.assertEqual(self.fixture, before)

    def test_zero_is_not_missing_and_missing_does_not_become_a_numeric_price(self):
        data = deepcopy(self.fixture)
        data['trade']['market_sent'] = 0
        data['trade']['market_received'] = None
        data['personal']['neutral_sent'] = 0
        data['personal']['personal_sent'] = None
        data['team']['lineup_points'] = 0
        data['team']['comparison_rank'] = None
        source = render_welcome(data)
        self.assertIn('<b class="pw-number">0</b><span class="pw-metric-label">Strongest legal lineup', source)
        self.assertIn('<b class="pw-number">0</b><span class="pw-metric-label">You send', source)
        self.assertIn('<b class="pw-number">Unavailable</b><span class="pw-metric-label">You receive', source)
        self.assertIn('<dt>You Send</dt><dd>0</dd>', source)
        self.assertIn('<dt>You Send</dt><dd>Unavailable</dd>', source)
        self.assertNotIn('>None<', source)
        self.assertIn('A comparative lineup rank is unavailable for this example.', source)

    def test_all_fixture_labels_are_escaped_and_do_not_create_active_content(self):
        data = deepcopy(self.fixture)
        value = '<script>alert("fixture")</script><img src=x onerror=alert(1)>'
        data['team']['name'] = value
        data['team']['reserve'][0]['name'] = value
        data['trade']['send'][0]['name'] = value
        data['personal']['before_order'][0]['label'] = value
        source = render_welcome(data)
        doc = PublicDocument(source)
        self.assertFalse(any(tag in {'script', 'img'} for tag, attrs in doc.elements))
        self.assertIn('&lt;script&gt;', source)
        self.assertNotIn('<img src=x', source)


if __name__ == '__main__':
    unittest.main()
