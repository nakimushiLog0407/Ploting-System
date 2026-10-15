import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prose_revisions as pr


class ProseRevisionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, folder in (("PROPOSALS", "proposals"), ("REVIEWS", "reviews")):
            p = patch.object(pr, name, Path(tmp.name) / folder)
            p.start()
            self.addCleanup(p.stop)
        self.drafts = [{"draft_id": "DRAFT-100001", "scene_id": "PLOT-100001",
                        "text": "元の文章", "status": "approved"}]

    def test_approval_preserves_original(self):
        rid = pr.propose(self.drafts, "req-1", "DRAFT-100001", "改稿した文章", "表現を調整")["revision_id"]
        self.assertEqual(pr.effective(self.drafts, pr.records(self.drafts))[0]["text"], "元の文章")
        with self.assertRaises(ValueError):
            pr.review(self.drafts, rid, "approved", "", False)
        pr.review(self.drafts, rid, "approved", "", True)
        result = pr.effective(self.drafts, pr.records(self.drafts))[0]
        self.assertEqual(result["text"], "改稿した文章")
        self.assertEqual(result["original_text"], "元の文章")
        self.assertEqual(self.drafts[0]["text"], "元の文章")

    def test_rejected_revision_does_not_apply(self):
        rid = pr.propose(self.drafts, "req-1", "DRAFT-100001", "別案", "調整")["revision_id"]
        pr.review(self.drafts, rid, "rejected", "", True)
        self.assertEqual(pr.effective(self.drafts, pr.records(self.drafts))[0]["text"], "元の文章")

    def test_second_revision_uses_latest_approved(self):
        a = pr.propose(self.drafts, "req-1", "DRAFT-100001", "第一稿改訂", "修正")["revision_id"]
        pr.review(self.drafts, a, "approved", "", True)
        b = pr.propose(self.drafts, "req-2", "DRAFT-100001", "第二稿改訂", "再修正")["revision_id"]
        pr.review(self.drafts, b, "approved", "", True)
        self.assertEqual(pr.effective(self.drafts, pr.records(self.drafts))[0]["approved_revision_ids"], [a, b])

    def test_pending_revision_blocks_parallel_change(self):
        pr.propose(self.drafts, "req-1", "DRAFT-100001", "別案", "修正")
        with self.assertRaises(ValueError):
            pr.propose(self.drafts, "req-2", "DRAFT-100001", "別案2", "修正")

    def test_idempotent_request(self):
        rid = pr.propose(self.drafts, "req-1", "DRAFT-100001", "別案", "修正")["revision_id"]
        self.assertEqual(pr.propose(self.drafts, "req-1", "DRAFT-100001", "別案", "修正")["revision_id"], rid)

    def test_approved_proposal_tampering_detected(self):
        rid = pr.propose(self.drafts, "req-1", "DRAFT-100001", "別案", "修正")["revision_id"]
        pr.review(self.drafts, rid, "approved", "", True)
        (pr.PROPOSALS / (rid + ".json")).write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            pr.records(self.drafts)


if __name__ == "__main__":
    unittest.main()
