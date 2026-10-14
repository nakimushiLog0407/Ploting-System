import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ReviewTests(unittest.TestCase):
    def test_existing_candidate(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "review_candidate.py"), "CAND-000001"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)
        self.assertEqual(item["evidence"]["quote"], "「改行と空白を確認します」")
        self.assertIn(item["effective_status"], ("candidate", "approved", "rejected"))

    def test_missing_candidate(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "review_candidate.py"), "CAND-999999"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

if __name__ == "__main__":
    unittest.main()
