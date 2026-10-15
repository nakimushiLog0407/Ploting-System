import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chat_canon_context import build

class ChatCanonContextTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {"candidate_id": "CAND-000001", "kind": "character", "content": "Approved",
             "evidence": {"source_id": "SRC-000001", "quote": "Original approved"}},
            {"candidate_id": "CAND-000002", "kind": "event", "content": "Pending",
             "evidence": {"source_id": "SRC-000002", "quote": "Original pending"}},
            {"candidate_id": "CAND-000003", "kind": "setting", "content": "Rejected",
             "evidence": {"source_id": "SRC-000003", "quote": "Original rejected"}},
        ]
        self.decisions = [
            {"candidate_id": "CAND-000001", "decision": "approved"},
            {"candidate_id": "CAND-000003", "decision": "rejected"},
        ]
        self.canon = [{"candidate_id": "CAND-000001", "content": "Approved"}]

    def test_separation(self):
        result = build(self.candidates, self.decisions, self.canon)
        self.assertEqual(len(result["approved_canon"]), 1)
        self.assertEqual(len(result["pending_not_canon"]), 1)
        self.assertEqual(len(result["rejected_not_canon"]), 1)
        self.assertTrue(result["approved_canon"][0]["is_canon"])
        self.assertFalse(result["pending_not_canon"][0]["is_canon"])
        self.assertFalse(result["approval_performed"])
        self.assertEqual(result["approved_canon"][0]["source_quote"], "Original approved")

    def test_missing_canon_fails_closed(self):
        with self.assertRaises(ValueError):
            build(self.candidates, self.decisions, [])

    def test_unexpected_canon_fails_closed(self):
        with self.assertRaises(ValueError):
            build(self.candidates, self.decisions, self.canon + [{"candidate_id": "CAND-000002"}])

    def test_approved_revision_effective_content(self):
        current = {"CAND-000001": "Revised approved"}
        history = [{"candidate_id": "CAND-000001", "revision_id": "REV-000001",
                    "status": "approved", "after": "Revised approved"},
                   {"candidate_id": "CAND-000001", "revision_id": "REV-000002",
                    "status": "proposed", "after": "Not approved"}]
        result = build(self.candidates, self.decisions, self.canon, current, history)
        entry = result["approved_canon"][0]
        self.assertEqual(entry["content"], "Revised approved")
        self.assertEqual(entry["original_content"], "Approved")
        self.assertEqual(entry["approved_revision_ids"], ["REV-000001"])
        self.assertEqual(result["pending_revisions_not_canon"][0]["proposed_content_not_canon"],
                         "Not approved")

    def test_revision_for_unapproved_candidate_rejected(self):
        history = [{"candidate_id": "CAND-000002", "revision_id": "REV-000003",
                    "status": "proposed", "after": "Not allowed"}]
        with self.assertRaises(ValueError):
            build(self.candidates, self.decisions, self.canon, None, history)

    def test_incomplete_effective_canon_rejected(self):
        with self.assertRaises(ValueError):
            build(self.candidates, self.decisions, self.canon, {})

    def test_duplicate_decisions_rejected(self):
        with self.assertRaises(ValueError):
            build(self.candidates, self.decisions + self.decisions[:1], self.canon)

if __name__ == "__main__":
    unittest.main()
