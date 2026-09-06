"""Completed DINS geometry must live on disk, not in the manifest accumulator."""
from __future__ import annotations

import gc
import tempfile
import unittest
import weakref
from pathlib import Path
from unittest.mock import patch

from app_metadata import VERSION
from tools.inspection import capture as module


class TrackedPage(dict):
    pass


class DinsCaptureMemoryTests(unittest.TestCase):
    def test_failed_viewports_close_native_resources_and_preserve_failure_evidence(self):
        def response(url):
            if url.endswith('/api/market/health'):
                return {'status': 'ready'}
            if url.endswith('/api/inspect/site-map'):
                return {'pages': [{'page_id': 'home', 'page_name': 'Home', 'route': '/'}]}
            if url.endswith('/api/status'):
                return {'version': VERSION, 'deployment': {'commit': 'fixture'}}
            return {}

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(module, '_json', side_effect=response),
            patch.object(module, '_capture_page', side_effect=RuntimeError('fixture failure')),
            patch.object(module, 'sync_playwright') as playwright,
        ):
            manifest = module.capture('https://dtos.example', Path(folder))
        self.assertEqual(manifest['status'], 'partial')
        self.assertEqual(len(manifest['failures']), len(module.VIEWPORTS))
        launch = playwright.return_value.__enter__.return_value.chromium.launch
        self.assertEqual(launch.return_value.close.call_count, len(module.VIEWPORTS))
        self.assertEqual(playwright.return_value.__exit__.call_count, len(module.VIEWPORTS))

    def test_completed_page_payloads_are_released_without_losing_artifacts(self):
        specs = [dict(page_id=f"page-{i}", page_name=f"Page {i}", route=f"/page-{i}") for i in range(12)]
        refs = []
        retained = []
        write = module._write_artifact_json

        def response(url):
            if url.endswith('/api/market/health'):
                return {'status': 'ready'}
            if url.endswith('/api/inspect/site-map'):
                return {'pages': specs}
            if url.endswith('/api/status'):
                return {'version': VERSION, 'deployment': {'commit': 'fixture'}}
            return {}

        def page(_browser, _store, _base, spec, _viewport, _league):
            (_store.current_root / 'pages' / spec['page_id']).mkdir(parents=True)
            gc.collect()
            retained.append(sum(ref() is not None for ref in refs))
            return {
                'page_id': spec['page_id'], 'viewport': {'name': 'desktop'},
                'metrics': {'product_contract_failures': 0, 'critical_accessibility_count': 0},
                'artifact_urls': {'viewport_screenshot': 'https://dtos.example/a.png', 'full_page_screenshot': 'https://dtos.example/b.png'},
                'interactions': [{'success': False, 'target': '/failure'}],
                'accessibility': {'violations': [{'severity': 'critical', 'rule': 'fixture'}]},
                'network': {'console_errors': ['fixture'], 'failed_requests': [{'url': '/fixture'}]},
                'geometry': {'elements': [{'text': f'row-{i}', 'width': i} for i in range(600)]},
            }

        def tracked_write(path, value, **kwargs):
            normalized = write(path, value, **kwargs)
            if path.name == 'desktop.json':
                normalized = TrackedPage(normalized)
                refs.append(weakref.ref(normalized))
            return normalized

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(module, '_json', side_effect=response),
            patch.object(module, '_capture_page', side_effect=page),
            patch.object(module, '_write_artifact_json', side_effect=tracked_write),
            patch.object(module, 'sync_playwright') as playwright,
            patch.object(module, 'VIEWPORTS', [type('Viewport', (), {'name': 'desktop'})()]),
        ):
            manifest = module.capture('https://dtos.example', Path(folder))
            self.assertEqual(len(list(Path(folder).rglob('desktop.json'))), 12)
            self.assertEqual(manifest['total_pages_completed'], 12)
            for key in ('interaction_failures', 'accessibility_regressions', 'console_errors', 'failed_network_requests'):
                self.assertEqual(len(manifest[key]), 12, key)
            self.assertEqual(len(manifest['screenshot_artifact_urls']), 24)
            self.assertLessEqual(max(retained), 1, 'completed full page payloads accumulated in memory')
            launch = playwright.return_value.__enter__.return_value.chromium.launch
            self.assertEqual(launch.call_count, 12, 'native capture resources span completed viewports')
            self.assertEqual(launch.return_value.close.call_count, 12)
            self.assertEqual(playwright.return_value.__exit__.call_count, 12)
            self.assertTrue(all(call.kwargs == {'headless': True} for call in launch.call_args_list))


if __name__ == '__main__':
    unittest.main()
