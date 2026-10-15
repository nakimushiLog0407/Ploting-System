import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from idea_intake_preview import preview

class IdeaIntakePreviewTests(unittest.TestCase):
    def test_out_of_order_ideas_remain_proposals(self):
        source = "青い空。主人公は笑った。"
        proposals = [
            {"kind": "event", "content": "主人公が笑う", "start": 4, "end": len(source)},
            {"kind": "setting", "content": "空は青い", "start": 0, "end": 4},
        ]
        result = preview(source, proposals)
        self.assertEqual(result["proposal_count"], 2)
        self.assertEqual(result["proposals"][0]["kind"], "event")
        self.assertEqual(result["proposals"][1]["source_quote"], "青い空。")
        self.assertTrue(all(not item["is_canon"] for item in result["proposals"]))
        self.assertFalse(result["saved"])
        self.assertFalse(result["approval_performed"])

    def test_bad_source_span_rejected(self):
        with self.assertRaises(ValueError):
            preview("abc", [{"kind": "event", "content": "test", "start": 0, "end": 4}])

    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValueError):
            preview("abc", [{"kind": "invented", "content": "test", "start": 0, "end": 3}])

    def test_unexpected_fields_rejected(self):
        with self.assertRaises(ValueError):
            preview("abc", [{"kind": "event", "content": "test", "start": 0, "end": 3,
                             "approved": True}])

    def test_empty_input_rejected(self):
        with self.assertRaises(ValueError):
            preview("", [])
        with self.assertRaises(ValueError):
            preview("abc", [])

if __name__ == "__main__":
    unittest.main()
