import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chat_canon_japanese import resolve, lookup

class ChatCanonJapaneseTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "approved_canon": [
                {"candidate_id": "CAND-000001", "kind": "character", "content": "Approved"},
                {"candidate_id": "CAND-000002", "kind": "setting", "content": "Approved setting"}],
            "pending_not_canon": [
                {"candidate_id": "CAND-000003", "kind": "character", "content": "Secret pending"}],
            "rejected_not_canon": [],
            "pending_revisions_not_canon": [],
        }

    def test_aliases(self):
        self.assertIsNone(resolve("正式設定"))
        self.assertEqual(resolve("人物設定"), "character")
        self.assertEqual(resolve("世界設定"), "setting")

    def test_character_lookup_approved_only(self):
        result = lookup("人物設定", self.context)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["content"], "Approved")
        self.assertNotIn("Secret pending", str(result))
        self.assertTrue(result["is_approved_canon"])
        self.assertFalse(result["approval_performed"])

    def test_unknown_and_mutation_requests_rejected(self):
        for message in ("設定を変更して", "人物設定を承認して", "人物設定と世界設定", ""):
            with self.subTest(message=message), self.assertRaises(ValueError):
                resolve(message)

    def test_pagination(self):
        result = lookup("正式設定", self.context, limit=1)
        self.assertEqual(result["total"], 2)
        self.assertTrue(result["has_more"])

if __name__ == "__main__":
    unittest.main()
