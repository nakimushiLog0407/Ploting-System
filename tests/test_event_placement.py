import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import event_placement as ep


class EventPlacementTests(unittest.TestCase):
    def setUp(self):
        self.events = [{"candidate_id": "CAND-100001", "kind": "event", "content": "出来事A",
                        "source_id": "SRC-1", "decision_id": "DEC-1"},
                       {"candidate_id": "CAND-100002", "kind": "event", "content": "出来事B",
                        "source_id": "SRC-2", "decision_id": "DEC-2"}]
        self.placement = {"placement_id": "EVP-100001", "event_id": "CAND-100001",
                          "phase": "序盤", "evidence": "明示", "status": "approved"}

    def test_only_approved_placement_is_visible(self):
        result = ep.timeline(self.events, [self.placement, dict(self.placement, status="proposed")], ["序盤", "終盤"])
        self.assertEqual(len(result["phases"][0]["events"]), 1)
        self.assertEqual(result["unplaced_events"][0]["event_id"], "CAND-100002")
        self.assertEqual(result["within_phase_order"], "unknown")

    def test_rejected_is_not_placed(self):
        result = ep.timeline(self.events, [dict(self.placement, status="rejected")], ["序盤"])
        self.assertEqual(len(result["unplaced_events"]), 2)

    def test_invalid_phase_fails(self):
        with self.assertRaises(ValueError):
            ep.timeline(self.events, [self.placement], ["終盤"])

    def test_duplicate_approved_event_fails(self):
        with self.assertRaises(ValueError):
            ep.timeline(self.events, [self.placement, dict(self.placement, placement_id="EVP-100002")], ["序盤"])

    def test_approval_requires_confirmation(self):
        with self.assertRaises(ValueError):
            ep.review("EVP-100001", "approved", "", False)

    def test_proposal_needs_approved_phase_and_event(self):
        with patch.object(ep, "records", return_value=[]), patch.object(ep, "event_ids", return_value={"CAND-100001"}), patch.object(ep, "approved_phases", return_value=[]):
            with self.assertRaises(ValueError):
                ep.propose("req-1", "CAND-100001", "序盤", "")

    def test_live_cli(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "event_placement.py"), "timeline", "--summary"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("unplaced_events", json.loads(p.stdout))


if __name__ == "__main__":
    unittest.main()
