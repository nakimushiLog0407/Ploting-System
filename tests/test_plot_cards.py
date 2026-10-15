import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import plot_cards as pc


class PlotCardsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, folder in (("PROPOSALS", "proposals"), ("REVIEWS", "reviews")):
            p = patch.object(pc, name, Path(tmp.name) / folder)
            p.start()
            self.addCleanup(p.stop)

    def add(self, request, kind, title, parent=None, position=None):
        return pc.propose(request, kind, title, "", parent, position, [])["plot_id"]

    def test_unplaced_scene_stays_in_inbox(self):
        sid = self.add("request-1", "scene", "思いついた場面")
        self.assertEqual(len(pc.overview(pc.records())["pending"]), 1)
        pc.review(sid, "approved", "", True)
        result = pc.overview(pc.records())
        self.assertEqual([x["plot_id"] for x in result["unplaced_scenes"]], [sid])
        self.assertFalse(result["sequence_inferred"])

    def test_explicit_chapter_and_scene_order(self):
        cid = self.add("request-1", "chapter", "第一章", position=1)
        pc.review(cid, "approved", "", True)
        sid = self.add("request-2", "scene", "場面", cid, 1)
        pc.review(sid, "approved", "", True)
        result = pc.overview(pc.records())
        self.assertEqual(result["ordered_chapters"][0]["scenes"][0]["plot_id"], sid)

    def test_parent_must_be_approved_before_scene(self):
        cid = self.add("request-1", "chapter", "章")
        sid = self.add("request-2", "scene", "場面", cid, 1)
        with self.assertRaises(ValueError):
            pc.review(sid, "approved", "", True)
        pc.review(cid, "approved", "", True)
        pc.review(sid, "approved", "", True)

    def test_duplicate_approved_position_rejected(self):
        a = self.add("request-1", "chapter", "第一章", position=1)
        b = self.add("request-2", "chapter", "別の第一章", position=1)
        pc.review(a, "approved", "", True)
        with self.assertRaises(ValueError):
            pc.review(b, "approved", "", True)

    def test_explicit_confirmation_and_rejection(self):
        sid = self.add("request-1", "scene", "没案")
        with self.assertRaises(ValueError):
            pc.review(sid, "approved", "", False)
        pc.review(sid, "rejected", "", True)
        self.assertEqual(len(pc.overview(pc.records())["rejected"]), 1)

    def test_idempotent_request(self):
        sid = self.add("request-1", "scene", "場面")
        self.assertEqual(pc.propose("request-1", "scene", "場面", "", None, None, [])["plot_id"], sid)
        with self.assertRaises(ValueError):
            self.add("request-1", "scene", "別の場面")


if __name__ == "__main__":
    unittest.main()
