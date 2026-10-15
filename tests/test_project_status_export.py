import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from project_status_export import aggregate, save


class ProjectStatusExportTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = {
            "canon": {"total": 2, "approved": 1, "rejected": 0, "pending": 1},
            "plot_cards": {"total": 1, "approved": 1, "rejected": 0, "pending": 0},
            "writing": {"scenes": 1, "not_started": 0, "awaiting_approval": 1,
                        "approved": 0, "revision_pending": 0, "approved_prose_scenes": 0},
            "unplaced_scene_ids": ["PRIVATE-SCENE-ID"],
            "review_inbox": {"total": 1, "by_category": {"prose_draft": 1}},
            "diagnostics": {"plot_findings": 0, "prose_findings": 0},
            "secret": "UNPUBLISHED NOVEL TEXT",
        }

    def test_export_excludes_story_and_identifiers(self):
        result = aggregate(self.dashboard)
        text = json.dumps(result)
        self.assertNotIn("UNPUBLISHED NOVEL TEXT", text)
        self.assertNotIn("PRIVATE-SCENE-ID", text)
        self.assertFalse(result["contains_story_text"])
        self.assertFalse(result["contains_identifiers"])

    def test_exclusive_file_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "status.json"
            result = aggregate(self.dashboard)
            save(result, path)
            self.assertEqual(json.loads(path.read_text())["schema_version"], 1)
            with self.assertRaises(ValueError):
                save(result, path)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "original"
            source.write_text("keep")
            link = Path(temp) / "link"
            link.symlink_to(source)
            with self.assertRaises(ValueError):
                save(aggregate(self.dashboard), link)
            self.assertEqual(source.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
