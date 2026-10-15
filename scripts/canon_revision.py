#!/usr/bin/env python3
"""Immutable proposed revisions to approved canon; never rewrites source records.

Approved revisions are an explicit overlay. The original catalog remains unchanged.
Each revision is based on the latest approved content and requires user approval.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from canon_catalog import build_catalog

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "canon_revisions" / "proposals"
REVIEWS = ROOT / "canon_revisions" / "reviews"
PATTERN = re.compile(r"^REV-\d{6,}$")


def encode(item):
    return (json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load(entries):
    base = {x["candidate_id"]: x for x in entries}
    proposals = {}
    requests = set()
    for path in sorted(PROPOSALS.glob("REV-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        required = {"revision_id", "request_id", "candidate_id", "before", "after",
                    "reason", "affected_candidate_ids", "created_at"}
        if not isinstance(item, dict) or set(item) != required:
            raise ValueError("Invalid revision proposal schema")
        rid = item["revision_id"]
        if not isinstance(rid, str) or not PATTERN.fullmatch(rid) or path.name != rid + ".json" or rid in proposals:
            raise ValueError("Invalid revision ID")
        req = item["request_id"]
        if not isinstance(req, str) or not 1 <= len(req) <= 128 or req in requests or any(ord(c) < 32 for c in req):
            raise ValueError("Invalid request ID")
        if item["candidate_id"] not in base:
            raise ValueError("Revision references unapproved candidate")
        if not isinstance(item["before"], str) or not isinstance(item["after"], str) or not item["after"].strip() or len(item["after"]) > 20000:
            raise ValueError("Invalid revision content")
        if not isinstance(item["reason"], str) or not item["reason"].strip() or len(item["reason"]) > 20000:
            raise ValueError("Revision reason required")
        affected = item["affected_candidate_ids"]
        if not isinstance(affected, list) or len(affected) != len(set(affected)) or any(x not in base for x in affected):
            raise ValueError("Affected IDs must reference approved candidates")
        if not isinstance(item["created_at"], str) or not item["created_at"]:
            raise ValueError("Invalid timestamp")
        proposals[rid] = (item, path)
        requests.add(req)
    reviews = {}
    for path in sorted(REVIEWS.glob("REV-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"revision_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid revision review schema")
        rid = item["revision_id"]
        if rid not in proposals or path.name != rid + ".json" or rid in reviews:
            raise ValueError("Review without proposal")
        if item["proposal_sha256"] != hashlib.sha256(proposals[rid][1].read_bytes()).hexdigest():
            raise ValueError("Revision proposal changed")
        if item["decision"] not in ("approved", "rejected") or item["actor"] != "user":
            raise ValueError("Invalid revision review")
        if not isinstance(item["reason"], str) or len(item["reason"]) > 20000 or not isinstance(item["reviewed_at"], str) or not item["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        reviews[rid] = item
    current = {cid: x["content"] for cid, x in base.items()}
    history = []
    for rid in sorted(proposals, key=lambda x: int(x[4:])):
        item = proposals[rid][0]
        status = reviews[rid]["decision"] if rid in reviews else "proposed"
        if status == "approved":
            cid = item["candidate_id"]
            if current[cid] != item["before"]:
                raise ValueError("Approved revision has stale baseline")
            current[cid] = item["after"]
        history.append({**item, "status": status})
    return current, history


def propose(entries, request_id, candidate_id, after, reason, affected):
    current, history = load(entries)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if candidate_id not in current:
        raise ValueError("Approved candidate required")
    if not isinstance(after, str) or not after.strip() or len(after) > 20000 or after == current[candidate_id]:
        raise ValueError("New content must differ from current approved content")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 20000:
        raise ValueError("Reason required")
    if not isinstance(affected, list) or len(affected) != len(set(affected)) or any(x not in current for x in affected):
        raise ValueError("Invalid affected candidate IDs")
    for item in history:
        if item["request_id"] == request_id:
            if (item["candidate_id"], item["after"], item["reason"], item["affected_candidate_ids"]) == (candidate_id, after, reason, affected):
                return {"status": "already_saved", "revision_id": item["revision_id"]}
            raise ValueError("Request ID reused")
    if any(x["candidate_id"] == candidate_id and x["status"] == "proposed" for x in history):
        raise ValueError("Pending revision already exists for candidate")
    rid = f"REV-{max((int(x['revision_id'][4:]) for x in history), default=0)+1:06d}"
    item = {"revision_id": rid, "request_id": request_id, "candidate_id": candidate_id,
            "before": current[candidate_id], "after": after, "reason": reason,
            "affected_candidate_ids": affected, "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (rid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "revision_id": rid}


def review(entries, rid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review decision")
    current, history = load(entries)
    matches = [x for x in history if x["revision_id"] == rid and x["status"] == "proposed"]
    if len(matches) != 1:
        raise ValueError("Pending revision not found")
    item = matches[0]
    if decision == "approved" and current[item["candidate_id"]] != item["before"]:
        raise ValueError("Revision baseline changed; create a new proposal")
    path = PROPOSALS / (rid + ".json")
    result = {"revision_id": rid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "decision": decision, "actor": "user", "reason": reason,
              "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (rid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(result))
    return {"status": "saved", "revision_id": rid, "decision": decision}


def main():
    p = argparse.ArgumentParser(description="Explicitly reviewed immutable canon revision overlay")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--candidate-id", required=True)
    a.add_argument("--after", required=True)
    a.add_argument("--reason", required=True)
    a.add_argument("--affected-id", action="append", default=[])
    a = sub.add_parser("review")
    a.add_argument("--revision-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    sub.add_parser("list")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        entries = build_catalog()
        if args.command == "propose":
            result = propose(entries, args.request_id, args.candidate_id, args.after, args.reason, args.affected_id)
        elif args.command == "review":
            result = review(entries, args.revision_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            current, history = load(entries)
            result = {"revisions": history, "effective_content": current,
                      "source_records_modified": False} if args.command == "list" else {
                          "revisions": len(history), "approved": sum(x["status"] == "approved" for x in history),
                          "source_records_modified": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
