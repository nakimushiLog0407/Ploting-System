import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chat_query import resolve, execute


class ChatQueryTests(unittest.TestCase):
    def setUp(self):
        self.data = {"candidates": [], "decisions": [], "cards": [], "moves": [],
                     "drafts": [], "revisions": [],
                     "plot_review": {"findings": []}, "prose_review": {"findings": []}}

    def test_supported_japanese_aliases(self):
        self.assertEqual(resolve("制作状況"), "dashboard")
        self.assertEqual(resolve("確認待ち"), "inbox")
        self.assertEqual(resolve("執筆進捗"), "progress")
        self.assertEqual(resolve("承認済み原稿"), "manuscript")

    def test_read_only_query(self):
        result = execute("確認待ち", self.data)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["approval_performed"])
        self.assertEqual(result["data"]["total"], 0)

    def test_unknown_and_write_requests_rejected(self):
        for message in ("設定を承認して", "本文を書き換えて", "進捗と原稿", ""):
            with self.subTest(message=message), self.assertRaises(ValueError):
                resolve(message)

    def test_no_fuzzy_interpretation(self):
        with self.assertRaises(ValueError):
            resolve("制作状況を変更")


if __name__ == "__main__":
    unittest.main()
