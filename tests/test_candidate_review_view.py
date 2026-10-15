import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from candidate_review_view import build

class CandidateReviewViewTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {"candidate_id": "CAND-000001", "kind": "character", "content": "Idea A",
             "evidence": {"source_id": "SRC-000001", "quote": "Original A", "start": 0, "end": 10}},
            {"candidate_id": "CAND-000002", "kind": "setting", "content": "Idea B",
             "evidence": {"source_id": "SRC-000002", "quote": "Original B", "start": 0, "end": 10}},
            {"candidate_id": "CAND-000003", "kind": "event", "content": "Idea C",
             "evidence": {"source_id": "SRC-000003", "quote": "Original C", "start": 0, "end": 10}},
        ]
        self.decisions = [
            {"candidate_id": "CAND-000001", "decision": "approved", "decision_id": "DEC-000001"},
            {"candidate_id": "CAND-000003", "decision": "rejected", "decision_id": "DEC-000002"},
        ]

    def test_all_statuses_and_source(self):
        result = build(self.candidates, self.decisions)
        self.assertEqual([x["review_status"] for x in result["entries"]],
                         ["approved", "pending", "rejected"])
        self.assertEqual([x["is_canon"] for x in result["entries"]], [True, False, False])
        self.assertEqual(result["entries"][0]["source_quote"], "Original A")
        self.assertTrue(result["read_only"])

    def test_pending_never_canon(self):
        result = build(self.candidates, self.decisions, "pending")
        self.assertEqual(result["total"], 1)
        self.assertFalse(result["entries"][0]["is_canon"])
        self.assertIsNone(result["entries"][0]["decision_id"])

    def test_duplicate_decision_fails_closed(self):
        with self.assertRaises(ValueError):
            build(self.candidates, self.decisions + self.decisions[:1])

    def test_invalid_status_rejected(self):
        with self.assertRaises(ValueError):
            build(self.candidates, self.decisions, "maybe")

if __name__ == "__main__":
    unittest.main()
