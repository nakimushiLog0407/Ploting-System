import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prose_drafts as pd


class ProseDraftTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, folder in (("PROPOSALS", "proposals"), ("REVIEWS", "reviews")):
            p = patch.object(pd, name, Path(tmp.name) / folder)
            p.start()
            self.addCleanup(p.stop)
        self.cards = [{"plot_id": "PLOT-100001", "kind": "scene", "status": "approved"},
                      {"plot_id": "PLOT-100002", "kind": "scene", "status": "proposed"}]

    def add(self, request, prose="文章案"):
        return pd.propose(self.cards, request, "PLOT-100001", prose, "")["draft_id"]

    def test_draft_needs_user_approval(self):
        did = self.add("req-1")
        self.assertEqual(pd.overview(pd.records(self.cards))["approved"], [])
        with self.assertRaises(ValueError):
            pd.review(self.cards, did, "approved", "", False)
        pd.review(self.cards, did, "approved", "", True)
        self.assertEqual(pd.overview(pd.records(self.cards))["approved"][0]["text"], "文章案")

    def test_rejected_draft_not_approved(self):
        did = self.add("req-1")
        pd.review(self.cards, did, "rejected", "", True)
        self.assertEqual(pd.overview(pd.records(self.cards))["approved"], [])

    def test_unapproved_scene_cannot_have_draft(self):
        with self.assertRaises(ValueError):
            pd.propose(self.cards, "req-1", "PLOT-100002", "文章", "")

    def test_only_one_approved_draft_per_scene(self):
        a = self.add("req-1")
        b = self.add("req-2", "別案")
        pd.review(self.cards, a, "approved", "", True)
        with self.assertRaises(ValueError):
            pd.review(self.cards, b, "approved", "", True)

    def test_idempotent_request(self):
        did = self.add("req-1")
        self.assertEqual(self.add("req-1"), did)
        with self.assertRaises(ValueError):
            self.add("req-1", "違う文章")

    def test_approved_draft_tampering_detected(self):
        did = self.add("req-1")
        pd.review(self.cards, did, "approved", "", True)
        (pd.PROPOSALS / (did + ".json")).write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            pd.records(self.cards)


if __name__ == "__main__":
    unittest.main()
