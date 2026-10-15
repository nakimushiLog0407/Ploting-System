import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prose_diagnostic_review as pr


class ProseDiagnosticReviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        p = patch.object(pr, "REVIEWS", Path(temp.name) / "reviews")
        p.start()
        self.addCleanup(p.stop)
        self.findings = [{"code": "APPROVED_SCENE_WITHOUT_PROSE",
                          "subject_id": "PLOT-100001", "detail": "No approved prose",
                          "requires_user_review": True, "auto_fix": False,
                          "literary_contradiction_proven": False}]

    def submit(self, request_id="req-1", decision="defer", confirmed=True):
        f = self.findings[0]
        return pr.review(self.findings, request_id, f["code"], f["subject_id"],
                         pr.digest(f), decision, "後日確認する", confirmed)

    def test_explicit_user_review(self):
        with self.assertRaises(ValueError):
            self.submit(confirmed=False)
        result = self.submit()
        view = pr.overview(self.findings)
        self.assertEqual(view["findings"][0]["review"], "defer")
        self.assertEqual(view["findings"][0]["review_id"], result["review_id"])
        self.assertFalse(view["automatic_corrections"])

    def test_idempotent_request(self):
        rid = self.submit()["review_id"]
        self.assertEqual(self.submit()["review_id"], rid)
        with self.assertRaises(ValueError):
            self.submit(decision="intentional")

    def test_changed_finding_needs_new_review(self):
        self.submit()
        self.findings[0]["detail"] = "Changed finding"
        self.assertEqual(pr.overview(self.findings)["findings"][0]["review"], "unreviewed")
        self.assertEqual(len(pr.overview(self.findings)["review_history"]), 1)

    def test_stale_fingerprint_rejected(self):
        f = self.findings[0]
        with self.assertRaises(ValueError):
            pr.review(self.findings, "req-1", f["code"], f["subject_id"],
                      "0" * 64, "defer", "後日確認する", True)

    def test_duplicate_review_rejected(self):
        self.submit()
        with self.assertRaises(ValueError):
            self.submit(request_id="req-2")

    def test_empty_reason_rejected(self):
        f = self.findings[0]
        with self.assertRaises(ValueError):
            pr.review(self.findings, "req-1", f["code"], f["subject_id"],
                      pr.digest(f), "defer", "", True)


if __name__ == "__main__":
    unittest.main()
