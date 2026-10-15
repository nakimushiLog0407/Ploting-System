import json
import subprocess
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from character_relationship_timeline import timeline

class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"candidate_id": "CAND-100001", "kind": "character"},
            {"candidate_id": "CAND-100002", "kind": "character"},
            {"candidate_id": "CAND-100003", "kind": "character"},
        ]
        self.items = [
            {"relation_id": "CRL-100002", "from_character_id": "CAND-100002", "to_character_id": "CAND-100001", "relation_type": "hostile", "phase": "終盤", "description": "対立", "evidence": "", "status": "approved"},
            {"relation_id": "CRL-100001", "from_character_id": "CAND-100001", "to_character_id": "CAND-100002", "relation_type": "friend", "phase": "序盤", "description": "友人", "evidence": "", "status": "approved"},
            {"relation_id": "CRL-100003", "from_character_id": "CAND-100001", "to_character_id": "CAND-100002", "relation_type": "ally", "phase": "中盤", "description": "協力", "evidence": "", "status": "proposed"},
        ]

    def test_unordered_without_explicit_order(self):
        result = timeline(self.entries, self.items)
        self.assertEqual(len(result["pairs"][0]["unordered"]), 2)
        self.assertEqual(result["pairs"][0]["ordered"], [])

    def test_explicit_order(self):
        result = timeline(self.entries, self.items, phase_order=["序盤", "終盤"])
        self.assertEqual([x["relation_type"] for x in result["pairs"][0]["ordered"]], ["friend", "hostile"])
        self.assertEqual(result["pairs"][0]["unordered"], [])

    def test_partial_order(self):
        result = timeline(self.entries, self.items, phase_order=["終盤"])
        self.assertEqual(len(result["pairs"][0]["ordered"]), 1)
        self.assertEqual(len(result["pairs"][0]["unordered"]), 1)

    def test_filters_character(self):
        self.assertEqual(timeline(self.entries, self.items, character_id="CAND-100003")["pairs"], [])

    def test_duplicate_phase_order_fails(self):
        with self.assertRaises(ValueError):
            timeline(self.entries, self.items, phase_order=["序盤", "序盤"])

    def test_cli_summary(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "character_relationship_timeline.py"), "--summary"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("pairs", json.loads(p.stdout))

if __name__ == "__main__":
    unittest.main()
