#!/usr/bin/env python3
"""Read-only unified preview and audit for unordered novel ideas."""
import argparse
import json
from pathlib import Path
import sys
from idea_intake_audit import audit


def review(source_text, proposals):
    result = audit(source_text, proposals)
    return {
        "schema_version": 1,
        "workflow": "unordered_idea_review",
        "source_text": source_text,
        "proposals": result["proposals"],
        "audit": result["audit"],
        "next_action": "Present proposals and source evidence for explicit user review",
        "classification_is_draft": True,
        "automatic_approval_allowed": False,
        "saved": False,
        "read_only": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Preview and audit unordered ideas")
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--proposals-file", required=True)
    args = parser.parse_args()
    try:
        source = Path(args.source_file).read_text(encoding="utf-8")
        proposals = json.loads(Path(args.proposals_file).read_text(encoding="utf-8"))
        print(json.dumps(review(source, proposals), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
