import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import event_order as eo

class EventOrderTests(unittest.TestCase):
    def setUp(self):
        self.placements = [
            {"event_id": x, "phase": "序盤", "status": "approved"}
            for x in ("CAND-100001", "CAND-100002", "CAND-100003")
        ]
        self.edge = {"order_id": "EOR-100001", "before_event_id": "CAND-100001",
                     "after_event_id": "CAND-100002", "evidence": "明示", "status": "approved"}

    def test_parallel_tiers_do_not_assert_total_order(self):
        x = eo.overview(self.placements, ["序盤"], [self.edge])
        self.assertEqual(x["phases"][0]["parallel_tiers"][0], ["CAND-100001", "CAND-100003"])
        self.assertEqual(x["phases"][0]["parallel_tiers"][1], ["CAND-100002"])
        self.assertTrue(x["tiers_are_not_total_order"])

    def test_proposed_and_rejected_not_used(self):
        for status in ("proposed", "rejected"):
            x = eo.overview(self.placements, ["序盤"], [dict(self.edge, status=status)])
            self.assertEqual(len(x["phases"][0]["parallel_tiers"]), 1)
            self.assertEqual(x["phases"][0]["approved_precedence"], [])

    def test_cycle_detected(self):
        with self.assertRaises(ValueError):
            eo.layers(["A", "B"], [("A", "B"), ("B", "A")])

    def test_self_reference_detected(self):
        with self.assertRaises(ValueError):
            eo.layers(["A"], [("A", "A")])

    def test_cross_phase_rejected(self):
        placements = self.placements + [{"event_id": "CAND-100004", "phase": "終盤", "status": "approved"}]
        with patch.object(eo, "records", return_value=[]), patch.object(eo, "placement_records", return_value=placements), patch.object(eo, "approved_phases", return_value=["序盤", "終盤"]):
            with self.assertRaises(ValueError):
                eo.propose("req-1", "CAND-100001", "CAND-100004", "")

    def test_user_confirmation_required(self):
        with self.assertRaises(ValueError):
            eo.review("EOR-100001", "approved", "", False)

    def test_cli_summary(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "event_order.py"), "overview", "--summary"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("approved_precedence", json.loads(p.stdout))

if __name__ == "__main__":
    unittest.main()
