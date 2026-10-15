import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_chatgpt_connector import verify


class ConnectorContractTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "schema_version": 1, "repository": "example-user/novel-project",
            "branch": "main", "mode": "chatgpt_github_connector",
            "execution": "chatgpt_initiated_only", "openai_api_required": False,
            "github_actions_required_for_reads": False,
            "read_only_queries": {"sources": "sources/records/*.json"},
            "constraints": ["approval", "no API", "no writes", "private repository",
                            "verify before claiming success"],
        }

    def test_valid_contract(self):
        self.assertTrue(verify(self.data)["valid"])

    def test_api_must_remain_disabled(self):
        self.data["openai_api_required"] = True
        with self.assertRaises(ValueError):
            verify(self.data)

    def test_no_autonomous_execution(self):
        self.data["execution"] = "github_calls_ai"
        with self.assertRaises(ValueError):
            verify(self.data)

    def test_unsafe_path_rejected(self):
        self.data["read_only_queries"]["sources"] = "../../secret"
        with self.assertRaises(ValueError):
            verify(self.data)

    def test_unknown_fields_rejected(self):
        self.data["api_key"] = "fake"
        with self.assertRaises(ValueError):
            verify(self.data)


if __name__ == "__main__":
    unittest.main()
