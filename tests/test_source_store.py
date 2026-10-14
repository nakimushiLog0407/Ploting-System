import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'source_store.py'

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'sources' / 'records').mkdir(parents=True)
        (self.root / 'sources' / 'payloads').mkdir(parents=True)
        # Keep actual code identical while isolating the data root.
        (self.root / 'scripts' / 'source_store.py').write_bytes(SCRIPT.read_bytes())
        self.script = self.root / 'scripts' / 'source_store.py'
        self.original = b'\xef\xbb\xbf' + '一行目\r\n\r\n  二行目\n'.encode('utf-8')
        self.input = self.root / 'input.txt'
        self.input.write_bytes(self.original)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, success=True):
        p = subprocess.run([sys.executable, str(self.script), *args], capture_output=True)
        if success:
            self.assertEqual(p.returncode, 0, p.stderr.decode())
        else:
            self.assertNotEqual(p.returncode, 0)
        return p

    def test_roundtrip_and_idempotency(self):
        p = self.run_cli('save', '--file', str(self.input), '--request-id', 'idea-001')
        self.assertEqual(json.loads(p.stdout)['source_id'], 'SRC-000001')
        p2 = self.run_cli('save', '--file', str(self.input), '--request-id', 'idea-001')
        self.assertEqual(json.loads(p2.stdout)['status'], 'already_saved')
        self.assertEqual(self.run_cli('read', 'SRC-000001').stdout, self.original)
        self.assertEqual(json.loads(self.run_cli('verify').stdout)['count'], 1)
        self.run_cli('save', '--file', str(self.input), '--request-id', 'idea-002')
        self.assertEqual(json.loads(self.run_cli('verify').stdout)['count'], 2)

    def test_same_request_different_content_rejected(self):
        self.run_cli('save', '--file', str(self.input), '--request-id', 'idea-001')
        self.input.write_bytes(b'changed')
        self.run_cli('save', '--file', str(self.input), '--request-id', 'idea-001', success=False)

    def test_tampering_detected_and_new_save_blocked(self):
        self.run_cli('save', '--file', str(self.input), '--request-id', 'idea-001')
        (self.root / 'sources' / 'payloads' / 'SRC-000001.txt').write_bytes(b'tampered')
        self.run_cli('verify', success=False)
        self.run_cli('save', '--file', str(self.input), '--request-id', 'idea-002', success=False)

    def test_invalid_utf8_rejected(self):
        self.input.write_bytes(b'\xff')
        self.run_cli('save', '--file', str(self.input), '--request-id', 'idea-001', success=False)

if __name__ == '__main__':
    unittest.main()
