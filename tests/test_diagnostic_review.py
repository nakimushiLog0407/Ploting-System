import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import diagnostic_review as dr


class DiagnosticReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patcher = patch.object(dr, "REVIEWS", Path(self.tmp.name))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.finding = {"code": "event_unplaced", "severity": "review",
                        "references": ["CAND-100001"], "detail": "No placement",
                        "requires_user_review": True}
        self.fid = dr.fingerprint(self.finding)

    def test_requires_explicit_user_confirmation(self):
        with self.assertRaises(ValueError):
            dr.review([self.finding], self.fid, "acknowledged", "", False)
        self.assertEqual(dr.read_reviews(), {})

    def test_append_only_and_idempotent(self):
        x = dr.review([self.finding], self.fid, "needs_fix", "あとで修正", True)
        self.assertEqual(x["status"], "saved")
        self.assertEqual(dr.review([self.finding], self.fid, "needs_fix", "あとで修正", True)["status"], "already_saved")
        with self.assertRaises(ValueError):
            dr.review([self.finding], self.fid, "not_an_issue", "", True)
        self.assertEqual(dr.read_reviews()[self.fid]["decision"], "needs_fix")

    def test_changed_finding_is_new_identity(self):
        dr.review([self.finding], self.fid, "acknowledged", "", True)
        changed = dict(self.finding, detail="Different evidence")
        result = dr.overview([changed], dr.read_reviews())
        self.assertEqual(result["active"][0]["review"], None)
        self.assertEqual(len(result["historical_not_current"]), 1)

    def test_no_stale_review(self):
        with self.assertRaises(ValueError):
            dr.review([], self.fid, "acknowledged", "", True)

    def test_tamper_detection(self):
        dr.review([self.finding], self.fid, "acknowledged", "", True)
        path = dr.REVIEWS / (self.fid + ".json")
        item = json.loads(path.read_text(encoding="utf-8"))
        item["finding"]["detail"] = "tampered"
        path.write_text(json.dumps(item), encoding="utf-8")
        with self.assertRaises(ValueError):
            dr.read_reviews()

    def test_no_canon_modification(self):
        x = dr.overview([self.finding], {})
        self.assertFalse(x["canon_modified"])
        self.assertTrue(x["decisions_do_not_change_canon"])


if __name__ == "__main__":
    unittest.main()
