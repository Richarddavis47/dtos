"""Public intelligence APIs must work independently of unittest discovery order."""
import subprocess
import sys
import unittest


class IntelligenceImportOrderTests(unittest.TestCase):
    def test_trade_and_unified_api_import_in_either_order(self):
        statements = (
            "from src.core.trade_intelligence import TradeAsset; from src.core.intelligence import IntelligenceOrchestrator",
            "from src.core.intelligence import IntelligenceOrchestrator; from src.core.trade_intelligence import TradeAsset",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                result = subprocess.run([sys.executable, "-c", statement], capture_output=True,
                    text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
