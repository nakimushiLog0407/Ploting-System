import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from idea_lifecycle_status import status


class IdeaLifecycleStatusTests(unittest.TestCase):
    def setUp(self):
        self.item = {
            "kind": "setting", "content": "空は青い。",
            "evidence": {"source_id": "SRC-000001", "quote": "空は青い。"},
        }
        self.verify = patch("idea_lifecycle_status.verify_all").start()
        self.candidate = patch("idea_lifecycle_status.candidate",
                               return_value=(self.item, "sha-test")).start()
        self.addCleanup(patch.stopall)

    @patch("idea_lifecycle_status.all_decisions", return_value=iter(()))
    def test_pending(self, decisions):
        result = status("CAND-000001")
        self.assertEqual(result["review_status"], "pending")
        self.assertFalse(result["is_canon"])
        self.assertTrue(result["read_only"])

    @patch("idea_lifecycle_status.all_decisions")
    def test_approved(self, decisions):
        decisions.return_value = iter([(None, {
            "candidate_id": "CAND-000001", "decision": "approved",
            "decision_id": "DEC-000001",
        })])
        result = status("CAND-000001")
        self.assertTrue(result["is_canon"])
        self.assertEqual(result["decision_id"], "DEC-000001")

    @patch("idea_lifecycle_status.all_decisions")
    def test_rejected(self, decisions):
        decisions.return_value = iter([(None, {
            "candidate_id": "CAND-000001", "decision": "rejected",
            "decision_id": "DEC-000002",
        })])
        self.assertFalse(status("CAND-000001")["is_canon"])

    @patch("idea_lifecycle_status.all_decisions")
    def test_duplicate_decisions_fail(self, decisions):
        decisions.return_value = iter([
            (None, {"candidate_id": "CAND-000001", "decision": "approved"}),
            (None, {"candidate_id": "CAND-000001", "decision": "rejected"}),
        ])
        with self.assertRaises(ValueError):
            status("CAND-000001")


if __name__ == "__main__":
    unittest.main()
