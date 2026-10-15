import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import project_query as pq


class ProjectQueryTests(unittest.TestCase):
    def setUp(self):
        self.data = {"candidates": [], "decisions": [], "cards": [], "moves": [],
                     "drafts": [], "revisions": [],
                     "plot_review": {"findings": []}, "prose_review": {"findings": []}}

    def test_dashboard(self):
        result = pq.query("dashboard", self.data)
        self.assertEqual(result["interface_version"], 1)
        self.assertEqual(result["data"]["canon"]["total"], 0)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["approval_performed"])

    def test_inbox_and_progress(self):
        self.assertEqual(pq.query("inbox", self.data)["data"]["total"], 0)
        self.assertEqual(pq.query("progress", self.data)["data"]["summary"]["scenes"], 0)

    def test_manuscript(self):
        result = pq.query("manuscript", self.data)
        self.assertEqual(result["data"]["chapters"], [])
        self.assertFalse(result["data"]["automatic_fill"])

    def test_context_requires_explicit_scene(self):
        with self.assertRaisesRegex(ValueError, "scene-id"):
            pq.query("context", self.data)

    def test_context_does_not_invent_scene(self):
        with patch.object(pq, "build_catalog", return_value=[]):
            with self.assertRaises(ValueError):
                pq.query("context", self.data, scene_id="PLOT-999999")

    def test_unsupported_command_rejected(self):
        with self.assertRaises(ValueError):
            pq.query("approve", self.data)


if __name__ == "__main__":
    unittest.main()
