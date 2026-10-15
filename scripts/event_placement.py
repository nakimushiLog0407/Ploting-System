#!/usr/bin/env python3
"""Approved-only placement of approved story events in approved global phases.

Proposals and reviews are append-only. No event order within a phase is inferred.
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
from story_timeline import approved_phases

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "event_placements" / "proposals"
REVIEWS = ROOT / "event_placements" / "reviews"
ID = re.compile(r"EVP-\d{6,}")


def encode(item):
    return (json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def valid_text(value, required=False):
    return isinstance(value, str) and len(value) <= 20000 and (not required or bool(value.strip()))


def event_ids():
    return {x["candidate_id"] for x in build_catalog() if x["kind"] == "event"}


def records(events=None, phases=None):
    if events is None:
        events = event_ids()
    if phases is None:
        phases = approved_phases()
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("EVP-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"placement_id", "request_id", "event_id", "phase", "evidence", "created_at"}:
            raise ValueError("Invalid event placement proposal")
        pid, req = item["placement_id"], item["request_id"]
        if not isinstance(pid, str) or not ID.fullmatch(pid) or path.name != pid + ".json" or pid in proposals:
            raise ValueError("Invalid placement ID")
        if not isinstance(req, str) or not 1 <= len(req) <= 128 or any(ord(c) < 32 for c in req) or req in requests:
            raise ValueError("Invalid request ID")
        if item["event_id"] not in events or item["phase"] not in phases:
            raise ValueError("Placement requires approved event and approved phase")
        if not valid_text(item["evidence"]) or not valid_text(item["created_at"], True):
            raise ValueError("Invalid placement metadata")
        proposals[pid] = (item, path)
        requests.add(req)
    reviews = {}
    for path in sorted(REVIEWS.glob("EVP-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"placement_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid placement review")
        pid = item["placement_id"]
        if pid not in proposals or path.name != pid + ".json" or pid in reviews:
            raise ValueError("Review without proposal")
        if item["decision"] not in ("approved", "rejected") or item["actor"] != "user":
            raise ValueError("Invalid review decision")
        if not valid_text(item["reason"]) or not valid_text(item["reviewed_at"], True):
            raise ValueError("Invalid review metadata")
        if item["proposal_sha256"] != hashlib.sha256(proposals[pid][1].read_bytes()).hexdigest():
            raise ValueError("Placement proposal changed")
        reviews[pid] = item
    result = [{**item, "status": reviews[pid]["decision"] if pid in reviews else "proposed"}
              for pid, (item, _) in proposals.items()]
    occupied = set()
    for item in result:
        if item["status"] == "approved":
            if item["event_id"] in occupied:
                raise ValueError("Conflicting approved placements for event")
            occupied.add(item["event_id"])
    return result


def propose(request_id, event_id, phase, evidence):
    existing = records()
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if event_id not in event_ids() or phase not in approved_phases():
        raise ValueError("Approved event and phase required")
    if not valid_text(evidence):
        raise ValueError("Invalid evidence")
    for item in existing:
        if item["request_id"] == request_id:
            if (item["event_id"], item["phase"], item["evidence"]) == (event_id, phase, evidence):
                return {"status": "already_saved", "placement_id": item["placement_id"]}
            raise ValueError("Request ID reused")
        if item["event_id"] == event_id and item["status"] != "rejected":
            raise ValueError("Event placement already pending or approved")
    pid = f"EVP-{max((int(x['placement_id'][4:]) for x in existing), default=0) + 1:06d}"
    item = {"placement_id": pid, "request_id": request_id, "event_id": event_id,
            "phase": phase, "evidence": evidence, "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (pid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "placement_id": pid}


def review(pid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not valid_text(reason):
        raise ValueError("Invalid review")
    matches = [x for x in records() if x["placement_id"] == pid and x["status"] == "proposed"]
    if len(matches) != 1:
        raise ValueError("Pending placement not found")
    if decision == "approved":
        if any(x["event_id"] == matches[0]["event_id"] and x["status"] == "approved" for x in records()):
            raise ValueError("Event already placed")
    path = PROPOSALS / (pid + ".json")
    item = {"placement_id": pid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (pid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "placement_id": pid, "decision": decision}


def timeline(entries, placements, phases):
    events = {x["candidate_id"]: x for x in entries if x["kind"] == "event"}
    result = [{"phase": p, "events": []} for p in phases]
    by_phase = {x["phase"]: x["events"] for x in result}
    placed = set()
    for item in placements:
        if item["status"] != "approved":
            continue
        eid, phase = item["event_id"], item["phase"]
        if eid not in events or phase not in by_phase or eid in placed:
            raise ValueError("Invalid approved placement")
        event = events[eid]
        by_phase[phase].append({"event_id": eid, "content": event["content"],
                                "source_id": event["source_id"], "decision_id": event["decision_id"],
                                "placement_id": item["placement_id"], "evidence": item["evidence"]})
        placed.add(eid)
    for group in result:
        group["events"].sort(key=lambda x: x["event_id"])
    return {"phases": result, "unplaced_events": [
        {"event_id": eid, "content": x["content"]} for eid, x in sorted(events.items()) if eid not in placed],
        "within_phase_order": "unknown"}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--event-id", required=True)
    a.add_argument("--phase", required=True)
    a.add_argument("--evidence", default="")
    a = sub.add_parser("review")
    a.add_argument("--placement-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    a = sub.add_parser("list")
    a.add_argument("--status", choices=("all", "approved", "proposed", "rejected"), default="approved")
    sub.add_parser("verify")
    a = sub.add_parser("timeline")
    a.add_argument("--summary", action="store_true")
    args = p.parse_args()
    try:
        if args.command == "propose":
            result = propose(args.request_id, args.event_id, args.phase, args.evidence)
        elif args.command == "review":
            result = review(args.placement_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            items = records()
            if args.command == "verify":
                result = {"verified": len(items)}
            elif args.command == "list":
                result = {"placements": [x for x in items if args.status == "all" or x["status"] == args.status]}
            else:
                result = timeline(build_catalog(), items, approved_phases())
                if args.summary:
                    result = {"phases": len(result["phases"]),
                              "placed_events": sum(len(x["events"]) for x in result["phases"]),
                              "unplaced_events": len(result["unplaced_events"])}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
