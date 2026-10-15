import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prose_diagnostics import diagnose


class ProseDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.cards = [
            {"plot_id": "PLOT-100001", "kind": "chapter", "title": "第一章", "status": "approved", "parent_chapter_id": None, "position": 1},
            {"plot_id": "PLOT-100002", "kind": "scene", "title": "場面A", "status": "approved", "parent_chapter_id": "PLOT-100001", "position": 1},
            {"plot_id": "PLOT-100003", "kind": "scene", "title": "場面B", "status": "approved", "parent_chapter_id": None, "position": None},
        ]
        self.drafts = [{"draft_id": "DRAFT-100001", "scene_id": "PLOT-100002",
                        "text": "承認済み文章", "status": "approved"}]

    def codes(self, drafts=None, revisions=None):
        return [x["code"] for x in diagnose(self.cards, [], self.drafts if drafts is None else drafts,
                                             [] if revisions is None else revisions)["findings"]]

    def test_unplaced_scene_reported(self):
        self.assertIn("SCENE_UNPLACED", self.codes())

    def test_missing_prose_reported(self):
        self.assertIn("APPROVED_SCENE_WITHOUT_PROSE", self.codes(drafts=[]))

    def test_pending_draft_not_treated_as_approved(self):
        drafts = self.drafts + [{"draft_id": "DRAFT-100002", "scene_id": "PLOT-100002",
                                 "text": "未承認案", "status": "proposed"}]
        self.assertIn("PENDING_PROSE_DRAFT", self.codes(drafts=drafts))

    def test_pending_revision_reported_without_replacing_prose(self):
        revisions = [{"revision_id": "PREV-100001", "draft_id": "DRAFT-100001",
                      "before": "承認済み文章", "after": "未承認改稿", "status": "proposed"}]
        self.assertIn("PENDING_PROSE_REVISION", self.codes(revisions=revisions))
        self.assertEqual(self.drafts[0]["text"], "承認済み文章")

    def test_duplicate_scene_positions_rejected_by_existing_plot_rules(self):
        self.cards.append({"plot_id": "PLOT-100004", "kind": "scene", "title": "場面C",
                           "status": "approved", "parent_chapter_id": "PLOT-100001", "position": 1})
        with self.assertRaisesRegex(ValueError, "Duplicate approved plot position"):
            self.codes()

    def test_no_semantic_claims(self):
        result = diagnose(self.cards, [], self.drafts, [])
        self.assertFalse(result["semantic_continuity_checked"])
        self.assertFalse(result["automatic_corrections"])
        self.assertTrue(all(not x["literary_contradiction_proven"] for x in result["findings"]))


if __name__ == "__main__":
    unittest.main()
