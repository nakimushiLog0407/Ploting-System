import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "candidate_store.py"


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "candidate_store.py").write_bytes(SCRIPT.read_bytes())
        (self.root / "sources" / "records").mkdir(parents=True)
        (self.root / "sources" / "payloads").mkdir(parents=True)
        self.text = "冒頭😀\r\n「引用」\n"
        data = self.text.encode("utf-8")
        (self.root / "sources" / "payloads" / "SRC-000001.txt").write_bytes(data)
        record = {
            "source_id": "SRC-000001", "encoding": "UTF-8",
            "payload_path": "sources/payloads/SRC-000001.txt",
            "sha256": hashlib.sha256(data).hexdigest(), "byte_length": len(data),
        }
        (self.root / "sources" / "records" / "SRC-000001.json").write_text(
            json.dumps(record), encoding="utf-8"
        )

    def run_cli(self, *args, ok=True):
        proc = subprocess.run(
            [sys.executable, str(self.root / "scripts" / "candidate_store.py"), *args],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode == 0, ok, proc.stderr)
        return proc

    def args(self, request="test-001", content="発言の候補"):
        start = self.text.index("「")
        return ("save", "--request-id", request, "--kind", "dialogue",
                "--content", content, "--source-id", "SRC-000001",
                "--start", str(start), "--end", str(start + len("「引用」")))

    def test_save_idempotent_and_verify(self):
        first = json.loads(self.run_cli(*self.args()).stdout)
        self.assertEqual(first, {"status": "saved", "candidate_id": "CAND-000001"})
        second = json.loads(self.run_cli(*self.args()).stdout)
        self.assertEqual(second["status"], "already_saved")
        self.assertEqual(json.loads(self.run_cli("verify").stdout)["count"], 1)
        saved = json.loads((self.root / "candidates" / "records" / "CAND-000001.json").read_text())
        self.assertEqual(saved["evidence"]["quote"], "「引用」")
        self.assertEqual(saved["status"], "candidate")

    def test_conflicting_request_rejected(self):
        self.run_cli(*self.args())
        self.run_cli(*self.args(content="別の候補"), ok=False)

    def test_tampered_quote_rejected(self):
        self.run_cli(*self.args())
        path = self.root / "candidates" / "records" / "CAND-000001.json"
        item = json.loads(path.read_text())
        item["evidence"]["quote"] = "偽物"
        path.write_text(json.dumps(item), encoding="utf-8")
        self.run_cli("verify", ok=False)
        self.run_cli(*self.args(request="test-002"), ok=False)

    def test_tampered_source_rejected(self):
        self.run_cli(*self.args())
        (self.root / "sources" / "payloads" / "SRC-000001.txt").write_text("変更", encoding="utf-8")
        self.run_cli("verify", ok=False)


if __name__ == "__main__":
    unittest.main()
