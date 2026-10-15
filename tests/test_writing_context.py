import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from writing_context import build


class WritingContextTests(unittest.TestCase):
    def setUp(self):
        self.cards = [
            {"plot_id": "PLOT-100001", "kind": "chapter", "title": "第一章", "status": "approved", "parent_chapter_id": None, "position": 1},
            {"plot_id": "PLOT-100002", "kind": "scene", "title": "前の場面", "status": "approved", "parent_chapter_id": "PLOT-100001", "position": 1},
            {"plot_id": "PLOT-100003", "kind": "scene", "title": "対象", "status": "approved", "parent_chapter_id": "PLOT-100001", "position": 2},
        ]
        self.drafts = [
            {"draft_id": "DRAFT-100001", "scene_id": "PLOT-100002", "text": "承認された前の文章", "status": "approved"},
            {"draft_id": "DRAFT-100002", "scene_id": "PLOT-100003", "text": "未承認案", "status": "proposed"},
        ]
        self.canon = [{"candidate_id": "CAND-100001", "kind": "setting", "content": "元の設定"}]
        self.changes = ({"CAND-100001": "承認済みの新設定"}, [{"revision_id": "REV-100001", "status": "approved"}])

    def context(self, **kwargs):
        return build("PLOT-100003", self.cards, [], self.drafts, [], self.canon, self.changes, **kwargs)

    def test_only_approved_context_and_revision(self):
        result = self.context()
        self.assertEqual(result["preceding_approved_prose"][0]["approved_prose"], "承認された前の文章")
        self.assertEqual(result["approved_canon"][0]["content"], "承認済みの新設定")
        self.assertEqual(result["approved_canon"][0]["original_content"], "元の設定")
        self.assertIsNone(result["target_existing_approved_prose"])
        self.assertEqual(self.canon[0]["content"], "元の設定")

    def test_prose_limit(self):
        result = self.context(max_prose_chars=4)
        self.assertEqual(result["preceding_approved_prose"][0]["approved_prose"], "前の文章")
        self.assertTrue(result["preceding_approved_prose"][0]["truncated"])

    def test_unapproved_target_rejected(self):
        with self.assertRaises(ValueError):
            build("PLOT-999999", self.cards, [], self.drafts, [], self.canon, self.changes)

    def test_unplaced_scene_has_no_inferred_prior(self):
        self.cards[2]["parent_chapter_id"] = None
        self.cards[2]["position"] = None
        result = self.context()
        self.assertFalse(result["target_position_confirmed"])
        self.assertEqual(result["preceding_approved_prose"], [])

    def test_invalid_limits_rejected(self):
        with self.assertRaises(ValueError):
            self.context(previous_scenes=-1)


if __name__ == "__main__":
    unittest.main()
