#!/usr/bin/env python3
"""Audit an idea preview for exact quotation and ungrounded additions.

This is a conservative lexical guard, not a semantic truth checker.
It never approves, saves, or modifies ideas.
"""
import argparse
import json
from pathlib import Path
import sys
from idea_intake_preview import preview


def audit(source_text, proposals):
    result = preview(source_text, proposals)
    findings = []
    for item in result["proposals"]:
        content = item["proposed_content"]
        quote = item["source_quote"]
        exact = content == quote
        contained = content in quote
        if not contained:
            findings.append({
                "proposal_number": item["proposal_number"],
                "code": "NOT_VERBATIM_FROM_EVIDENCE",
                "severity": "review_required",
                "message": "Proposed content is not an exact substring of its source quote; human semantic review required.",
            })
        item["verbatim_match"] = exact
        item["substring_of_source_quote"] = contained
        item["human_semantic_review_required"] = not exact
    result["audit"] = {
        "findings": findings,
        "finding_count": len(findings),
        "semantic_fidelity_verified": False,
        "automatic_approval_allowed": False,
        "human_review_required": True,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Audit proposed idea extraction without any writes")
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--proposals-file", required=True)
    args = parser.parse_args()
    try:
        source = Path(args.source_file).read_text(encoding="utf-8")
        proposals = json.loads(Path(args.proposals_file).read_text(encoding="utf-8"))
        print(json.dumps(audit(source, proposals), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
