import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "scripts").mkdir()
        for name in ("decision_store.py", "candidate_store.py"):
            (self.root / "scripts" / name).write_bytes((ROOT / "scripts" / name).read_bytes())
        payload = "「テスト」\n".encode("utf-8")
        (self.root / "sources" / "records").mkdir(parents=True)
        (self.root / "sources" / "payloads").mkdir(parents=True)
        (self.root / "sources" / "payloads" / "SRC-000001.txt").write_bytes(payload)
        meta = {
            "source_id": "SRC-000001", "encoding": "UTF-8",
            "payload_path": "sources/payloads/SRC-000001.txt",
            "sha256": hashlib.sha256(payload).hexdigest(), "byte_length": len(payload),
        }
        (self.root / "sources" / "records" / "SRC-000001.json").write_text(json.dumps(meta), encoding="utf-8")
        self.cli("candidate_store.py", "save", "--request-id", "candidate-1",
                 "--kind", "dialogue", "--content", "候補",
                 "--source-id", "SRC-000001", "--start", "0", "--end", "5")

    def cli(self, script, *args, ok=True):
        result = subprocess.run([sys.executable, str(self.root / "scripts" / script), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stderr)
        return result

    def decision_args(self, request="decision-1", decision="approved"):
        return ("record", "--request-id", request, "--candidate-id", "CAND-000001",
                "--decision", decision, "--confirm-user-decision")

    def test_approval_idempotency(self):
        first = json.loads(self.cli("decision_store.py", *self.decision_args()).stdout)
        self.assertEqual(first["decision_id"], "DEC-000001")
        second = json.loads(self.cli("decision_store.py", *self.decision_args()).stdout)
        self.assertEqual(second["status"], "already_saved")
        self.assertEqual(json.loads(self.cli("decision_store.py", "verify").stdout)["count"], 1)
        original = json.loads((self.root / "candidates" / "records" / "CAND-000001.json").read_text())
        self.assertEqual(original["status"], "candidate")

    def test_rejection(self):
        self.cli("decision_store.py", *self.decision_args(decision="rejected"))
        record = json.loads((self.root / "decisions" / "records" / "DEC-000001.json").read_text())
        self.assertEqual(record["decision"], "rejected")

    def test_confirmation_required(self):
        args = self.decision_args()[:-1]
        self.cli("decision_store.py", *args, ok=False)

    def test_conflicting_decision_rejected(self):
        self.cli("decision_store.py", *self.decision_args())
        self.cli("decision_store.py", *self.decision_args("decision-2", "rejected"), ok=False)

    def test_tampering_rejected(self):
        self.cli("decision_store.py", *self.decision_args())
        path = self.root / "candidates" / "records" / "CAND-000001.json"
        data = json.loads(path.read_text())
        data["content"] = "改変"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.cli("decision_store.py", "verify", ok=False)


if __name__ == "__main__":
    unittest.main()
