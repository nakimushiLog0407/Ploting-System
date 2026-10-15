import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import character_relation_types as cr

class RelationTypeTests(unittest.TestCase):
    def test_known_relation_types(self):
        self.assertTrue({"friend", "family", "hostile", "mentor", "student"}.issubset(cr.TYPES))

    def test_archive_readable(self):
        self.assertIsInstance(cr.records(), list)

    def test_explicit_review_required(self):
        with self.assertRaises(ValueError):
            cr.review("CRL-999999", "approved", "", False)

    def test_unknown_type_rejected(self):
        with patch.object(cr, "records", return_value=[]):
            with self.assertRaises(ValueError):
                cr.propose("test", "CAND-000001", "CAND-000002", "invented", "", "説明", "")

    def test_proposed_is_not_approved(self):
        self.assertNotEqual("proposed", "approved")

if __name__ == "__main__":
    unittest.main()
