import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from idea_decision_handoff import decide, preview_decision

class IdeaDecisionHandoffTests(unittest.TestCase):
    def setUp(self):
        self.item = {"kind": "setting", "content": "空は青い。",
                     "evidence": {"source_id": "SRC-000001", "quote": "空は青い。"}}

    def test_no_confirmation_never_records(self):
        calls = []
        with self.assertRaises(ValueError):
            decide("CAND-000001", "approved", "", "decision-test",
                   False, recorder=lambda *args: calls.append(args))
        self.assertEqual(calls, [])

    @patch("idea_decision_handoff.all_decisions", return_value=iter(()))
    @patch("idea_decision_handoff.candidate")
    @patch("idea_decision_handoff.verify_all")
    def test_preview_is_read_only(self, verify, candidate, decisions):
        candidate.return_value = (self.item, "sha-test")
        result = preview_decision("CAND-000001", "approved")
        self.assertTrue(result["read_only"])
        self.assertFalse(result["saved"])
        self.assertEqual(result["source_quote"], "空は青い。")

    @patch("idea_decision_handoff.all_decisions", return_value=iter(()))
    @patch("idea_decision_handoff.candidate")
    @patch("idea_decision_handoff.verify_all")
    def test_confirmed_decision_records_once(self, verify, candidate, decisions):
        candidate.return_value = (self.item, "sha-test")
        calls = []
        def recorder(*args):
            calls.append(args)
            return {"status": "saved", "decision_id": "DEC-000001"}
        result = decide("CAND-000001", "approved", "採用", "decision-test",
                        True, recorder=recorder)
        self.assertEqual(calls, [("decision-test", "CAND-000001", "approved", "採用", True)])
        self.assertTrue(result["user_confirmed"])

    @patch("idea_decision_handoff.all_decisions")
    @patch("idea_decision_handoff.candidate")
    @patch("idea_decision_handoff.verify_all")
    def test_existing_decision_is_rejected(self, verify, candidate, decisions):
        candidate.return_value = (self.item, "sha-test")
        decisions.return_value = iter([(None, {"candidate_id": "CAND-000001"})])
        with self.assertRaises(ValueError):
            preview_decision("CAND-000001", "approved")

    def test_invalid_decision_rejected(self):
        with self.assertRaises(ValueError):
            preview_decision("CAND-000001", "maybe")

if __name__ == "__main__":
    unittest.main()
