import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from manuscript_export import assemble, render_text


class ManuscriptExportTests(unittest.TestCase):
    def setUp(self):
        self.cards = [
            {"plot_id": "PLOT-100001", "kind": "chapter", "title": "第一章", "status": "approved", "parent_chapter_id": None, "position": 1},
            {"plot_id": "PLOT-100002", "kind": "scene", "title": "場面A", "status": "approved", "parent_chapter_id": "PLOT-100001", "position": 1},
            {"plot_id": "PLOT-100003", "kind": "scene", "title": "場面B", "status": "approved", "parent_chapter_id": None, "position": None},
        ]
        self.drafts = [
            {"draft_id": "DRAFT-100001", "scene_id": "PLOT-100002", "text": "承認された文章", "status": "approved"},
            {"draft_id": "DRAFT-100002", "scene_id": "PLOT-100003", "text": "未配置の文章", "status": "approved"},
            {"draft_id": "DRAFT-100003", "scene_id": "PLOT-100002", "text": "未承認の文章", "status": "proposed"},
        ]

    def test_approved_ordered_prose_only(self):
        result = assemble(self.cards, [], self.drafts, [])
        text = render_text(result)
        self.assertIn("承認された文章", text)
        self.assertNotIn("未配置の文章", text)
        self.assertNotIn("未承認の文章", text)
        self.assertEqual(result["unplaced_scene_ids"], ["PLOT-100003"])

    def test_approved_revision_and_original_preservation(self):
        revisions = [{"revision_id": "PREV-100001", "draft_id": "DRAFT-100001", "before": "承認された文章", "after": "承認された改稿", "status": "approved"}]
        result = assemble(self.cards, [], self.drafts, revisions)
        self.assertIn("承認された改稿", render_text(result))
        self.assertEqual(self.drafts[0]["text"], "承認された文章")

    def test_missing_prose_reported_not_filled(self):
        result = assemble(self.cards, [], [], [])
        self.assertEqual(result["missing_approved_prose"][0]["scene_id"], "PLOT-100002")
        self.assertFalse(result["automatic_fill"])

    def test_explicit_move_changes_export_order(self):
        moves = [{"move_id": "PMOV-100001", "plot_id": "PLOT-100003",
                  "before": {"parent_chapter_id": None, "position": None},
                  "after": {"parent_chapter_id": "PLOT-100001", "position": 2}, "status": "approved"}]
        result = assemble(self.cards, moves, self.drafts, [])
        text = render_text(result)
        self.assertLess(text.index("承認された文章"), text.index("未配置の文章"))


if __name__ == "__main__":
    unittest.main()
