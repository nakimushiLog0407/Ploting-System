import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chat_canon_page import page

class ChatCanonPageTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "approved_canon": [
                {"candidate_id": "CAND-000001", "kind": "character", "content": "Approved A", "is_canon": True},
                {"candidate_id": "CAND-000002", "kind": "setting", "content": "Approved B", "is_canon": True},
                {"candidate_id": "CAND-000003", "kind": "character", "content": "Approved C", "is_canon": True},
            ],
            "pending_not_canon": [
                {"candidate_id": "CAND-000004", "kind": "character", "content": "Pending", "is_canon": False}],
            "rejected_not_canon": [],
            "pending_revisions_not_canon": [
                {"revision_id": "REV-000001", "candidate_id": "CAND-000001",
                 "proposed_content_not_canon": "Not approved"}],
        }

    def test_default_is_approved_only(self):
        result = page(self.context)
        self.assertEqual(result["total"], 3)
        self.assertTrue(result["is_approved_canon"])
        self.assertNotIn("Pending", str(result))

    def test_kind_filter_and_pagination(self):
        result = page(self.context, kind="character", limit=1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["items"]), 1)
        self.assertTrue(result["has_more"])
        next_page = page(self.context, kind="character", limit=1, offset=1)
        self.assertEqual(next_page["items"][0]["candidate_id"], "CAND-000003")

    def test_pending_separate_from_canon(self):
        result = page(self.context, group="pending")
        self.assertEqual(result["total"], 1)
        self.assertFalse(result["is_approved_canon"])
        self.assertFalse(result["approval_performed"])

    def test_revisions_cannot_use_kind_filter(self):
        with self.assertRaises(ValueError):
            page(self.context, group="pending_revisions", kind="character")

    def test_invalid_limits_rejected(self):
        for value in (0, 101, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                page(self.context, limit=value)
        with self.assertRaises(ValueError):
            page(self.context, offset=-1)

if __name__ == "__main__":
    unittest.main()
