#!/usr/bin/env python3
"""Explicitly confirmed single-candidate save from a reviewed idea.

Saving a candidate never approves canon. No bulk/implicit writes.
"""
import argparse
import json
import sys

from idea_save_handoff import plan
from candidate_store import save as save_candidate


def save_reviewed(source_id, source_text, proposals, request_prefix,
                  proposal_number, confirmed=False, writer=None):
    if confirmed is not True:
        raise ValueError("Explicit user confirmation to save a candidate is required")
    if type(proposal_number) is not int or proposal_number < 1:
        raise ValueError("Invalid proposal number")
    handoff = plan(source_id, source_text, proposals, request_prefix)
    matching = [entry for entry in handoff["items"]
                if entry["proposal_number"] == proposal_number]
    if len(matching) != 1:
        raise ValueError("Proposal number not found")
    request = matching[0]["candidate_save_request"]
    persist = save_candidate if writer is None else writer
    saved = persist(request["request_id"], request["kind"], request["content"],
                    request["source_id"], request["start"], request["end"])
    return {"candidate_save_result": saved, "proposal_number": proposal_number,
            "candidate_only": True, "canon_approved": False,
            "user_confirmed_candidate_save": True}


def main():
    parser = argparse.ArgumentParser(description="Save one explicitly confirmed idea candidate")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--proposals-file", required=True)
    parser.add_argument("--request-prefix", required=True)
    parser.add_argument("--proposal-number", type=int, required=True)
    parser.add_argument("--confirm-user-save", action="store_true", required=True)
    args = parser.parse_args()
    try:
        from pathlib import Path
        source = Path(args.source_file).read_text(encoding="utf-8")
        proposals = json.loads(Path(args.proposals_file).read_text(encoding="utf-8"))
        print(json.dumps(save_reviewed(args.source_id, source, proposals,
                                      args.request_prefix, args.proposal_number,
                                      args.confirm_user_save), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
