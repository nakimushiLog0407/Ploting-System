import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from canon_diagnostics import diagnose


class CanonDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"candidate_id": "CAND-100001", "kind": "event"},
            {"candidate_id": "CAND-100002", "kind": "event"},
            {"candidate_id": "CAND-100003", "kind": "character"},
            {"candidate_id": "CAND-100004", "kind": "character"},
        ]
        self.placements = [{"placement_id": "EVP-100001", "event_id": "CAND-100001",
                            "phase": "序盤", "status": "approved"}]
        self.rel = {"relation_id": "CRL-100001", "from_character_id": "CAND-100003",
                    "to_character_id": "CAND-100004", "relation_type": "friend",
                    "phase": "序盤", "status": "approved"}

    def test_unplaced_event_review_only(self):
        x = diagnose(self.entries, ["序盤"], self.placements, [], [self.rel])
        self.assertEqual(x["structural_count"], 0)
        self.assertEqual(x["review_count"], 1)
        self.assertEqual(x["findings"][0]["code"], "event_unplaced")
        self.assertFalse(x["canon_modified"])

    def test_unknown_phase_is_review_candidate(self):
        rel = dict(self.rel, phase="未登録")
        x = diagnose(self.entries, ["序盤"], self.placements, [], [rel])
        self.assertIn("relation_phase_unrecognized", [f["code"] for f in x["findings"]])

    def test_multiple_relation_types_not_automatically_conflict(self):
        other = dict(self.rel, relation_id="CRL-100002", relation_type="hostile")
        x = diagnose(self.entries, ["序盤"], self.placements, [], [self.rel, other])
        self.assertEqual(x["structural_count"], 0)
        self.assertFalse(x["literary_contradictions_automatically_determined"])

    def test_missing_character_structural(self):
        rel = dict(self.rel, to_character_id="CAND-999999")
        x = diagnose(self.entries, ["序盤"], self.placements, [], [rel])
        self.assertIn("missing_character", [f["code"] for f in x["findings"]])

    def test_pending_reverse_order_review_only(self):
        placements = self.placements + [{"placement_id": "EVP-100002", "event_id": "CAND-100002",
                                         "phase": "序盤", "status": "approved"}]
        approved = {"order_id": "EOR-100001", "before_event_id": "CAND-100001",
                    "after_event_id": "CAND-100002", "status": "approved"}
        pending = {"order_id": "EOR-100002", "before_event_id": "CAND-100002",
                   "after_event_id": "CAND-100001", "status": "proposed"}
        x = diagnose(self.entries, ["序盤"], placements, [approved, pending], [])
        self.assertIn("pending_reverse_order", [f["code"] for f in x["findings"]])
        self.assertEqual(x["structural_count"], 0)

    def test_cycle_structural(self):
        placements = self.placements + [{"placement_id": "EVP-100002", "event_id": "CAND-100002",
                                         "phase": "序盤", "status": "approved"}]
        orders = [{"order_id": "EOR-100001", "before_event_id": "CAND-100001",
                   "after_event_id": "CAND-100002", "status": "approved"},
                  {"order_id": "EOR-100002", "before_event_id": "CAND-100002",
                   "after_event_id": "CAND-100001", "status": "approved"}]
        x = diagnose(self.entries, ["序盤"], placements, orders, [])
        self.assertIn("event_order_cycle", [f["code"] for f in x["findings"]])

    def test_cli_summary(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "canon_diagnostics.py"), "--summary"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("review_count", json.loads(p.stdout))


if __name__ == "__main__":
    unittest.main()
