import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import plot_moves as pm


class PlotMovesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for name, folder in (("PROPOSALS", "proposals"), ("REVIEWS", "reviews")):
            p = patch.object(pm, name, Path(temp.name) / folder)
            p.start()
            self.addCleanup(p.stop)
        self.cards = [
            {"plot_id": "PLOT-100001", "kind": "chapter", "status": "approved",
             "parent_chapter_id": None, "position": 1},
            {"plot_id": "PLOT-100002", "kind": "chapter", "status": "approved",
             "parent_chapter_id": None, "position": 2},
            {"plot_id": "PLOT-100003", "kind": "scene", "status": "approved",
             "parent_chapter_id": None, "position": None},
        ]

    def test_move_requires_approval(self):
        mid = pm.propose(self.cards, "req-1", "PLOT-100003", "PLOT-100001", 1, "配置指定")["move_id"]
        self.assertIsNone(pm.effective(self.cards, pm.records(self.cards))[2]["position"])
        with self.assertRaises(ValueError):
            pm.review(self.cards, mid, "approved", "", False)
        pm.review(self.cards, mid, "approved", "", True)
        result = pm.effective(self.cards, pm.records(self.cards))
        self.assertEqual(result[2]["position"], 1)
        self.assertIsNone(self.cards[2]["position"])

    def test_reject_occupied_position(self):
        mid = pm.propose(self.cards, "req-1", "PLOT-100002", None, 1, "移動")["move_id"]
        with self.assertRaises(ValueError):
            pm.review(self.cards, mid, "approved", "", True)

    def test_rejected_move_does_not_apply(self):
        mid = pm.propose(self.cards, "req-1", "PLOT-100003", "PLOT-100001", 1, "移動")["move_id"]
        pm.review(self.cards, mid, "rejected", "", True)
        self.assertIsNone(pm.effective(self.cards, pm.records(self.cards))[2]["position"])

    def test_stale_baseline_is_rejected(self):
        mid = pm.propose(self.cards, "req-1", "PLOT-100003", "PLOT-100001", 1, "移動")["move_id"]
        pm.review(self.cards, mid, "approved", "", True)
        second = pm.propose(self.cards, "req-2", "PLOT-100003", "PLOT-100002", 1, "再配置")["move_id"]
        pm.review(self.cards, second, "approved", "", True)
        self.assertEqual(pm.effective(self.cards, pm.records(self.cards))[2]["parent_chapter_id"], "PLOT-100002")

    def test_pending_duplicate_blocked(self):
        pm.propose(self.cards, "req-1", "PLOT-100003", "PLOT-100001", 1, "移動")
        with self.assertRaises(ValueError):
            pm.propose(self.cards, "req-2", "PLOT-100003", "PLOT-100002", 1, "別案")


if __name__ == "__main__":
    unittest.main()
