import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chat_read import route, execute

class ChatReadTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "approved_canon": [{"candidate_id": "CAND-000001", "kind": "character",
                                "content": "Approved"}],
            "pending_not_canon": [{"candidate_id": "CAND-000002", "kind": "character",
                                  "content": "Not approved"}],
            "rejected_not_canon": [],
            "pending_revisions_not_canon": [],
        }

    def test_routes(self):
        self.assertEqual(route("制作状況"), "dashboard")
        self.assertEqual(route("確認待ち"), "inbox")
        self.assertEqual(route("執筆進捗"), "progress")
        self.assertEqual(route("人物設定"), "canon")

    def test_canon_is_approved_only(self):
        result = execute("人物設定", canon_context=self.context)
        self.assertEqual(result["route"], "canon")
        self.assertEqual(result["result"]["total"], 1)
        self.assertNotIn("Not approved", str(result))
        self.assertFalse(result["approval_performed"])

    def test_project_summary_dispatch(self):
        with patch("chat_read.compact", return_value={"read_only": True}) as mocked:
            result = execute("制作状況", project_data={})
        self.assertEqual(result["route"], "dashboard")
        mocked.assert_called_once_with("dashboard", {}, 20, 0)

    def test_unknown_and_write_requests_rejected(self):
        for message in ("人物設定を変更", "設定を承認", "人物設定と世界設定", "原稿を表示", ""):
            with self.subTest(message=message), self.assertRaises(ValueError):
                route(message)

    def test_pagination(self):
        result = execute("正式設定", canon_context=self.context, limit=1)
        self.assertEqual(result["result"]["limit"], 1)

if __name__ == "__main__":
    unittest.main()
