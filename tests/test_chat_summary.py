import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chat_summary import compact


class ChatSummaryTests(unittest.TestCase):
    def setUp(self):
        self.data = {"candidates": [], "decisions": [], "cards": [], "moves": [],
                     "drafts": [], "revisions": [],
                     "plot_review": {"findings": []}, "prose_review": {"findings": []}}

    def test_dashboard_is_complete(self):
        result = compact("dashboard", self.data)
        self.assertTrue(result["complete"])
        self.assertEqual(result["data"]["canon"]["total"], 0)

    def test_inbox_pagination_is_explicit(self):
        items = [{"category": "plot_card", "id": str(i)} for i in range(5)]
        report = {"total": 5, "by_category": {"plot_card": 5}, "items": items}
        with patch("chat_summary.query", return_value={"data": report}):
            first = compact("inbox", self.data, limit=2)
            second = compact("inbox", self.data, limit=2, offset=2)
        self.assertEqual([x["id"] for x in first["items"]], ["0", "1"])
        self.assertTrue(first["has_more"])
        self.assertFalse(first["complete"])
        self.assertEqual([x["id"] for x in second["items"]], ["2", "3"])

    def test_progress_keeps_summary_when_paginated(self):
        report = {"summary": {"scenes": 3}, "unplaced_scene_ids": [],
                  "chapters": [{"chapter_id": str(i)} for i in range(3)]}
        with patch("chat_summary.query", return_value={"data": report}):
            result = compact("progress", self.data, limit=1)
        self.assertEqual(result["summary"]["scenes"], 3)
        self.assertEqual(len(result["chapters"]), 1)
        self.assertTrue(result["has_more"])

    def test_reject_invalid_limits_and_unsupported_commands(self):
        for limit in (0, 101, True, -1):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                compact("inbox", self.data, limit=limit)
        with self.assertRaises(ValueError):
            compact("inbox", self.data, offset=-1)
        with self.assertRaises(ValueError):
            compact("manuscript", self.data)


if __name__ == "__main__":
    unittest.main()
