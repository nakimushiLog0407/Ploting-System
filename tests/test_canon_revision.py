import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import canon_revision as cr


class CanonRevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for name, value in (("PROPOSALS", root / "proposals"), ("REVIEWS", root / "reviews")):
            p = patch.object(cr, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.entries = [{"candidate_id": "CAND-100001", "kind": "setting", "content": "旧設定"},
                        {"candidate_id": "CAND-100002", "kind": "character", "content": "人物"}]

    def test_requires_explicit_review_and_preserves_source(self):
        result = cr.propose(self.entries, "request-1", "CAND-100001", "新設定", "変更理由", ["CAND-100002"])
        rid = result["revision_id"]
        with self.assertRaises(ValueError):
            cr.review(self.entries, rid, "approved", "", False)
        self.assertEqual(cr.load(self.entries)[0]["CAND-100001"], "旧設定")
        cr.review(self.entries, rid, "approved", "承認", True)
        self.assertEqual(cr.load(self.entries)[0]["CAND-100001"], "新設定")
        self.assertEqual(self.entries[0]["content"], "旧設定")

    def test_rejection_no_effect(self):
        rid = cr.propose(self.entries, "request-1", "CAND-100001", "新設定", "理由", [])["revision_id"]
        cr.review(self.entries, rid, "rejected", "", True)
        self.assertEqual(cr.load(self.entries)[0]["CAND-100001"], "旧設定")

    def test_duplicate_request_and_pending_block(self):
        x = cr.propose(self.entries, "request-1", "CAND-100001", "新設定", "理由", [])
        self.assertEqual(cr.propose(self.entries, "request-1", "CAND-100001", "新設定", "理由", [])["status"], "already_saved")
        with self.assertRaises(ValueError):
            cr.propose(self.entries, "request-2", "CAND-100001", "別案", "理由", [])
        with self.assertRaises(ValueError):
            cr.propose(self.entries, "request-1", "CAND-100001", "別案", "理由", [])

    def test_change_history_and_stale_baseline(self):
        rid = cr.propose(self.entries, "request-1", "CAND-100001", "新設定", "理由", [])["revision_id"]
        cr.review(self.entries, rid, "approved", "", True)
        rid2 = cr.propose(self.entries, "request-2", "CAND-100001", "さらに変更", "理由2", [])["revision_id"]
        cr.review(self.entries, rid2, "approved", "", True)
        current, history = cr.load(self.entries)
        self.assertEqual(current["CAND-100001"], "さらに変更")
        self.assertEqual([x["before"] for x in history], ["旧設定", "新設定"])
        path = cr.PROPOSALS / (rid2 + ".json")
        import json
        item = json.loads(path.read_text(encoding="utf-8"))
        item["before"] = "不正な旧設定"
        path.write_text(json.dumps(item), encoding="utf-8")
        with self.assertRaises(ValueError):
            cr.load(self.entries)

    def test_immutable_proposal(self):
        rid = cr.propose(self.entries, "request-1", "CAND-100001", "新設定", "理由", [])["revision_id"]
        cr.review(self.entries, rid, "approved", "", True)
        path = cr.PROPOSALS / (rid + ".json")
        path.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            cr.load(self.entries)

    def test_unapproved_candidate_disallowed(self):
        with self.assertRaises(ValueError):
            cr.propose(self.entries, "request-1", "CAND-999999", "新設定", "理由", [])


if __name__ == "__main__":
    unittest.main()
