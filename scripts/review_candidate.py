#!/usr/bin/env python3
"""Read-only candidate review; does not approve or modify records."""
import argparse
import json
import sys
from decision_store import candidate, all_decisions, verify_all

def review(cid):
    verify_all()
    item, digest = candidate(cid)
    decisions = [d for _, d in all_decisions() if d["candidate_id"] == cid]
    if len(decisions) > 1:
        raise ValueError("Conflicting decisions")
    decision = decisions[0] if decisions else None
    return {
        "candidate_id": cid, "kind": item["kind"], "content": item["content"],
        "evidence": item["evidence"], "candidate_sha256": digest,
        "effective_status": decision["decision"] if decision else "candidate",
        "decision_id": decision["decision_id"] if decision else None,
        "reason": decision["reason"] if decision else None,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_id")
    args = parser.parse_args()
    try:
        print(json.dumps(review(args.candidate_id), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
