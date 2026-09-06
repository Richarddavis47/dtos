import os
from io import BytesIO
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from playwright.sync_api import sync_playwright
from tools.validation import browser_fixture_images as images


class FixtureImagesTests(unittest.TestCase):
    def test_every_canonical_synthetic_id_has_prepared_transport(self):
        bank = set(images.prepared_ids())
        for identity in ("10213", *(f"v{i:05d}" for i in range(2, 12323))):
            self.assertIn(images.prepared_identity(identity), bank)
        for identity in bank:
            self.assertEqual(images.prepared_identity(identity), identity)
        with self.assertRaises(ValueError):
            images.prepared_identity("v12323")

    def test_unprepared_market_assets_decode_without_external_fallback(self):
        identities = ("v00251", "v05000", "v10001", "v12322")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for identity in identities:
                mapped = images.prepared_identity(identity)
                (root / f"{mapped}.jpg").write_bytes(images.image_bytes(mapped))
            page = Mock()
            with patch.dict(os.environ, {"DTOS_PRODUCTION_SHAPED_FIXTURE": "1", "RENDER": ""}):
                evidence = images.install(page, fixture_origin="http://dtos.fixture", directory=root)
            callback = page.route.call_args.args[1]
            for identity in identities:
                route = Mock()
                route.request.url = f"https://sleepercdn.com/content/nfl/players/{identity}.jpg"
                route.request.method = "GET"
                with patch.object(images, "image_bytes", side_effect=AssertionError("request-time encoding")):
                    callback(route)
                route.fallback.assert_not_called()
                route.abort.assert_not_called()
                with Image.open(BytesIO(route.fulfill.call_args.kwargs["body"])) as image:
                    image.load()
                    self.assertEqual(image.size, (350, 254))
            self.assertEqual(set(evidence["requested_ids"]), set(identities))
            route.request.url = "https://sleepercdn.com/content/nfl/players/v12323.jpg"
            callback(route)
            route.abort.assert_called_once_with("blockedbyclient")
            route.fallback.assert_not_called()

    def test_prepared_transport_is_byte_identical_and_does_not_encode_on_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(images, "prepared_ids", return_value=("v00002",)):
                images.prepare(root)
            self.assertEqual((root / "v00002.jpg").read_bytes(), images.image_bytes("v00002"))
            page = Mock()
            route = Mock()
            route.request.url = "https://sleepercdn.com/content/nfl/players/v00002.jpg"
            route.request.method = "GET"
            with patch.dict(os.environ, {"DTOS_PRODUCTION_SHAPED_FIXTURE": "1", "RENDER": ""}):
                images.install(page, fixture_origin="http://dtos.fixture", directory=root)
            callback = page.route.call_args.args[1]
            with patch.object(images, "image_bytes", side_effect=AssertionError("request-time encoding")):
                callback(route)
            self.assertEqual(route.fulfill.call_args.kwargs["body"], (root / "v00002.jpg").read_bytes())

    def test_exact_allowlist_never_matches_real_or_unknown_requests(self):
        base = "https://sleepercdn.com/content/nfl/players/"
        self.assertEqual(images.fixture_id(base + "v00002.jpg"), "v00002")
        for value in ("v00001.jpg", "v12323.jpg", "4984.jpg", "v00002.jpg?secret=x", "../v00002.jpg"):
            self.assertIsNone(images.fixture_id(base + value))
        self.assertIsNone(images.fixture_id(base.replace("sleepercdn.com", "example.org") + "v00002.jpg"))

    def test_real_deterministic_headshot_workload_not_empty_placeholder(self):
        payload = images.image_bytes("v00002")
        self.assertEqual(payload, images.image_bytes("v00002"))
        self.assertNotEqual(payload, images.image_bytes("v00003"))
        self.assertGreater(len(payload), 26835)
        self.assertLess(len(payload), 128 * 1024)
        with Image.open(BytesIO(payload)) as image:
            image.load()
            self.assertEqual(image.size, (350, 254))
            self.assertEqual(image.mode, "P")
            self.assertEqual(image.format, "PNG")
            with image.convert("RGBA") as rgba:
                self.assertGreaterEqual(sum(rgba.getchannel("A").histogram()[1:]), 37323)

    def test_production_and_nonfixture_activation_fail_closed(self):
        for env, origin in (({}, "http://dtos.fixture"),
                            ({"RENDER": "true", "DTOS_PRODUCTION_SHAPED_FIXTURE": "1"}, "http://dtos.fixture"),
                            ({"DTOS_PRODUCTION_SHAPED_FIXTURE": "1"}, "https://dtos.onrender.com")):
            with patch.dict(os.environ, env, clear=True), self.assertRaises(RuntimeError):
                images.install(Mock(), fixture_origin=origin)

    def test_representative_cards_decode_and_bad_html_still_fails(self):
        with patch.dict(os.environ, {"DTOS_PRODUCTION_SHAPED_FIXTURE": "1", "RENDER": ""}), sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                for width in (390, 1440):
                    page = browser.new_page(viewport={"width": width, "height": 900})
                    failures = []
                    page.on("requestfailed", lambda request: failures.append(request.failure))
                    evidence = images.install(page, fixture_origin="http://dtos.fixture")
                    ids = [*range(2, 24), *range(12313, 12323)]
                    page.set_content(''.join(f'<img width="100" src="https://sleepercdn.com/content/nfl/players/v{i:05d}.jpg">' for i in ids))
                    page.evaluate("async () => { await Promise.all([...document.images].map(i=>i.decode())); }")
                    self.assertEqual(page.evaluate("[...document.images].filter(i=>i.naturalWidth===350&&i.naturalHeight===254).length"), len(ids))
                    self.assertEqual(failures, [])
                    self.assertEqual(evidence["responses"], len(ids))
                    with tempfile.TemporaryDirectory() as folder:
                        path = Path(folder) / "cards.png"
                        page.screenshot(path=str(path), full_page=True)
                        self.assertGreater(path.stat().st_size, 10000)
                    page.route("https://negative.fixture/bad.jpg", lambda route: route.fulfill(status=403, content_type="text/html", body="<html>Denied</html>", headers={"X-Content-Type-Options": "nosniff"}))
                    with page.expect_response("https://negative.fixture/bad.jpg") as rejected:
                        self.assertTrue(page.evaluate("async () => {const i=new Image();i.src='https://negative.fixture/bad.jpg';document.body.append(i);try{await i.decode();return false}catch{return i.naturalWidth===0}}"))
                    # HTTP errors produce responses, not necessarily the transport
                    # requestfailed event. Neither the 403 nor decode failure hides.
                    self.assertEqual(rejected.value.status, 403)
                    page.close()
            finally:
                browser.close()
