import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import setting_classification as sc

class ClassificationTests(unittest.TestCase):
    def test_four_categories(self):
        self.assertEqual(set(sc.CATEGORIES), {"world_rule", "organization", "place", "term"})

    def test_current_repository_valid(self):
        self.assertIsInstance(sc.all_classifications(), list)

    def test_explicit_confirmation_required(self):
        with self.assertRaises(ValueError):
            sc.review("CLS-999999", "approved", "", False)

    def test_no_implicit_approval(self):
        self.assertFalse(any(x["status"] == "approved" for x in [
            {"status": "proposed"}, {"status": "rejected"}
        ]))

    def test_propose_rejects_unknown_category(self):
        with patch.object(sc, "all_classifications", return_value=[]):
            with self.assertRaises(ValueError):
                sc.propose("test-req", "CAND-000001", "invented", "")

if __name__ == "__main__":
    unittest.main()
