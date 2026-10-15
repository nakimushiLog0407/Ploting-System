import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from plot_overview import build


class PlotOverviewTests(unittest.TestCase):
    def setUp(self):
        self.cards = [
            {"plot_id": "PLOT-100001", "kind": "chapter", "status": "approved", "parent_chapter_id": None, "position": 1},
            {"plot_id": "PLOT-100002", "kind": "scene", "status": "approved", "parent_chapter_id": "PLOT-100001", "position": 1},
            {"plot_id": "PLOT-100003", "kind": "scene", "status": "approved", "parent_chapter_id": None, "position": None},
        ]

    def test_integrated_approved_data(self):
        links = [{"link_id": "SLNK-100001", "from_scene_id": "PLOT-100002",
                  "to_scene_id": "PLOT-100003", "relation_type": "foreshadows", "status": "approved"}]
        threads = [{"thread_id": "FSDW-100001", "status": "approved",
                    "setup_scene_id": "PLOT-100002", "payoff_scene_id": None}]
        result = build(self.cards, [], links, threads, [])
        scene = result["plot"]["ordered_chapters"][0]["scenes"][0]
        self.assertEqual(scene["approved_links"][0]["link_id"], "SLNK-100001")
        self.assertEqual(scene["foreshadowing"][0]["role"], "setup")
        self.assertEqual(result["unplaced_scene_ids"], ["PLOT-100003"])
        self.assertEqual(result["unassigned_payoff_thread_ids"], ["FSDW-100001"])
        self.assertFalse(result["unassigned_payoff_is_error"])

    def test_rejected_and_pending_links_are_not_canon(self):
        links = [{"link_id": "SLNK-100001", "from_scene_id": "PLOT-100002",
                  "to_scene_id": "PLOT-100003", "relation_type": "causes", "status": "proposed"}]
        result = build(self.cards, [], links, [], [])
        self.assertEqual(result["scene_relationships"]["approved_by_type"]["causes"], [])
        self.assertFalse(result["inferred_causality"])

    def test_approved_move_reflected_without_modifying_original(self):
        moves = [{"move_id": "PMOV-100001", "plot_id": "PLOT-100003",
                  "before": {"parent_chapter_id": None, "position": None},
                  "after": {"parent_chapter_id": "PLOT-100001", "position": 2},
                  "status": "approved"}]
        result = build(self.cards, moves, [], [], [])
        scenes = result["plot"]["ordered_chapters"][0]["scenes"]
        self.assertEqual([x["position"] for x in scenes], [1, 2])
        self.assertIsNone(self.cards[2]["position"])

    def test_approved_payoff_reassignment_reflected(self):
        threads = [{"thread_id": "FSDW-100001", "status": "approved",
                    "setup_scene_id": "PLOT-100002", "payoff_scene_id": None}]
        changes = [{"change_id": "FCHG-100001", "thread_id": "FSDW-100001",
                    "before": {"setup_scene_id": "PLOT-100002", "payoff_scene_id": None},
                    "after": {"setup_scene_id": "PLOT-100002", "payoff_scene_id": "PLOT-100003"},
                    "status": "approved"}]
        result = build(self.cards, [], [], threads, changes)
        self.assertEqual(result["unassigned_payoff_thread_ids"], [])
        self.assertIsNone(threads[0]["payoff_scene_id"])


if __name__ == "__main__":
    unittest.main()
