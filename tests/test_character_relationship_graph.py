import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from character_relationship_graph import build_graph


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"candidate_id": "CAND-100001", "kind": "character", "content": "人物A", "source_id": "SRC-100001", "decision_id": "DEC-100001"},
            {"candidate_id": "CAND-100002", "kind": "character", "content": "人物B", "source_id": "SRC-100001", "decision_id": "DEC-100002"},
            {"candidate_id": "CAND-100003", "kind": "setting", "content": "都市", "source_id": "SRC-100001", "decision_id": "DEC-100003"},
        ]
        self.relations = [
            {"relationship_id": "REL-100001", "from_candidate_id": "CAND-100001", "to_candidate_id": "CAND-100002", "relation": "related_to", "status": "approved", "evidence": "明示的な関係"},
            {"relationship_id": "REL-100002", "from_candidate_id": "CAND-100001", "to_candidate_id": "CAND-100003", "relation": "related_to", "status": "approved", "evidence": ""},
            {"relationship_id": "REL-100003", "from_candidate_id": "CAND-100002", "to_candidate_id": "CAND-100001", "relation": "related_to", "status": "proposed", "evidence": ""},
        ]

    def test_only_approved_character_edges(self):
        graph = build_graph(self.entries, self.relations)
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(graph["edges"][0]["relation"], "related_to")

    def test_empty_graph(self):
        self.assertEqual(build_graph([], []), {"nodes": [], "edges": []})

    def test_cli_summary(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "character_relationship_graph.py"), "--summary"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("relationships", json.loads(p.stdout))


if __name__ == "__main__":
    unittest.main()
