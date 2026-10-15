import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import plot_diagnostic_review as pr


class PlotDiagnosticReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = patch.object(pr, "REVIEWS", Path(tmp.name) / "reviews")
        p.start()
        self.addCleanup(p.stop)
        self.findings = [{"code": "SCENE_UNPLACED", "subject_id": "PLOT-100001",
                          "detail": "Not placed", "requires_user_review": True,
                          "auto_fix": False, "literary_contradiction_proven": False}]

    def add(self, request="req-1", decision="intentional"):
        f = self.findings[0]
        return pr.propose(self.findings, request, f["code"], f["subject_id"],
                          pr.digest(f), decision, "明示的な判断")

    def test_explicit_disposition(self):
        rid = self.add()["review_id"]
        item = pr.overview(self.findings)["findings"][0]
        self.assertEqual(item["review"], "intentional")
        self.assertEqual(item["review_id"], rid)
        self.assertFalse(pr.overview(self.findings)["auto_fix"])

    def test_idempotent_request(self):
        rid = self.add()["review_id"]
        self.assertEqual(self.add()["review_id"], rid)
        with self.assertRaises(ValueError):
            self.add(decision="defer")

    def test_changed_finding_needs_fresh_review(self):
        self.add()
        self.findings[0]["detail"] = "Updated"
        self.assertEqual(pr.overview(self.findings)["findings"][0]["review"], "unreviewed")
        self.assertEqual(len(pr.overview(self.findings)["review_history"]), 1)

    def test_stale_fingerprint_rejected(self):
        with self.assertRaises(ValueError):
            pr.propose(self.findings, "req-1", "SCENE_UNPLACED", "PLOT-100001",
                       "0" * 64, "defer", "後日確認")

    def test_duplicate_review_blocked(self):
        self.add()
        with self.assertRaises(ValueError):
            self.add(request="req-2")


if __name__ == "__main__":
    unittest.main()
