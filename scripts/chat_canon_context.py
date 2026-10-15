#!/usr/bin/env python3
"""Separate approved canon from unapproved candidate ideas, read-only."""
import json
import sys
from candidate_store import all_records
from decision_store import all_decisions, verify_all
from canon_catalog import build_catalog

def build(candidates, decisions, canon):
    decisions_by_id = {d["candidate_id"]: d for d in decisions}
    if len(decisions_by_id) != len(decisions):
        raise ValueError("Duplicate decision")
    approved_ids = {c["candidate_id"] for c in canon}
    approved, pending, rejected = [], [], []
    for candidate in candidates:
        cid = candidate["candidate_id"]
        decision = decisions_by_id.get(cid)
        status = decision["decision"] if decision else "pending"
        entry = {"candidate_id": cid, "kind": candidate["kind"],
                 "content": candidate["content"],
                 "source_id": candidate["evidence"]["source_id"],
                 "source_quote": candidate["evidence"]["quote"],
                 "is_canon": status == "approved"}
        if status == "approved":
            if cid not in approved_ids:
                raise ValueError("Approved candidate missing from canon")
            approved.append(entry)
        elif status == "rejected":
            rejected.append(entry)
        else:
            pending.append(entry)
    if approved_ids != {x["candidate_id"] for x in approved}:
        raise ValueError("Canon and approved decisions disagree")
    return {"schema_version": 1, "approved_canon": approved,
            "pending_not_canon": pending, "rejected_not_canon": rejected,
            "read_only": True, "approval_performed": False}

def main():
    try:
        verify_all()
        result = build([x for _, x in all_records()],
                       [x for _, x in all_decisions()], build_catalog())
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
