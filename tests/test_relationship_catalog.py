import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from relationship_catalog import validate, browse, verify_relationships


class RelationshipTests(unittest.TestCase):
    def base(self):
        return {
            "schema_version": 1, "relationship_id": "REL-000001", "request_id": "test-link-001",
            "from_candidate_id": "CAND-000001", "to_candidate_id": "CAND-000002",
            "relation": "related_to", "status": "proposed", "evidence": "",
            "created_at": "2026-10-14T00:00:00+00:00",
            "reviewed_by": None, "reviewed_at": None,
        }

    def test_valid_proposal(self):
        self.assertEqual(validate(self.base())["status"], "proposed")

    def test_rejects_unreviewed_approval(self):
        item = self.base()
        item["status"] = "approved"
        with self.assertRaises(ValueError):
            validate(item)

    def test_valid_explicit_approval(self):
        item = self.base()
        item.update(status="approved", reviewed_by="user", reviewed_at="2026-10-14T01:00:00+00:00")
        self.assertEqual(validate(item)["status"], "approved")

    def test_self_relation_rejected(self):
        item = self.base()
        item["to_candidate_id"] = item["from_candidate_id"]
        with self.assertRaises(ValueError):
            validate(item)

    def test_repository_links_are_valid(self):
        count = verify_relationships()
        self.assertGreaterEqual(count, 0)
        approved = browse(status="approved")
        self.assertTrue(all(item["status"] == "approved" for item in approved))
        self.assertLessEqual(len(approved), count)


if __name__ == "__main__":
    unittest.main()
