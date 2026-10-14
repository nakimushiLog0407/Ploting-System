import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from relationship_workflow import effective, review, verify_reviews

class RelationshipWorkflowTests(unittest.TestCase):
    def test_existing_archive_valid(self):
        self.assertEqual(verify_reviews(), 0)
        self.assertEqual(effective("approved"), [])

    def test_explicit_confirmation_required(self):
        with self.assertRaises(ValueError):
            review("REL-000001", "approved", "", False)

    def test_invalid_filter_rejected(self):
        with self.assertRaises(ValueError):
            effective("unknown")

if __name__ == "__main__":
    unittest.main()
