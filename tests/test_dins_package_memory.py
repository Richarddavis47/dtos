"""Packaging must not preload the entire completed DINS capture."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from app_metadata import BUILD_NUMBER, VERSION
from tools.inspection import package


class DinsPackageMemoryTests(unittest.TestCase):
    def test_completed_artifacts_are_written_before_reading_the_next(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture = root / 'capture'
            capture.mkdir()
            (capture / 'manifest.json').write_text(json.dumps({'version': VERSION, 'build': BUILD_NUMBER}))
            for index in range(16):
                (capture / f'{index:02}.png').write_bytes(b'fixture-png' * 1024)
            original_read = Path.read_bytes
            original_write = package.zipfile.ZipFile.writestr
            outstanding = 0
            peak = 0

            def read(path):
                nonlocal outstanding, peak
                if path.suffix == '.png':
                    outstanding += 1
                    peak = max(peak, outstanding)
                return original_read(path)

            def write(archive, info, content, *args, **kwargs):
                nonlocal outstanding
                result = original_write(archive, info, content, *args, **kwargs)
                if info.filename.endswith('.png'):
                    outstanding -= 1
                return result

            with patch.object(Path, 'read_bytes', read), patch.object(package.zipfile.ZipFile, 'writestr', write):
                assets = package.package_bundle(capture, root / 'output')
            self.assertEqual(outstanding, 0)
            self.assertEqual(peak, 1, 'packager retained multiple complete artifact buffers')
            # The previous eager algorithm's exact ordering, permissions,
            # timestamps, content and compression must remain byte-equivalent.
            expected = root / 'expected.zip'
            eager = [('manifest.json', assets['manifest'].read_bytes()), *[
                (path.name, path.read_bytes()) for path in sorted(capture.glob('*.png'))
            ]]
            with zipfile.ZipFile(expected, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for name, content in eager:
                    info = zipfile.ZipInfo(f'dins/{name}', date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, content)
            self.assertEqual(assets['bundle'].read_bytes(), expected.read_bytes())


if __name__ == '__main__':
    unittest.main()
