import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from idea_save_handoff import plan

class IdeaSaveHandoffTests(unittest.TestCase):
    def setUp(self):
        self.source = "空は青い。"
        self.proposals = [{"kind": "setting", "content": "空は青い。",
                           "start": 0, "end": len(self.source)}]
        self.evidence = {"quote": self.source, "source_id": "SRC-000001"}

    @patch("idea_save_handoff.source_span")
    def test_plan_preserves_source_and_never_saves(self, span):
        span.return_value = self.evidence
        result = plan("SRC-000001", self.source, self.proposals, "intake-test")
        entry = result["items"][0]
        self.assertEqual(entry["candidate_save_request"]["kind"], "setting")
        self.assertEqual(entry["candidate_save_request"]["request_id"], "intake-test-001")
        self.assertFalse(entry["will_be_canon"])
        self.assertFalse(result["saved"])
        self.assertFalse(result["approval_performed"])
        span.assert_called_once_with("SRC-000001", 0, len(self.source))

    @patch("idea_save_handoff.source_span")
    def test_mismatched_archive_rejected(self, span):
        span.return_value = {"quote": "Different text"}
        with self.assertRaises(ValueError):
            plan("SRC-000001", self.source, self.proposals, "intake-test")

    @patch("idea_save_handoff.source_span")
    def test_invalid_request_prefix_rejected(self, span):
        with self.assertRaises(ValueError):
            plan("SRC-000001", self.source, self.proposals, "bad prefix")
        span.assert_not_called()

    @patch("idea_save_handoff.source_span")
    def test_invalid_source_span_rejected(self, span):
        invalid = [dict(self.proposals[0], end=100)]
        with self.assertRaises(ValueError):
            plan("SRC-000001", self.source, invalid, "intake-test")
        span.assert_not_called()

if __name__ == "__main__":
    unittest.main()
