#!/usr/bin/env python3
"""Separate approved canon from unapproved candidate ideas, read-only."""
import json
import sys
from candidate_store import all_records
from decision_store import all_decisions, verify_all
from canon_catalog import build_catalog
from canon_revision import load as load_revisions

def build(candidates, decisions, canon, current=None, history=None):
    decisions_by_id = {d["candidate_id"]: d for d in decisions}
    if len(decisions_by_id) != len(decisions):
        raise ValueError("Duplicate decision")
    approved_ids = {c["candidate_id"] for c in canon}
    if len(approved_ids) != len(canon):
        raise ValueError("Duplicate canon entry")
    if current is None:
        current = {c["candidate_id"]: c["content"] for c in canon}
    if set(current) != approved_ids:
        raise ValueError("Effective canon does not match approved catalog")
    history = [] if history is None else history
    revisions_by_candidate = {}
    pending_revisions = []
    for revision in history:
        if revision["candidate_id"] not in approved_ids:
            raise ValueError("Revision targets non-canon candidate")
        if revision["status"] == "approved":
            revisions_by_candidate.setdefault(revision["candidate_id"], []).append(revision["revision_id"])
        elif revision["status"] == "proposed":
            pending_revisions.append({"revision_id": revision["revision_id"],
                                      "candidate_id": revision["candidate_id"],
                                      "proposed_content_not_canon": revision["after"]})
        elif revision["status"] != "rejected":
            raise ValueError("Unknown revision status")
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
            approved.append({**entry, "original_content": entry["content"],
                             "content": current[cid],
                             "approved_revision_ids": revisions_by_candidate.get(cid, [])})
        elif status == "rejected":
            rejected.append(entry)
        else:
            pending.append(entry)
    if approved_ids != {x["candidate_id"] for x in approved}:
        raise ValueError("Canon and approved decisions disagree")
    return {"schema_version": 1, "approved_canon": approved,
            "pending_not_canon": pending, "rejected_not_canon": rejected,
            "pending_revisions_not_canon": pending_revisions,
            "read_only": True, "approval_performed": False}

def main():
    try:
        verify_all()
        canon = build_catalog()
        current, history = load_revisions(canon)
        result = build([x for _, x in all_records()],
                       [x for _, x in all_decisions()], canon, current, history)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
