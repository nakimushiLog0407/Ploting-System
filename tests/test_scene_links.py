import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scene_links as sl


class SceneLinksTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, folder in (("PROPOSALS", "proposals"), ("REVIEWS", "reviews")):
            p = patch.object(sl, name, Path(tmp.name) / folder)
            p.start()
            self.addCleanup(p.stop)
        self.cards = [
            {"plot_id": "PLOT-100001", "kind": "scene", "status": "approved"},
            {"plot_id": "PLOT-100002", "kind": "scene", "status": "approved"},
            {"plot_id": "PLOT-100003", "kind": "scene", "status": "proposed"},
        ]

    def add(self, request, relation="causes", a="PLOT-100001", b="PLOT-100002"):
        return sl.propose(self.cards, request, a, b, relation, "明示された関係")["link_id"]

    def test_pending_not_effective_and_approval_required(self):
        lid = self.add("request-1")
        self.assertEqual(sl.overview(sl.records(self.cards))["approved_by_type"]["causes"], [])
        with self.assertRaises(ValueError):
            sl.review(self.cards, lid, "approved", "", False)
        sl.review(self.cards, lid, "approved", "", True)
        self.assertEqual(len(sl.overview(sl.records(self.cards))["approved_by_type"]["causes"]), 1)

    def test_chronology_does_not_imply_causality(self):
        lid = self.add("request-1", "precedes")
        sl.review(self.cards, lid, "approved", "", True)
        result = sl.overview(sl.records(self.cards))
        self.assertEqual(len(result["approved_by_type"]["precedes"]), 1)
        self.assertEqual(result["approved_by_type"]["causes"], [])
        self.assertFalse(result["causality_inferred"])

    def test_rejected_is_not_effective(self):
        lid = self.add("request-1")
        sl.review(self.cards, lid, "rejected", "", True)
        self.assertEqual(sl.overview(sl.records(self.cards))["approved_by_type"]["causes"], [])

    def test_requires_approved_scenes(self):
        with self.assertRaises(ValueError):
            self.add("request-1", b="PLOT-100003")

    def test_duplicate_approved_relation_blocked(self):
        lid = self.add("request-1", "related_to")
        sl.review(self.cards, lid, "approved", "", True)
        duplicate = self.add("request-2", "related_to", "PLOT-100002", "PLOT-100001")
        with self.assertRaises(ValueError):
            sl.review(self.cards, duplicate, "approved", "", True)

    def test_request_id_idempotency(self):
        lid = self.add("request-1")
        self.assertEqual(self.add("request-1"), lid)
        with self.assertRaises(ValueError):
            self.add("request-1", "enables")


if __name__ == "__main__":
    unittest.main()
