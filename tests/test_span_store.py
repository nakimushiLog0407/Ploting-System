
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / 'scripts' / 'span_store.py'
)


class SpanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        root = Path(self.tmp.name)
        (root / 'scripts').mkdir()
        (root / 'scripts' / 'span_store.py').write_bytes(
            SCRIPT.read_bytes()
        )

        (root / 'sources' / 'records').mkdir(parents=True)
        (root / 'sources' / 'payloads').mkdir(parents=True)

        self.script = root / 'scripts' / 'span_store.py'
        self.root = root

        self.original = '冒頭😀\r\n  「台詞」\n末尾'
        data = self.original.encode('utf-8')

        (
            root / 'sources' / 'payloads'
            / 'SRC-000001.txt'
        ).write_bytes(data)

        rec = {
            'source_id': 'SRC-000001',
            'payload_path':
                'sources/payloads/SRC-000001.txt',
            'sha256': hashlib.sha256(data).hexdigest(),
            'byte_length': len(data),
        }

        (
            root / 'sources' / 'records'
            / 'SRC-000001.json'
        ).write_text(
            json.dumps(rec),
            encoding='utf-8',
        )

    def run_cmd(self, *args, ok=True):
        result = subprocess.run(
            [
                sys.executable,
                str(self.script),
                *map(str, args),
            ],
            capture_output=True,
        )

        self.assertEqual(
            result.returncode == 0,
            ok,
            result.stderr.decode(),
        )
        return result

    def test_extract_and_verify(self):
        start = self.original.index('「')
        end = self.original.index('」') + 1

        rec = json.loads(
            self.run_cmd(
                'extract',
                'SRC-000001',
                start,
                end,
            ).stdout
        )

        self.assertEqual(rec['quote'], '「台詞」')

        path = self.root / 'candidate.json'
        path.write_text(
            json.dumps(rec, ensure_ascii=False),
            encoding='utf-8',
        )

        self.run_cmd('verify', path)

        rec['quote'] = '改ざん'
        path.write_text(
            json.dumps(rec, ensure_ascii=False),
            encoding='utf-8',
        )

        self.run_cmd('verify', path, ok=False)

    def test_out_of_range(self):
        self.run_cmd(
            'extract',
            'SRC-000001',
            0,
            1000,
            ok=False,
        )
        self.run_cmd(
            'extract',
            'SRC-000001',
            -1,
            2,
            ok=False,
        )

    def test_modified_source_rejected(self):
        (
            self.root / 'sources' / 'payloads'
            / 'SRC-000001.txt'
        ).write_text('改ざん', encoding='utf-8')

        self.run_cmd(
            'extract',
            'SRC-000001',
            0,
            1,
            ok=False,
        )


if __name__ == '__main__':
    unittest.main()
