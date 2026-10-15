import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from project_dashboard import build


class ProjectDashboardTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [{"candidate_id": "CAND-1"}, {"candidate_id": "CAND-2"},
                           {"candidate_id": "CAND-3"}]
        self.decisions = [{"candidate_id": "CAND-1", "decision": "approved"},
                          {"candidate_id": "CAND-2", "decision": "rejected"}]
        self.cards = [
            {"plot_id": "PLOT-100001", "kind": "chapter", "title": "第一章", "status": "approved",
             "parent_chapter_id": None, "position": 1},
            {"plot_id": "PLOT-100002", "kind": "scene", "title": "場面", "status": "approved",
             "parent_chapter_id": "PLOT-100001", "position": 1},
            {"plot_id": "PLOT-100003", "kind": "scene", "title": "候補", "status": "proposed",
             "parent_chapter_id": None, "position": None},
        ]
        self.drafts = [{"draft_id": "DRAFT-100001", "scene_id": "PLOT-100002",
                        "text": "未承認案", "status": "proposed"}]
        self.plot_review = {"findings": [{"subject_id": "PLOT-100002", "code": "CHECK",
                                         "finding_sha256": "a" * 64, "review": "unreviewed"}]}
        self.prose_review = {"findings": []}

    def dashboard(self):
        return build(self.candidates, self.decisions, self.cards, [], self.drafts, [],
                     self.plot_review, self.prose_review)

    def test_counts_and_review_inbox(self):
        result = self.dashboard()
        self.assertEqual(result["canon"], {"total": 3, "approved": 1, "rejected": 1, "pending": 1})
        self.assertEqual(result["plot_cards"]["pending"], 1)
        self.assertEqual(result["writing"]["scenes"], 1)
        self.assertEqual(result["writing"]["awaiting_approval"], 1)
        self.assertEqual(result["review_inbox"]["total"], 4)

    def test_no_automatic_approval(self):
        result = self.dashboard()
        self.assertFalse(result["automatic_changes"])
        self.assertTrue(result["approval_is_explicit"])
        self.assertEqual(self.drafts[0]["status"], "proposed")

    def test_unknown_candidate_decision_rejected(self):
        self.decisions.append({"candidate_id": "CAND-999", "decision": "approved"})
        with self.assertRaises(ValueError):
            self.dashboard()

    def test_empty_project(self):
        result = build([], [], [], [], [], [], {"findings": []}, {"findings": []})
        self.assertEqual(result["canon"]["total"], 0)
        self.assertEqual(result["review_inbox"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
