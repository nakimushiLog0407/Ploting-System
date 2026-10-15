#!/usr/bin/env python3
"""Immutable proposals and explicit user reviews for a global story phase order."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "story_timeline" / "proposals"
REVIEWS = ROOT / "story_timeline" / "reviews"
PATTERN = re.compile(r"STL-\d{6,}")


def encoded(item):
    return (json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode()


def validate_phases(phases):
    if not isinstance(phases, list) or not phases or any(not isinstance(x, str) or not x.strip() or len(x) > 200 for x in phases) or len(set(phases)) != len(phases):
        raise ValueError("Distinct nonempty phase labels required")
    return phases


def records():
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("STL-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"timeline_id", "request_id", "phases", "reason", "created_at"}:
            raise ValueError("Invalid proposal schema")
        tid = x["timeline_id"]
        if not isinstance(tid, str) or not PATTERN.fullmatch(tid) or path.name != tid + ".json" or tid in proposals:
            raise ValueError("Invalid timeline ID")
        req = x["request_id"]
        if not isinstance(req, str) or not 1 <= len(req) <= 128 or any(ord(c) < 32 for c in req) or req in requests:
            raise ValueError("Invalid request ID")
        validate_phases(x["phases"])
        if not isinstance(x["reason"], str) or len(x["reason"]) > 20000 or not isinstance(x["created_at"], str) or not x["created_at"]:
            raise ValueError("Invalid metadata")
        proposals[tid] = (x, path)
        requests.add(req)
    reviews = {}
    for path in sorted(REVIEWS.glob("STL-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"timeline_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid review schema")
        tid = x["timeline_id"]
        if tid not in proposals or path.name != tid + ".json" or tid in reviews or x["decision"] not in ("approved", "rejected") or x["actor"] != "user":
            raise ValueError("Invalid review")
        if not isinstance(x["reason"], str) or len(x["reason"]) > 20000 or not isinstance(x["reviewed_at"], str) or not x["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        if x["proposal_sha256"] != hashlib.sha256(proposals[tid][1].read_bytes()).hexdigest():
            raise ValueError("Modified proposal")
        reviews[tid] = x
    result = [{**x, "status": reviews[tid]["decision"] if tid in reviews else "proposed"}
              for tid, (x, _) in proposals.items()]
    if sum(x["status"] == "approved" for x in result) > 1:
        raise ValueError("Multiple approved timelines")
    return result


def propose(request_id, phases, reason):
    existing = records()
    validate_phases(phases)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid reason")
    for x in existing:
        if x["request_id"] == request_id:
            if x["phases"] == phases and x["reason"] == reason:
                return {"status": "already_saved", "timeline_id": x["timeline_id"]}
            raise ValueError("Request ID reused")
        if x["status"] != "rejected":
            raise ValueError("Pending or approved timeline already exists")
    tid = f"STL-{max((int(x['timeline_id'][4:]) for x in existing), default=0)+1:06d}"
    x = {"timeline_id": tid, "request_id": request_id, "phases": phases,
         "reason": reason, "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (tid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encoded(x))
    return {"status": "saved", "timeline_id": tid}


def review(tid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review")
    matches = [x for x in records() if x["timeline_id"] == tid and x["status"] == "proposed"]
    if len(matches) != 1:
        raise ValueError("Pending timeline not found")
    path = PROPOSALS / (tid + ".json")
    x = {"timeline_id": tid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
         "decision": decision, "actor": "user", "reason": reason,
         "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (tid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encoded(x))
    return {"status": "saved", "timeline_id": tid, "decision": decision}


def approved_phases():
    return next((x["phases"] for x in records() if x["status"] == "approved"), [])


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--phase", action="append", required=True)
    a.add_argument("--reason", default="")
    a = sub.add_parser("review")
    a.add_argument("--timeline-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    a = sub.add_parser("list")
    a.add_argument("--status", choices=("all", "approved", "proposed", "rejected"), default="approved")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        if args.command == "propose":
            result = propose(args.request_id, args.phase, args.reason)
        elif args.command == "review":
            result = review(args.timeline_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            items = records()
            result = {"verified": len(items)} if args.command == "verify" else {
                "timelines": [x for x in items if args.status == "all" or x["status"] == args.status]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
