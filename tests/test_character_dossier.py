import json
import subprocess
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from character_dossier import dossiers

class CharacterDossierTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"candidate_id": "CAND-100001", "kind": "character", "content": "人物A", "source_id": "SRC-100001", "quote": "人物A", "decision_id": "DEC-100001"},
            {"candidate_id": "CAND-100002", "kind": "dialogue", "content": "台詞A", "source_id": "SRC-100001", "quote": "台詞A", "decision_id": "DEC-100002"},
        ]
        self.link = {"relationship_id": "REL-100001", "from_candidate_id": "CAND-100002", "to_candidate_id": "CAND-100001", "relation": "spoken_by", "status": "approved"}

    def test_incoming_dialogue(self):
        result = dossiers(self.entries, [self.link])
        self.assertEqual(result[0]["related"][0]["direction"], "incoming")
        self.assertEqual(result[0]["related"][0]["content"], "台詞A")

    def test_unapproved_link_excluded(self):
        self.assertEqual(dossiers(self.entries, [dict(self.link, status="proposed")])[0]["related"], [])

    def test_no_character(self):
        self.assertEqual(dossiers(self.entries[1:], []), [])

    def test_missing_endpoint(self):
        with self.assertRaises(ValueError):
            dossiers(self.entries[:1], [self.link])

    def test_live_cli(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "character_dossier.py"), "--summary"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("characters", json.loads(p.stdout))

if __name__ == "__main__":
    unittest.main()
