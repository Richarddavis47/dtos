"""Bounded full-page capture preserves the native screenshot's exact pixels."""
from io import BytesIO
from pathlib import Path
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch
import zlib

from PIL import Image
from playwright.sync_api import sync_playwright

from tools.inspection.png_stream import _first_row, _parts, _scanlines, full_page_screenshot


class DinsPngStreamTests(unittest.TestCase):
    def test_strip_boundary_preserves_all_five_native_filter_types(self):
        for channels in (3, 4):
            raw = bytes((index * 79) % 256 for index in range(channels * 7))
            for kind in range(5):
                encoded = bytearray()
                for index, value in enumerate(raw):
                    left = raw[index - channels] if index >= channels else 0
                    predictor = left if kind in (1, 4) else left // 2 if kind == 3 else 0
                    encoded.append((value - predictor) & 255)
                self.assertEqual(_first_row(bytes([kind]) + encoded, channels), b'\0' + raw)

    def test_scanline_inflation_memory_is_independent_of_strip_height(self):
        width, height = 1440, 10000
        row = b'\0' + b'\xff' * (width * 4)
        compressor = zlib.compressobj()
        compressed = b''.join(compressor.compress(row) for _ in range(height)) + compressor.flush()
        # Several IDAT boundaries can split a deflate block or scanline anywhere.
        chunks = [(b'IDAT', memoryview(compressed)[i:i + 37]) for i in range(0, len(compressed), 37)]
        tracemalloc.start()
        try:
            count = 0
            for result in _scanlines(chunks, width, height, 4):
                self.assertEqual(result, row)
                count += 1
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(count, height)
        self.assertLess(peak, 256 * 1024)

    def test_corrupt_checksum_truncated_stream_and_extra_rows_fail_closed(self):
        output = BytesIO()
        with Image.new('RGB', (8, 2), 'green') as image:
            image.save(output, format='PNG')
        corrupt = bytearray(output.getvalue())
        corrupt[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            _parts(bytes(corrupt))
        compressed = zlib.compress(b'\0' + b'\0' * 24)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            list(_scanlines([(b'IDAT', compressed[:-2])], 8, 1, 3))
        with self.assertRaisesRegex(ValueError, 'row count'):
            list(_scanlines([(b'IDAT', zlib.compress((b'\0' + b'\0' * 24) * 2))], 8, 1, 3))

    def test_dom_change_rejects_capture_without_replacing_last_valid_png(self):
        class Page:
            reads = 0

            def content(self):
                self.reads += 1
                return str(self.reads)

            def evaluate(self, script):
                return {'width': 8, 'height': 10}

            def screenshot(self, **options):
                output = BytesIO()
                with Image.new('RGBA', (8, 10), 'green') as image:
                    image.save(output, format='PNG')
                return output.getvalue()

        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'full.png'
            target.write_bytes(b'last valid fixture')
            with self.assertRaisesRegex(ValueError, 'Page changed'):
                full_page_screenshot(Page(), target, strip_height=10)
            self.assertEqual(target.read_bytes(), b'last valid fixture')
            self.assertEqual(list(Path(folder).glob('*.tmp')), [])

    def test_native_pixel_equivalence_for_viewports_sticky_fixed_and_scale(self):
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                for width, height, scale in ((1440, 1200, 1), (1024, 1366, 1), (390, 844, 1), (391, 301, 2)):
                    with self.subTest(width=width, scale=scale):
                        page = browser.new_page(viewport={'width':width, 'height':height}, device_scale_factor=scale, color_scheme='dark', reduced_motion='reduce')
                        try:
                            page.set_content('''<style>body{margin:0;background:linear-gradient(#07131a,#16481c);color:white;font:16px Arial}header{position:fixed;top:0;left:0;right:0;background:#2229;height:30px;z-index:9}.sticky{position:sticky;top:30px;background:blue}article{height:235px;padding:12px;border:1px solid lime;box-shadow:inset 0 0 15px #88f8}footer{height:111px}</style><header>Fixed Header</header><main>'''+''.join(f'<article><h2>Card {i}</h2><div class="sticky">Sticky {i}</div><svg width="100" height="60"><circle cx="30" cy="30" r="28" fill="lime"/></svg><p>Text and geometry evidence.</p></article>' for i in range(11))+'<footer>Last pixel</footer></main>')
                            with Image.open(BytesIO(page.screenshot(full_page=True))) as native:
                                expected = native.convert('RGBA')
                            target = Path(folder) / 'full.png'
                            original_bytes = Image.Image.tobytes

                            def bounded_bytes(image, *args, **kwargs):
                                self.assertEqual(image.height, 1, 'Encoding copied an entire strip')
                                return original_bytes(image, *args, **kwargs)

                            with patch.object(page, 'screenshot', wraps=page.screenshot) as screenshots, patch.object(Image.Image, 'tobytes', bounded_bytes), patch.object(Image, 'open', side_effect=AssertionError('Decoded image allocation')):
                                full_page_screenshot(page, target, strip_height=height, device_scale_factor=scale)
                            clips = [call.kwargs['clip'] for call in screenshots.call_args_list]
                            self.assertGreater(len(clips), 1)
                            self.assertLessEqual(max(clip['height'] for clip in clips), height)
                            self.assertEqual(sum(clip['height'] for clip in clips) * scale, expected.height)
                            with Image.open(target) as actual:
                                self.assertEqual(actual.size, expected.size)
                                self.assertEqual(actual.convert('RGBA').tobytes(), expected.tobytes())
                            self.assertEqual(page.evaluate('scrollY'), 0)
                            expected.close()
                        finally:
                            page.close()
            finally:
                browser.close()

    def test_failure_preserves_existing_png_and_removes_unpublished_temporary(self):
        class Page:
            def content(self):
                return 'stable fixture'

            def evaluate(self, script):
                return {'width':8, 'height':35}

            def screenshot(self, **options):
                self_options = options['clip']
                if self_options['y']:
                    raise RuntimeError('strip failed')
                self.assert_options = options
                output = BytesIO()
                Image.new('RGBA', (8, 10), 'green').save(output, format='PNG')
                return output.getvalue()

        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'full.png'
            target.write_bytes(b'last valid fixture')
            page = Page()
            with self.assertRaisesRegex(RuntimeError, 'strip failed'):
                full_page_screenshot(page, target, strip_height=10)
            self.assertEqual(target.read_bytes(), b'last valid fixture')
            self.assertEqual(list(Path(folder).glob('*.tmp')), [])
            self.assertEqual(page.assert_options, {'full_page':True, 'clip':{'x':0, 'y':0, 'width':8, 'height':10}})
