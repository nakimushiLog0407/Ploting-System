import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from setting_dossier import build_dossiers


class SettingDossierTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"candidate_id": "CAND-100001", "kind": "setting", "content": "架空都市の設定", "quote": "架空都市", "source_id": "SRC-100001", "decision_id": "DEC-100001"},
            {"candidate_id": "CAND-100002", "kind": "character", "content": "登場人物", "quote": "人物", "source_id": "SRC-100001", "decision_id": "DEC-100002"},
        ]
        self.link = {"relationship_id": "REL-100001", "from_candidate_id": "CAND-100002", "to_candidate_id": "CAND-100001", "relation": "related_to", "status": "approved"}

    def test_approved_link(self):
        result = build_dossiers(self.entries, [self.link])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["related"][0]["direction"], "incoming")
        self.assertEqual(result[0]["related"][0]["content"], "登場人物")

    def test_unapproved_link_is_excluded(self):
        result = build_dossiers(self.entries, [dict(self.link, status="proposed")])
        self.assertEqual(result[0]["related"], [])

    def test_only_settings_are_dossiers(self):
        self.assertEqual(build_dossiers(self.entries[1:], []), [])

    def test_missing_related_entry_fails(self):
        with self.assertRaises(ValueError):
            build_dossiers(self.entries[:1], [self.link])

    def test_approved_category_visible(self):
        classifications = [{"candidate_id": "CAND-100001", "category": "place", "status": "approved"}]
        result = build_dossiers(self.entries, [], classifications)
        self.assertEqual(result[0]["category"], "place")

    def test_pending_or_rejected_classification_is_unclassified(self):
        for status in ("proposed", "rejected"):
            classifications = [{"candidate_id": "CAND-100001", "category": "place", "status": status}]
            result = build_dossiers(self.entries, [], classifications)
            self.assertEqual(result[0]["category"], "unclassified")

    def test_no_classification_is_unclassified(self):
        self.assertEqual(build_dossiers(self.entries, [])[0]["category"], "unclassified")

    def test_conflicting_approved_categories_fail(self):
        with self.assertRaises(ValueError):
            build_dossiers(self.entries, [], [
                {"candidate_id": "CAND-100001", "category": "place", "status": "approved"},
                {"candidate_id": "CAND-100001", "category": "term", "status": "approved"},
            ])

    def test_cli_runs_with_current_archive(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "setting_dossier.py"), "--summary"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("total", json.loads(p.stdout))


if __name__ == "__main__":
    unittest.main()
