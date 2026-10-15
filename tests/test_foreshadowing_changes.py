import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import foreshadowing_changes as fc


class ForeshadowingChangesTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, folder in (("PROPOSALS", "proposals"), ("REVIEWS", "reviews")):
            p = patch.object(fc, name, Path(tmp.name) / folder)
            p.start()
            self.addCleanup(p.stop)
        self.threads = [{"thread_id": "FSDW-100001", "status": "approved",
                         "setup_scene_id": "PLOT-100001", "payoff_scene_id": None}]
        self.scenes = {"PLOT-100001", "PLOT-100002", "PLOT-100003"}

    def test_approved_change_only(self):
        cid = fc.propose(self.threads, self.scenes, "req-1", "FSDW-100001",
                         "PLOT-100001", "PLOT-100002", "回収先を指定")["change_id"]
        self.assertIsNone(fc.effective(self.threads, fc.records(self.threads, self.scenes), self.scenes)[0]["payoff_scene_id"])
        with self.assertRaises(ValueError):
            fc.review(self.threads, self.scenes, cid, "approved", "", False)
        fc.review(self.threads, self.scenes, cid, "approved", "", True)
        self.assertEqual(fc.effective(self.threads, fc.records(self.threads, self.scenes), self.scenes)[0]["payoff_scene_id"], "PLOT-100002")
        self.assertIsNone(self.threads[0]["payoff_scene_id"])

    def test_rejected_change_ignored(self):
        cid = fc.propose(self.threads, self.scenes, "req-1", "FSDW-100001",
                         "PLOT-100001", "PLOT-100002", "変更")["change_id"]
        fc.review(self.threads, self.scenes, cid, "rejected", "", True)
        self.assertIsNone(fc.effective(self.threads, fc.records(self.threads, self.scenes), self.scenes)[0]["payoff_scene_id"])

    def test_unapproved_scene_rejected(self):
        with self.assertRaises(ValueError):
            fc.propose(self.threads, self.scenes, "req-1", "FSDW-100001",
                       "PLOT-100001", "PLOT-999999", "変更")

    def test_followup_and_stale_baseline(self):
        cid = fc.propose(self.threads, self.scenes, "req-1", "FSDW-100001",
                         "PLOT-100001", "PLOT-100002", "指定")["change_id"]
        fc.review(self.threads, self.scenes, cid, "approved", "", True)
        cid2 = fc.propose(self.threads, self.scenes, "req-2", "FSDW-100001",
                          "PLOT-100001", "PLOT-100003", "再指定")["change_id"]
        fc.review(self.threads, self.scenes, cid2, "approved", "", True)
        self.assertEqual(fc.effective(self.threads, fc.records(self.threads, self.scenes), self.scenes)[0]["payoff_scene_id"], "PLOT-100003")

    def test_duplicate_request_idempotent(self):
        cid = fc.propose(self.threads, self.scenes, "req-1", "FSDW-100001",
                         "PLOT-100001", "PLOT-100002", "変更")["change_id"]
        self.assertEqual(fc.propose(self.threads, self.scenes, "req-1", "FSDW-100001",
                                    "PLOT-100001", "PLOT-100002", "変更")["change_id"], cid)


if __name__ == "__main__":
    unittest.main()
