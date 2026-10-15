import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from character_dossier import dossiers
from character_relationship_graph import build_graph


class TypedIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"candidate_id": "CAND-100001", "kind": "character", "content": "人物A", "source_id": "SRC-1", "quote": "A", "decision_id": "DEC-1"},
            {"candidate_id": "CAND-100002", "kind": "character", "content": "人物B", "source_id": "SRC-2", "quote": "B", "decision_id": "DEC-2"},
        ]
        self.typed = {"relation_id": "CRL-100001", "from_character_id": "CAND-100001",
                      "to_character_id": "CAND-100002", "relation_type": "friend",
                      "phase": "序盤", "description": "友人", "evidence": "原文",
                      "status": "approved"}

    def test_dossier_both_directions(self):
        result = dossiers(self.entries, [], [self.typed])
        self.assertEqual(result[0]["typed_relationships"][0]["direction"], "outgoing")
        self.assertEqual(result[1]["typed_relationships"][0]["direction"], "incoming")
        self.assertEqual(result[0]["typed_relationships"][0]["phase"], "序盤")

    def test_graph_approved_only(self):
        graph = build_graph(self.entries, [], [self.typed])
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(graph["edges"][0]["source"], "typed")
        self.assertEqual(graph["edges"][0]["relation"], "friend")

    def test_pending_and_rejected_hidden(self):
        for status in ("proposed", "rejected"):
            item = dict(self.typed, status=status)
            self.assertEqual(dossiers(self.entries, [], [item])[0]["typed_relationships"], [])
            self.assertEqual(build_graph(self.entries, [], [item])["edges"], [])

    def test_missing_character_fails(self):
        with self.assertRaises(ValueError):
            build_graph(self.entries[:1], [], [self.typed])
        with self.assertRaises(ValueError):
            dossiers(self.entries[:1], [], [self.typed])

    def test_multiple_phases_preserved(self):
        later = dict(self.typed, relation_id="CRL-100002", phase="終盤", relation_type="hostile")
        graph = build_graph(self.entries, [], [self.typed, later])
        self.assertEqual(len(graph["edges"]), 2)

if __name__ == "__main__":
    unittest.main()
