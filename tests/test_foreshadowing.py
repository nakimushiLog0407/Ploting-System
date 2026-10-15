import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import foreshadowing as fs


class ForeshadowingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, folder in (("PROPOSALS", "proposals"), ("REVIEWS", "reviews")):
            p = patch.object(fs, name, Path(tmp.name) / folder)
            p.start()
            self.addCleanup(p.stop)
        self.cards = [
            {"plot_id": "PLOT-100001", "kind": "scene", "status": "approved"},
            {"plot_id": "PLOT-100002", "kind": "scene", "status": "approved"},
            {"plot_id": "PLOT-100003", "kind": "scene", "status": "proposed"},
        ]

    def add(self, request, setup=None, payoff=None):
        return fs.propose(self.cards, request, "伏線", "詳細", setup, payoff, "")["thread_id"]

    def test_unassigned_payoff_is_not_error(self):
        fid = self.add("request-1", "PLOT-100001")
        fs.review(self.cards, fid, "approved", "", True)
        result = fs.overview(fs.records(self.cards))
        self.assertEqual(result["without_payoff"], [fid])
        self.assertFalse(result["missing_payoff_is_error"])

    def test_setup_and_payoff_are_separate(self):
        fid = self.add("request-1", "PLOT-100001", "PLOT-100002")
        fs.review(self.cards, fid, "approved", "", True)
        result = fs.overview(fs.records(self.cards))
        self.assertEqual(result["approved"][0]["setup_assignment"], "assigned")
        self.assertEqual(result["approved"][0]["payoff_assignment"], "assigned")
        self.assertFalse(result["actual_payoff_verified"])

    def test_unapproved_scene_is_invalid(self):
        with self.assertRaises(ValueError):
            self.add("request-1", "PLOT-100003")

    def test_explicit_review_and_rejection(self):
        fid = self.add("request-1")
        with self.assertRaises(ValueError):
            fs.review(self.cards, fid, "approved", "", False)
        fs.review(self.cards, fid, "rejected", "", True)
        self.assertEqual(fs.overview(fs.records(self.cards))["approved"], [])

    def test_duplicate_request_is_idempotent(self):
        fid = self.add("request-1")
        self.assertEqual(self.add("request-1"), fid)
        with self.assertRaises(ValueError):
            self.add("request-1", "PLOT-100001")

    def test_tampered_approved_proposal_detected(self):
        fid = self.add("request-1")
        fs.review(self.cards, fid, "approved", "", True)
        path = fs.PROPOSALS / (fid + ".json")
        path.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            fs.records(self.cards)


if __name__ == "__main__":
    unittest.main()
