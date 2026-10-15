#!/usr/bin/env python3
"""Immutable user-approved revisions of prose drafts, preserving every version."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from prose_drafts import records as draft_records
from plot_cards import records as plot_records, encode

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "prose_revisions" / "proposals"
REVIEWS = ROOT / "prose_revisions" / "reviews"
PATTERN = re.compile(r"^PREV-\d{6,}$")


def approved_base(drafts):
    approved = [x for x in drafts if x["status"] == "approved"]
    return {x["draft_id"]: x for x in approved}


def effective(drafts, revisions):
    base = approved_base(drafts)
    current = {did: x["text"] for did, x in base.items()}
    history = {did: [] for did in base}
    for rev in sorted(revisions, key=lambda x: int(x["revision_id"][5:])):
        if rev["status"] != "approved":
            continue
        did = rev["draft_id"]
        if did not in current or current[did] != rev["before"]:
            raise ValueError("Approved prose revision has stale baseline")
        current[did] = rev["after"]
        history[did].append(rev["revision_id"])
    return [{"draft_id": did, "scene_id": base[did]["scene_id"],
             "text": current[did], "original_text": base[did]["text"],
             "approved_revision_ids": history[did]} for did in base]


def records(drafts):
    base = approved_base(drafts)
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("PREV-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"revision_id", "request_id", "draft_id", "before", "after", "reason", "created_at"}:
            raise ValueError("Invalid prose revision schema")
        rid, req = x["revision_id"], x["request_id"]
        if not isinstance(rid, str) or not PATTERN.fullmatch(rid) or path.name != rid + ".json" or rid in proposals:
            raise ValueError("Invalid revision ID")
        if not isinstance(req, str) or not 1 <= len(req) <= 128 or any(ord(c) < 32 for c in req) or req in requests:
            raise ValueError("Invalid request ID")
        if x["draft_id"] not in base:
            raise ValueError("Revision requires approved draft")
        if not isinstance(x["before"], str) or not isinstance(x["after"], str) or not x["after"].strip() or len(x["after"]) > 200000 or x["before"] == x["after"]:
            raise ValueError("Invalid revision content")
        if not isinstance(x["reason"], str) or not x["reason"].strip() or len(x["reason"]) > 20000:
            raise ValueError("Revision reason required")
        if not isinstance(x["created_at"], str) or not x["created_at"]:
            raise ValueError("Invalid timestamp")
        proposals[rid] = (x, path)
        requests.add(req)
    reviews = {}
    for path in sorted(REVIEWS.glob("PREV-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"revision_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid prose revision review schema")
        rid = x["revision_id"]
        if rid not in proposals or path.name != rid + ".json" or rid in reviews:
            raise ValueError("Review without revision")
        if x["proposal_sha256"] != hashlib.sha256(proposals[rid][1].read_bytes()).hexdigest():
            raise ValueError("Prose revision proposal modified")
        if x["decision"] not in ("approved", "rejected") or x["actor"] != "user":
            raise ValueError("Explicit user decision required")
        if not isinstance(x["reason"], str) or len(x["reason"]) > 20000 or not isinstance(x["reviewed_at"], str) or not x["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        reviews[rid] = x
    result = [{**x, "status": reviews[rid]["decision"] if rid in reviews else "proposed"}
              for rid, (x, _) in proposals.items()]
    effective(drafts, result)
    return result


def propose(drafts, request_id, draft_id, after, reason):
    revisions = records(drafts)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if not isinstance(after, str) or not after.strip() or len(after) > 200000:
        raise ValueError("Invalid revised text")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 20000:
        raise ValueError("Revision reason required")
    current = {x["draft_id"]: x["text"] for x in effective(drafts, revisions)}
    if draft_id not in current:
        raise ValueError("Approved draft required")
    for x in revisions:
        if x["request_id"] == request_id:
            if (x["draft_id"], x["after"], x["reason"]) == (draft_id, after, reason):
                return {"status": "already_saved", "revision_id": x["revision_id"]}
            raise ValueError("Request ID reused")
    if after == current[draft_id]:
        raise ValueError("Revised prose must differ")
    if any(x["draft_id"] == draft_id and x["status"] == "proposed" for x in revisions):
        raise ValueError("Pending revision already exists for draft")
    rid = f"PREV-{max((int(x['revision_id'][5:]) for x in revisions), default=0)+1:06d}"
    item = {"revision_id": rid, "request_id": request_id, "draft_id": draft_id,
            "before": current[draft_id], "after": after, "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (rid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "revision_id": rid}


def review(drafts, rid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review decision")
    revisions = records(drafts)
    matches = [x for x in revisions if x["revision_id"] == rid and x["status"] == "proposed"]
    if len(matches) != 1:
        raise ValueError("Pending revision not found")
    if decision == "approved":
        effective(drafts, revisions + [{**matches[0], "status": "approved"}])
    path = PROPOSALS / (rid + ".json")
    item = {"revision_id": rid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (rid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "revision_id": rid, "decision": decision}


def main():
    p = argparse.ArgumentParser(description="User-reviewed immutable prose revisions")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--draft-id", required=True)
    a.add_argument("--after", required=True)
    a.add_argument("--reason", required=True)
    a = sub.add_parser("review")
    a.add_argument("--revision-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    sub.add_parser("list")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        drafts = draft_records(plot_records())
        if args.command == "propose":
            result = propose(drafts, args.request_id, args.draft_id, args.after, args.reason)
        elif args.command == "review":
            result = review(drafts, args.revision_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            revisions = records(drafts)
            result = {"revisions": revisions, "effective_prose": effective(drafts, revisions),
                      "original_drafts_modified": False} if args.command == "list" else {
                          "revisions": len(revisions), "approved": sum(x["status"] == "approved" for x in revisions),
                          "original_drafts_modified": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
