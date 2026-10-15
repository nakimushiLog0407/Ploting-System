import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from writing_progress import summarize


class WritingProgressTests(unittest.TestCase):
    def setUp(self):
        self.cards = [
            {"plot_id": "PLOT-100001", "kind": "chapter", "title": "第一章", "status": "approved", "parent_chapter_id": None, "position": 1},
            {"plot_id": "PLOT-100002", "kind": "scene", "title": "未作成", "status": "approved", "parent_chapter_id": "PLOT-100001", "position": 1},
            {"plot_id": "PLOT-100003", "kind": "scene", "title": "承認待ち", "status": "approved", "parent_chapter_id": "PLOT-100001", "position": 2},
            {"plot_id": "PLOT-100004", "kind": "scene", "title": "承認済み", "status": "approved", "parent_chapter_id": None, "position": None},
            {"plot_id": "PLOT-100005", "kind": "scene", "title": "改稿待ち", "status": "approved", "parent_chapter_id": "PLOT-100001", "position": 3},
            {"plot_id": "PLOT-100006", "kind": "scene", "title": "未承認", "status": "proposed", "parent_chapter_id": None, "position": None},
        ]
        self.drafts = [
            {"draft_id": "DRAFT-100001", "scene_id": "PLOT-100003", "text": "未承認案", "status": "proposed"},
            {"draft_id": "DRAFT-100002", "scene_id": "PLOT-100004", "text": "承認済み", "status": "approved"},
            {"draft_id": "DRAFT-100003", "scene_id": "PLOT-100005", "text": "承認済み", "status": "approved"},
        ]
        self.revisions = [{"revision_id": "PREV-100001", "draft_id": "DRAFT-100003",
                           "before": "承認済み", "after": "改稿案", "status": "proposed"}]

    def test_all_states(self):
        result = summarize(self.cards, [], self.drafts, self.revisions)
        self.assertEqual(result["summary"]["scenes"], 4)
        for status in ("not_started", "awaiting_approval", "approved", "revision_pending"):
            self.assertEqual(result["summary"][status], 1)
        self.assertEqual(result["summary"]["approved_prose_scenes"], 2)

    def test_unplaced_scene_remains_visible(self):
        result = summarize(self.cards, [], self.drafts, self.revisions)
        self.assertEqual(result["scenes_without_chapter"][0]["scene_id"], "PLOT-100004")
        self.assertIn("PLOT-100004", result["unplaced_scene_ids"])

    def test_pending_prose_not_counted_complete(self):
        result = summarize(self.cards, [], self.drafts, self.revisions)
        self.assertEqual(result["chapters"][0]["counts"]["awaiting_approval"], 1)
        self.assertFalse(result["sequence_inferred"])

    def test_approved_revision_removes_pending_state(self):
        revisions = [{**self.revisions[0], "status": "approved"}]
        result = summarize(self.cards, [], self.drafts, revisions)
        self.assertEqual(result["summary"]["revision_pending"], 0)
        self.assertEqual(result["summary"]["approved"], 2)

    def test_empty_project(self):
        result = summarize([], [], [], [])
        self.assertEqual(result["summary"]["scenes"], 0)
        self.assertEqual(result["chapters"], [])


if __name__ == "__main__":
    unittest.main()
