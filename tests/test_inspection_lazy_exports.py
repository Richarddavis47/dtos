"""Browser-only capture must not import the server intelligence engine."""
import subprocess
import sys
import unittest


class InspectionLazyExportTests(unittest.TestCase):
    def test_capture_import_does_not_load_unused_server_engine(self):
        result = subprocess.run([sys.executable, '-c',
            "import sys; import tools.inspection.capture; "
            "assert 'src.core.inspection.engine' not in sys.modules"],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_public_exports_preserve_exact_implementation_objects(self):
        import src.core.inspection as inspection
        from src.core.inspection.engine import InspectionEngine
        from src.core.inspection.models import VIEWPORTS
        self.assertIs(inspection.InspectionEngine, InspectionEngine)
        self.assertIs(inspection.VIEWPORTS, VIEWPORTS)
        for name in inspection.__all__:
            self.assertIsNotNone(getattr(inspection, name))
        with self.assertRaises(AttributeError):
            getattr(inspection, 'not_an_export')
