import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from story_chronology_view import build_view


class StoryChronologyViewTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            {"candidate_id": "CAND-100001", "kind": "event", "content": "出来事A", "source_id": "SRC-1", "decision_id": "DEC-1"},
            {"candidate_id": "CAND-100002", "kind": "event", "content": "出来事B", "source_id": "SRC-2", "decision_id": "DEC-2"},
            {"candidate_id": "CAND-100003", "kind": "event", "content": "出来事C", "source_id": "SRC-3", "decision_id": "DEC-3"},
            {"candidate_id": "CAND-100004", "kind": "event", "content": "未配置", "source_id": "SRC-4", "decision_id": "DEC-4"},
            {"candidate_id": "CAND-100005", "kind": "character", "content": "人物", "source_id": "SRC-5", "decision_id": "DEC-5"},
        ]
        self.placements = [
            {"event_id": eid, "phase": "序盤", "status": "approved"}
            for eid in ("CAND-100001", "CAND-100002", "CAND-100003")
        ]
        self.orders = [{"order_id": "EOR-100001", "before_event_id": "CAND-100001",
                        "after_event_id": "CAND-100002", "evidence": "根拠", "status": "approved"}]

    def test_integrates_approved_order_and_unplaced(self):
        x = build_view(self.events, ["序盤", "終盤"], self.placements, self.orders)
        self.assertEqual(len(x["phases"]), 2)
        self.assertEqual([e["event_id"] for e in x["phases"][0]["tiers"][0]],
                         ["CAND-100001", "CAND-100003"])
        self.assertEqual([e["event_id"] for e in x["phases"][0]["tiers"][1]], ["CAND-100002"])
        self.assertEqual(len(x["unplaced_events"]), 1)
        self.assertEqual(len(x["phases"][0]["events_without_explicit_precedence"]), 1)
        self.assertEqual(x["canon_source"], "approved_only")

    def test_pending_and_rejected_order_ignored(self):
        for status in ("proposed", "rejected"):
            x = build_view(self.events, ["序盤"], self.placements, [dict(self.orders[0], status=status)])
            self.assertEqual(len(x["phases"][0]["tiers"]), 1)
            self.assertEqual(x["phases"][0]["precedence"], [])

    def test_pending_placement_ignored(self):
        placements = self.placements + [{"event_id": "CAND-100004", "phase": "序盤", "status": "proposed"}]
        x = build_view(self.events, ["序盤"], placements, self.orders)
        self.assertEqual(len(x["unplaced_events"]), 1)

    def test_cross_phase_order_rejected(self):
        placements = [dict(x) for x in self.placements]
        placements[1]["phase"] = "終盤"
        with self.assertRaises(ValueError):
            build_view(self.events, ["序盤", "終盤"], placements, self.orders)

    def test_cycle_rejected(self):
        orders = self.orders + [{"order_id": "EOR-100002", "before_event_id": "CAND-100002",
                                 "after_event_id": "CAND-100001", "evidence": "", "status": "approved"}]
        with self.assertRaises(ValueError):
            build_view(self.events, ["序盤"], self.placements, orders)

    def test_empty_view(self):
        x = build_view([], [], [], [])
        self.assertEqual(x["phases"], [])
        self.assertEqual(x["unplaced_events"], [])

    def test_cli_summary(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "story_chronology_view.py"), "--summary"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("placed_events", json.loads(p.stdout))


if __name__ == "__main__":
    unittest.main()
