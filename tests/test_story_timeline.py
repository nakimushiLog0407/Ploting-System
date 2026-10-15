import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import story_timeline as st

class StoryTimelineTests(unittest.TestCase):
    def test_phases_validate(self):
        self.assertEqual(st.validate_phases(["序盤", "中盤", "終盤"]), ["序盤", "中盤", "終盤"])
        for phases in ([], ["序盤", "序盤"], ["", "終盤"], "序盤"):
            with self.assertRaises(ValueError):
                st.validate_phases(phases)

    def test_existing_records_verify(self):
        self.assertIsInstance(st.records(), list)

    def test_review_needs_user_confirmation(self):
        with self.assertRaises(ValueError):
            st.review("STL-999999", "approved", "", False)

    def test_proposal_not_auto_approved(self):
        with patch.object(st, "records", return_value=[{"timeline_id": "STL-000001", "request_id": "r", "phases": ["序盤"], "reason": "", "status": "proposed"}]):
            with self.assertRaises(ValueError):
                st.propose("another", ["終盤"], "")

    def test_approved_phases_empty_without_approval(self):
        with patch.object(st, "records", return_value=[{"status": "proposed", "phases": ["序盤"]}]):
            self.assertEqual(st.approved_phases(), [])

if __name__ == "__main__":
    unittest.main()
