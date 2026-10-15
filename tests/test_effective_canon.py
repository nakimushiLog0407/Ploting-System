import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import canon_revision as cr
from effective_canon import effective_entries
from character_dossier import dossiers
from setting_dossier import build_dossiers
from story_chronology_view import build_view


class EffectiveCanonTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, folder in (("PROPOSALS", "proposals"), ("REVIEWS", "reviews")):
            p = patch.object(cr, name, Path(tmp.name) / folder)
            p.start()
            self.addCleanup(p.stop)
        self.entries = [
            {"candidate_id": "CAND-100001", "kind": "character", "content": "元の人物",
             "source_id": "SRC-100001", "quote": "元の人物", "decision_id": "DEC-100001"},
            {"candidate_id": "CAND-100002", "kind": "setting", "content": "元の世界",
             "source_id": "SRC-100001", "quote": "元の世界", "decision_id": "DEC-100002"},
            {"candidate_id": "CAND-100003", "kind": "event", "content": "元の出来事",
             "source_id": "SRC-100001", "quote": "元の出来事", "decision_id": "DEC-100003"},
        ]

    def test_unapproved_revision_is_not_effective(self):
        cr.propose(self.entries, "req-1", "CAND-100001", "新しい人物", "理由", [])
        result = effective_entries(self.entries)
        self.assertEqual(result[0]["content"], "元の人物")
        self.assertIsNone(result[0]["effective_revision_id"])

    def test_approved_revision_propagates_without_changing_source(self):
        for i, text in enumerate(("新しい人物", "新しい世界", "新しい出来事")):
            rid = cr.propose(self.entries, "req-" + str(i), self.entries[i]["candidate_id"], text, "理由", [])["revision_id"]
            cr.review(self.entries, rid, "approved", "", True)
        result = effective_entries(self.entries)
        self.assertEqual(dossiers(result, [])[0]["content"], "新しい人物")
        self.assertEqual(build_dossiers(result, [])[0]["content"], "新しい世界")
        chronology = build_view(result, ["序盤"],
                                [{"event_id": "CAND-100003", "phase": "序盤", "status": "approved"}], [])
        self.assertEqual(chronology["phases"][0]["tiers"][0][0]["content"], "新しい出来事")
        self.assertEqual(result[0]["original_content"], "元の人物")
        self.assertEqual(result[0]["quote"], "元の人物")
        self.assertEqual(self.entries[0]["content"], "元の人物")

    def test_rejected_revision_never_propagates(self):
        rid = cr.propose(self.entries, "req-1", "CAND-100002", "不採用", "理由", [])["revision_id"]
        cr.review(self.entries, rid, "rejected", "", True)
        self.assertEqual(effective_entries(self.entries)[1]["content"], "元の世界")


if __name__ == "__main__":
    unittest.main()
