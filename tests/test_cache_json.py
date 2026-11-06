"""Sharing immutable text must not change retained evidence or its ownership."""
from __future__ import annotations

import gc
from io import StringIO
import json
import math
import unittest
from unittest.mock import patch
import weakref

from src.platform import cache_json


class CacheJSONTests(unittest.TestCase):
    def load(self, text):
        return cache_json.load_cache_json(StringIO(text))

    def test_identical_short_values_share_across_nested_source_and_disclosure(self):
        text = '{"source":{"league":"fixture-league-long"},"disclosure":[["fixture-league-long"],{"league":"fixture-league-long"}]}'
        value = self.load(text)
        self.assertEqual(value, json.loads(text))
        self.assertIs(value['source']['league'], value['disclosure'][0][0])
        self.assertIs(value['source']['league'], value['disclosure'][1]['league'])

    def test_equal_mutable_containers_do_not_share_and_scores_remain_exact(self):
        row = {'points': [0, -2.125, 23.4738, None], 'provenance': {'source': 'Sleeper fixture'}}
        value = self.load(json.dumps({'before': row, 'after': row}))
        self.assertEqual(value, {'before': row, 'after': row})
        self.assertIsNot(value['before'], value['after'])
        self.assertIsNot(value['before']['points'], value['after']['points'])
        value['before']['points'][0] = 99
        value['before']['provenance']['source'] = 'changed disclosure'
        self.assertEqual(value['after'], row)

    def test_unicode_escaping_duplicate_keys_and_numeric_types_match_stdlib(self):
        text = '{"text":"\\u00e9\\ud83c\\udfc8","other":["é🏈"],"dup":1,"dup":2,"int":9007199254740993,"negative_zero":-0.0,"bool":false,"null":null}'
        value = self.load(text)
        self.assertEqual(value, json.loads(text))
        self.assertIs(value['text'], value['other'][0])
        self.assertIs(type(value['int']), int)
        self.assertEqual(math.copysign(1, value['negative_zero']), -1)

    def test_invalid_input_has_the_same_decode_error(self):
        for text in ('{"unfinished":', '[1,]', '{"bad":"\\x"}'):
            with self.subTest(text=text), self.assertRaises(json.JSONDecodeError):
                self.load(text)

    def test_existing_nonfinite_json_behavior_is_not_changed_into_a_score(self):
        value = self.load('[NaN, Infinity, -Infinity]')
        self.assertTrue(math.isnan(value[0]))
        self.assertEqual(value[1:], [math.inf, -math.inf])
        from src.core.player_value_projection.sleeper_actuals import score_number
        self.assertTrue(all(score_number(item) is None for item in value))

    def test_length_entry_and_character_limits_are_bounded(self):
        strings = cache_json._Strings()
        strings.MAX_ENTRIES = 2
        strings.MAX_CHARACTER_BYTES = 40
        for value in ('', 'x', 'x' * 129):
            self.assertIs(strings.share(value), value)
        strings.share('ab')
        strings.share('cdefghij')
        self.assertEqual(len(strings.values), 2)
        self.assertEqual(strings.character_bytes, 40)
        strings.share('not admitted')
        self.assertEqual(len(strings.values), 2)
        strings = cache_json._Strings()
        strings.MAX_CHARACTER_BYTES = 4
        strings.share('too long')
        self.assertFalse(strings.values)

    def test_pool_is_released_on_success_and_failure_without_global_interning(self):
        references = []
        real = cache_json._Strings
        def make():
            value = real()
            references.append(weakref.ref(value))
            return value
        with patch.object(cache_json, '_Strings', side_effect=make):
            first = self.load('{"scope":"distinct-fixture-league-scope"}')
            second = self.load('{"scope":"distinct-fixture-league-scope"}')
            with self.assertRaises(json.JSONDecodeError):
                self.load('{"broken":')
        gc.collect()
        self.assertTrue(all(ref() is None for ref in references))
        self.assertEqual(first, second)
        self.assertIsNot(first['scope'], second['scope'])

    def test_root_arrays_primitives_and_long_unique_text_keep_stdlib_values(self):
        for source in ([['repeat-scope', 'repeat-scope']], 'a' * 1000, 0, None, True):
            text = json.dumps(source)
            self.assertEqual(self.load(text), json.loads(text))

    def test_fresh_atomic_writer_keeps_full_expanded_admission_basis(self):
        from datetime import datetime, timezone
        from pathlib import Path
        import tempfile
        from services import sleeper
        from src.platform import cache_budget
        child = {'scope': 'same immutable scoped source', 'points': [0, -2.125, 23.4738]}
        state = {'data': {'league': {'league_id': 'fixture-cache'}, 'a': child, 'b': child},
                 'last_sync': datetime.now(timezone.utc).isoformat()}
        expected = json.dumps(state, separators=(',', ':'), ensure_ascii=False).encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'cache.json'
            with patch.object(sleeper, 'league_cache_file', return_value=path), \
                    patch.object(cache_budget, 'json_admission', wraps=cache_budget.json_admission) as admission:
                sleeper.save_cache(state=state, league_id='fixture-cache')
            self.assertEqual(path.read_bytes(), expected)
            self.assertEqual(admission.call_args.args[2], len(expected))
            restored = {}
            with patch.object(sleeper, 'league_cache_file', return_value=path):
                sleeper.load_cache(state=restored, league_id='fixture-cache')
            self.assertEqual(restored['data'], state['data'])
            self.assertIsNot(restored['data']['a'], restored['data']['b'])
