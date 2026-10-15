import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from idea_candidate_save import save_reviewed

class IdeaCandidateSaveTests(unittest.TestCase):
    def setUp(self):
        self.source = "空は青い。"
        self.proposals = [{"kind": "setting", "content": self.source,
                           "start": 0, "end": len(self.source)}]
        self.args = ("SRC-000001", self.source, self.proposals, "intake-test", 1)

    def test_missing_confirmation_never_writes(self):
        called = []
        with self.assertRaises(ValueError):
            save_reviewed(*self.args, confirmed=False, writer=lambda *args: called.append(args))
        self.assertEqual(called, [])

    @patch("idea_save_handoff.source_span")
    def test_confirmed_candidate_only(self, span):
        span.return_value = {"quote": self.source}
        calls = []
        def writer(*args):
            calls.append(args)
            return {"status": "saved", "candidate_id": "CAND-000001"}
        result = save_reviewed(*self.args, confirmed=True, writer=writer)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], ("intake-test-001", "setting", self.source,
                                    "SRC-000001", 0, len(self.source)))
        self.assertTrue(result["candidate_only"])
        self.assertFalse(result["canon_approved"])

    @patch("idea_save_handoff.source_span")
    def test_unknown_proposal_does_not_write(self, span):
        span.return_value = {"quote": self.source}
        calls = []
        with self.assertRaises(ValueError):
            save_reviewed("SRC-000001", self.source, self.proposals, "intake-test",
                          2, confirmed=True, writer=lambda *args: calls.append(args))
        self.assertEqual(calls, [])

    @patch("idea_save_handoff.source_span")
    def test_source_mismatch_does_not_write(self, span):
        span.return_value = {"quote": "not original"}
        calls = []
        with self.assertRaises(ValueError):
            save_reviewed(*self.args, confirmed=True, writer=lambda *args: calls.append(args))
        self.assertEqual(calls, [])

if __name__ == "__main__":
    unittest.main()
