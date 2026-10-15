import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from story_relation_alignment import align


class StoryRelationAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"candidate_id": "CAND-100001", "kind": "event", "content": "出来事A", "source_id": "SRC-1", "decision_id": "DEC-1"},
            {"candidate_id": "CAND-100002", "kind": "event", "content": "出来事B", "source_id": "SRC-2", "decision_id": "DEC-2"},
            {"candidate_id": "CAND-100003", "kind": "character", "content": "人物A", "source_id": "SRC-3", "decision_id": "DEC-3"},
            {"candidate_id": "CAND-100004", "kind": "character", "content": "人物B", "source_id": "SRC-4", "decision_id": "DEC-4"},
        ]
        self.placements = [{"event_id": "CAND-100001", "phase": "序盤", "status": "approved"}]
        self.relation = {"relation_id": "CRL-100001", "from_character_id": "CAND-100003",
                         "to_character_id": "CAND-100004", "relation_type": "friend",
                         "phase": "序盤", "description": "友人", "evidence": "明示", "status": "approved"}

    def test_same_phase_without_causality(self):
        result = align(self.entries, ["序盤", "終盤"], self.placements, [], [self.relation])
        self.assertEqual(len(result["phases"][0]["character_relations"]), 1)
        self.assertEqual(len(result["phases"][0]["tiers"][0]), 1)
        self.assertTrue(result["phase_alignment_only"])
        self.assertEqual(result["relation_event_causality"], "not_established")
        self.assertEqual(result["relation_event_order"], "not_established")
        self.assertEqual(len(result["unplaced_events"]), 1)

    def test_unapproved_relations_excluded(self):
        for status in ("proposed", "rejected"):
            result = align(self.entries, ["序盤"], self.placements, [], [dict(self.relation, status=status)])
            self.assertEqual(result["phases"][0]["character_relations"], [])

    def test_missing_and_unknown_phase_separate(self):
        items = [dict(self.relation, relation_id="CRL-100002", phase=""),
                 dict(self.relation, relation_id="CRL-100003", phase="未登録")]
        result = align(self.entries, ["序盤"], self.placements, [], items)
        self.assertEqual(len(result["relations_without_phase"]), 1)
        self.assertEqual(len(result["relations_with_unrecognized_phase"]), 1)
        self.assertEqual(result["phases"][0]["character_relations"], [])

    def test_character_filter(self):
        result = align(self.entries, ["序盤"], self.placements, [], [self.relation],
                       character_id="CAND-100004")
        self.assertEqual(len(result["phases"][0]["character_relations"]), 1)
        result = align(self.entries, ["序盤"], self.placements, [], [self.relation],
                       character_id="CAND-100003")
        self.assertEqual(len(result["phases"][0]["character_relations"]), 1)
        with self.assertRaises(ValueError):
            align(self.entries, ["序盤"], self.placements, [], [self.relation],
                  character_id="CAND-999999")

    def test_missing_character_rejected(self):
        with self.assertRaises(ValueError):
            align(self.entries[:-1], ["序盤"], self.placements, [], [self.relation])

    def test_cli_summary(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "story_relation_alignment.py"), "--summary"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("character_relations", json.loads(p.stdout))


if __name__ == "__main__":
    unittest.main()
