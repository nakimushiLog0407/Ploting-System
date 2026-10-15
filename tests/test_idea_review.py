import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from idea_review import review


class IdeaReviewTests(unittest.TestCase):
    def setUp(self):
        self.source = "主人公は笑った。空は青かった。"
        self.proposals = [
            {"kind": "event", "content": "主人公は笑った。",
             "start": 0, "end": len("主人公は笑った。")},
            {"kind": "setting", "content": "空は鮮やかな青だった。",
             "start": len("主人公は笑った。"), "end": len(self.source)},
        ]

    def test_combined_review_preserves_order_and_evidence(self):
        result = review(self.source, self.proposals)
        self.assertEqual(result["workflow"], "unordered_idea_review")
        self.assertEqual([p["kind"] for p in result["proposals"]],
                         ["event", "setting"])
        self.assertEqual(result["proposals"][0]["source_quote"], "主人公は笑った。")
        self.assertEqual(result["audit"]["finding_count"], 1)
        self.assertEqual(result["audit"]["findings"][0]["proposal_number"], 2)
        self.assertTrue(result["classification_is_draft"])
        self.assertFalse(result["automatic_approval_allowed"])
        self.assertFalse(result["saved"])
        self.assertTrue(result["read_only"])

    def test_invalid_source_span_rejected(self):
        invalid = [{"kind": "event", "content": "test", "start": 0,
                    "end": len(self.source) + 1}]
        with self.assertRaises(ValueError):
            review(self.source, invalid)

    def test_unknown_fields_cannot_approve(self):
        invalid = [dict(self.proposals[0], approved=True)]
        with self.assertRaises(ValueError):
            review(self.source, invalid)

    def test_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.txt"
            proposals = Path(directory) / "proposals.json"
            source.write_text(self.source, encoding="utf-8")
            proposals.write_text(json.dumps(self.proposals, ensure_ascii=False),
                                 encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "idea_review.py"),
                 "--source-file", str(source), "--proposals-file", str(proposals)],
                capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            self.assertEqual(data["audit"]["finding_count"], 1)
            self.assertEqual(data["source_text"], self.source)
            self.assertFalse(data["saved"])


if __name__ == "__main__":
    unittest.main()
