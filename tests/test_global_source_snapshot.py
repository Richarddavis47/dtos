import hashlib
import tempfile
import unittest
from pathlib import Path

import httpx

from src.core.data_platform.source_snapshot import download_snapshot


class GlobalSourceSnapshotTests(unittest.TestCase):
    def test_exact_revision_and_cleanup_after_consumer_failure(self):
        body = b"player_id,rec\n00-1,5\n"
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))) as client:
                with self.assertRaisesRegex(RuntimeError, "consumer"):
                    with download_snapshot(client, "https://source.test/stats", directory=directory) as snapshot:
                        self.assertEqual(snapshot.sha256, hashlib.sha256(body).hexdigest())
                        self.assertEqual(snapshot.path.read_bytes(), body)
                        self.assertEqual(snapshot.bytes_downloaded, len(body))
                        raise RuntimeError("consumer")
            self.assertEqual(list(directory.iterdir()), [])

    def test_oversize_or_empty_never_leaves_partial_feed(self):
        for body in (b"x" * 101, b""):
            with self.subTest(size=len(body)), tempfile.TemporaryDirectory() as root:
                directory = Path(root)
                with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))) as client:
                    with self.assertRaises(ValueError):
                        with download_snapshot(client, "https://source.test/stats", directory=directory,
                                               maximum_bytes=100):
                            self.fail("Rejected source was exposed")
                self.assertEqual(list(directory.iterdir()), [])
