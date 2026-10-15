import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from idea_intake_audit import audit

class IdeaIntakeAuditTests(unittest.TestCase):
    def test_exact_quote_no_lexical_finding(self):
        text = "主人公は笑った。"
        result = audit(text, [{"kind": "event", "content": text, "start": 0, "end": len(text)}])
        self.assertEqual(result["audit"]["finding_count"], 0)
        self.assertTrue(result["proposals"][0]["verbatim_match"])
        self.assertFalse(result["audit"]["semantic_fidelity_verified"])
        self.assertFalse(result["audit"]["automatic_approval_allowed"])

    def test_added_detail_flagged_for_review(self):
        text = "主人公は笑った。"
        result = audit(text, [{"kind": "event", "content": "主人公は嬉しそうに笑った。",
                               "start": 0, "end": len(text)}])
        self.assertEqual(result["audit"]["finding_count"], 1)
        self.assertEqual(result["audit"]["findings"][0]["code"], "NOT_VERBATIM_FROM_EVIDENCE")
        self.assertTrue(result["proposals"][0]["human_semantic_review_required"])
        self.assertFalse(result["saved"])

    def test_paraphrase_requires_review_even_if_legitimate(self):
        text = "彼女はうなずいた。"
        result = audit(text, [{"kind": "event", "content": "彼女が同意した",
                               "start": 0, "end": len(text)}])
        self.assertEqual(result["audit"]["finding_count"], 1)

    def test_invalid_span_fails_closed(self):
        with self.assertRaises(ValueError):
            audit("abc", [{"kind": "event", "content": "abc", "start": 0, "end": 10}])

if __name__ == "__main__":
    unittest.main()
