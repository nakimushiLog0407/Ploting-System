#!/usr/bin/env python3
"""Prepare a candidate-save handoff; never save or approve anything.

Source must already be archived. A user must explicitly approve saving
candidate records; that does not approve them as canonical settings.
"""
import argparse
import json
import sys
from idea_review import review
from candidate_store import source_span


def plan(source_id, source_text, proposals, request_prefix):
    if not isinstance(request_prefix, str) or not 1 <= len(request_prefix) <= 100 or any(ord(ch) < 33 or ord(ch) > 126 for ch in request_prefix):
        raise ValueError("A printable ASCII request prefix is required")
    reviewed = review(source_text, proposals)
    items = []
    for item in reviewed["proposals"]:
        evidence = source_span(source_id, item["start"], item["end"])
        if evidence["quote"] != item["source_quote"]:
            raise ValueError("Archived source does not match the reviewed text")
        items.append({
            "proposal_number": item["proposal_number"],
            "candidate_save_request": {
                "request_id": f"{request_prefix}-{item['proposal_number']:03d}",
                "kind": item["kind"],
                "content": item["proposed_content"],
                "source_id": source_id,
                "start": item["start"],
                "end": item["end"],
            },
            "source_quote": evidence["quote"],
            "review_required": True,
            "will_be_canon": False,
        })
    return {
        "schema_version": 1,
        "source_id": source_id,
        "items": items,
        "audit": reviewed["audit"],
        "next_action": "Ask user to approve each candidate SAVE request; canonical approval is separate",
        "saved": False,
        "approval_performed": False,
        "read_only": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Preview candidate-save requests without writes")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--proposals-file", required=True)
    parser.add_argument("--request-prefix", required=True)
    args = parser.parse_args()
    try:
        from pathlib import Path
        source = Path(args.source_file).read_text(encoding="utf-8")
        proposals = json.loads(Path(args.proposals_file).read_text(encoding="utf-8"))
        print(json.dumps(plan(args.source_id, source, proposals, args.request_prefix),
                         ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
