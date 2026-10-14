import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from canon_catalog import search, KINDS


class CanonCatalogTests(unittest.TestCase):
    def test_search_and_filter(self):
        entries = [
            {"kind": "character", "source_id": "SRC-000001", "content": "主人公は旅人", "quote": "旅人"},
            {"kind": "event", "source_id": "SRC-000002", "content": "帰還", "quote": "帰った"},
        ]
        self.assertEqual(len(search(entries, kind="character")), 1)
        self.assertEqual(len(search(entries, query="旅人")), 1)
        self.assertEqual(len(search(entries, source_id="SRC-000002")), 1)
        self.assertEqual(search(entries, query="存在しない"), [])
        with self.assertRaises(ValueError):
            search(entries, kind="invalid")

    def test_approved_candidate_visible(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "canon_catalog.py")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        entry = next(e for e in payload["entries"] if e["candidate_id"] == "CAND-000001")
        self.assertEqual(entry["kind"], "dialogue")
        self.assertEqual(entry["decision_id"], "DEC-000001")
        self.assertEqual(entry["quote"], "「改行と空白を確認します」")

    def test_summary(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "canon_catalog.py"), "--summary"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["total"], sum(payload["by_kind"].values()))
        self.assertEqual(set(payload["by_kind"]), set(KINDS))


if __name__ == "__main__":
    unittest.main()
