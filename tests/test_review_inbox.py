import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from review_inbox import build


class ReviewInboxTests(unittest.TestCase):
    def test_pending_items_from_all_categories(self):
        candidates = [{"candidate_id": "CAND-100001"}, {"candidate_id": "CAND-100002"}]
        decisions = [{"candidate_id": "CAND-100001", "decision": "approved"}]
        cards = [{"plot_id": "PLOT-100001", "status": "proposed"}]
        drafts = [{"draft_id": "DRAFT-100001", "status": "proposed"}]
        revisions = [{"revision_id": "PREV-100001", "status": "proposed"}]
        plot = {"findings": [{"subject_id": "PLOT-100002", "code": "SCENE_UNPLACED",
                              "finding_sha256": "a" * 64, "review": "unreviewed"}]}
        prose = {"findings": [{"subject_id": "PLOT-100003", "code": "APPROVED_SCENE_WITHOUT_PROSE",
                               "finding_sha256": "b" * 64, "review": "needs_revision"}]}
        result = build(candidates, decisions, cards, drafts, revisions, plot, prose)
        self.assertEqual(result["total"], 6)
        self.assertEqual(set(result["by_category"]), {"canon_candidate", "plot_card", "prose_draft",
                                                       "prose_revision", "plot_diagnostic", "prose_diagnostic"})
        self.assertFalse(result["automatic_approval"])
        self.assertFalse(result["automatic_changes"])

    def test_reviewed_intentional_and_deferred_not_pending(self):
        plot = {"findings": [{"subject_id": "PLOT-1", "code": "A", "finding_sha256": "a" * 64,
                              "review": "intentional"},
                             {"subject_id": "PLOT-2", "code": "B", "finding_sha256": "b" * 64,
                              "review": "defer"}]}
        result = build([], [], [], [], [], plot, {"findings": []})
        self.assertEqual(result["total"], 0)

    def test_empty_inbox(self):
        result = build([], [], [], [], [], {"findings": []}, {"findings": []})
        self.assertEqual(result["items"], [])
        self.assertEqual(result["total"], 0)

    def test_decided_candidate_excluded(self):
        result = build([{"candidate_id": "CAND-1"}],
                       [{"candidate_id": "CAND-1", "decision": "rejected"}],
                       [], [], [], {"findings": []}, {"findings": []})
        self.assertEqual(result["total"], 0)


if __name__ == "__main__":
    unittest.main()
