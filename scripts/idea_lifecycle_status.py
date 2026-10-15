#!/usr/bin/env python3
"""Read-only view of a candidate's evidence and human decision status."""
import argparse
import json
import sys

from decision_store import candidate, all_decisions, verify_all


def status(candidate_id):
    verify_all()
    item, digest = candidate(candidate_id)
    matching = [decision for _, decision in all_decisions()
                if decision["candidate_id"] == candidate_id]
    if len(matching) > 1:
        raise ValueError("Conflicting candidate decisions")
    decision = matching[0] if matching else None
    evidence = item["evidence"]
    return {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "kind": item["kind"],
        "content": item["content"],
        "source_id": evidence["source_id"],
        "source_quote": evidence["quote"],
        "candidate_sha256": digest,
        "review_status": decision["decision"] if decision else "pending",
        "decision_id": decision["decision_id"] if decision else None,
        "is_canon": bool(decision and decision["decision"] == "approved"),
        "read_only": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Show one candidate and its decision")
    parser.add_argument("--candidate-id", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(status(args.candidate_id), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
