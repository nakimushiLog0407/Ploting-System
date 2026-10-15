import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from plot_diagnostics import diagnose


class PlotDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.cards = [
            {"plot_id": "PLOT-100001", "kind": "chapter", "status": "approved", "parent_chapter_id": None, "position": 1},
            {"plot_id": "PLOT-100002", "kind": "scene", "status": "approved", "parent_chapter_id": "PLOT-100001", "position": 1},
            {"plot_id": "PLOT-100003", "kind": "scene", "status": "approved", "parent_chapter_id": "PLOT-100001", "position": 2},
        ]

    def test_valid_precedence_no_conflict(self):
        links = [{"link_id": "SLNK-100001", "status": "approved", "relation_type": "precedes",
                  "from_scene_id": "PLOT-100002", "to_scene_id": "PLOT-100003"}]
        self.assertEqual(diagnose(self.cards, links, [])["count"], 0)

    def test_precedence_conflict_is_review_only(self):
        links = [{"link_id": "SLNK-100001", "status": "approved", "relation_type": "precedes",
                  "from_scene_id": "PLOT-100003", "to_scene_id": "PLOT-100002"}]
        result = diagnose(self.cards, links, [])
        self.assertIn("PRECEDENCE_POSITION_CONFLICT", [x["code"] for x in result["findings"]])
        self.assertTrue(all(x["requires_user_review"] and not x["auto_fix"] for x in result["findings"]))

    def test_causal_link_does_not_imply_order(self):
        links = [{"link_id": "SLNK-100001", "status": "approved", "relation_type": "causes",
                  "from_scene_id": "PLOT-100003", "to_scene_id": "PLOT-100002"}]
        self.assertEqual(diagnose(self.cards, links, [])["count"], 0)

    def test_unassigned_payoff_is_not_literary_contradiction(self):
        threads = [{"thread_id": "FSDW-100001", "status": "approved",
                    "setup_scene_id": "PLOT-100002", "payoff_scene_id": None}]
        result = diagnose(self.cards, [], threads)
        self.assertEqual(result["findings"][0]["code"], "PAYOFF_UNASSIGNED")
        self.assertFalse(result["findings"][0]["literary_contradiction_proven"])

    def test_unplaced_scene_is_reported(self):
        self.cards[2]["position"] = None
        result = diagnose(self.cards, [], [])
        self.assertIn("SCENE_UNPLACED", [x["code"] for x in result["findings"]])

    def test_cycle_is_reported(self):
        links = [{"link_id": "SLNK-100001", "status": "approved", "relation_type": "precedes",
                  "from_scene_id": "PLOT-100002", "to_scene_id": "PLOT-100003"},
                 {"link_id": "SLNK-100002", "status": "approved", "relation_type": "precedes",
                  "from_scene_id": "PLOT-100003", "to_scene_id": "PLOT-100002"}]
        result = diagnose(self.cards, links, [])
        self.assertIn("PRECEDENCE_CYCLE", [x["code"] for x in result["findings"]])


if __name__ == "__main__":
    unittest.main()
