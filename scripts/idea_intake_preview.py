#!/usr/bin/env python3
"""Preview unordered idea classifications without saving or approving anything.

Input JSON is a user-reviewed draft. The tool checks exact source spans and
supported categories; it never writes to the repository.
"""
import argparse
import json
from pathlib import Path
import sys

KINDS = ("character", "event", "dialogue", "setting", "foreshadowing", "other")


def preview(source_text, proposals):
    if not isinstance(source_text, str) or not source_text.strip():
        raise ValueError("Source text required")
    if not isinstance(proposals, list) or not proposals:
        raise ValueError("At least one proposal required")
    if len(proposals) > 100:
        raise ValueError("Too many proposals")
    result = []
    for index, item in enumerate(proposals, start=1):
        if not isinstance(item, dict) or set(item) != {"kind", "content", "start", "end"}:
            raise ValueError("Invalid proposal fields")
        kind, content = item["kind"], item["content"]
        start, end = item["start"], item["end"]
        if kind not in KINDS or not isinstance(content, str) or not content.strip() or len(content) > 20000:
            raise ValueError("Invalid classification or content")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source_text):
            raise ValueError("Invalid source span")
        quote = source_text[start:end]
        if not quote.strip():
            raise ValueError("Empty source evidence")
        result.append({"proposal_number": index, "kind": kind,
                       "proposed_content": content,
                       "source_quote": quote, "start": start, "end": end,
                       "status": "requires_user_review", "is_canon": False})
    return {"schema_version": 1, "proposal_count": len(result),
            "proposals": result, "read_only": True,
            "saved": False, "approval_performed": False}


def main():
    parser = argparse.ArgumentParser(description="Preview classified ideas before any write")
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--proposals-file", required=True)
    args = parser.parse_args()
    try:
        source = Path(args.source_file).read_text(encoding="utf-8")
        proposals = json.loads(Path(args.proposals_file).read_text(encoding="utf-8"))
        print(json.dumps(preview(source, proposals), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
