#!/usr/bin/env python3
"""Read-only candidate decisions with provenance; no implicit canon promotion."""
import argparse
import json
import sys
from candidate_store import all_records
from decision_store import all_decisions, verify_all

def build(candidates, decisions, status="all"):
    if status not in ("all", "pending", "approved", "rejected"):
        raise ValueError("Unknown status")
    decisions_by_candidate = {}
    for decision in decisions:
        cid = decision["candidate_id"]
        if cid in decisions_by_candidate:
            raise ValueError("Duplicate candidate decision")
        decisions_by_candidate[cid] = decision
    entries = []
    for candidate in candidates:
        cid = candidate["candidate_id"]
        decision = decisions_by_candidate.get(cid)
        state = decision["decision"] if decision else "pending"
        if status != "all" and state != status:
            continue
        evidence = candidate["evidence"]
        entries.append({
            "candidate_id": cid, "kind": candidate["kind"],
            "content": candidate["content"], "review_status": state,
            "is_canon": state == "approved",
            "source_id": evidence["source_id"],
            "source_quote": evidence["quote"],
            "source_start": evidence["start"],
            "source_end": evidence["end"],
            "decision_id": decision["decision_id"] if decision else None,
        })
    return {"status_filter": status, "total": len(entries),
            "entries": entries, "read_only": True,
            "unapproved_never_canon": True}

def main():
    parser = argparse.ArgumentParser(description="Inspect verified candidate decisions")
    parser.add_argument("--status", choices=("all", "pending", "approved", "rejected"), default="all")
    args = parser.parse_args()
    try:
        verify_all()
        result = build([record for _, record in all_records()],
                       [record for _, record in all_decisions()], args.status)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
