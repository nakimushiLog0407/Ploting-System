#!/usr/bin/env python3
"""Immutable approved reassignment of foreshadowing setup/payoff scenes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from foreshadowing import records as thread_records
from plot_cards import records as card_records, encode

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "foreshadowing_changes" / "proposals"
REVIEWS = ROOT / "foreshadowing_changes" / "reviews"
PATTERN = re.compile(r"^FCHG-\d{6,}$")
FIELDS = ("setup_scene_id", "payoff_scene_id")


def validate_assignment(thread, assignment, scenes):
    if not isinstance(assignment, dict) or set(assignment) != set(FIELDS):
        raise ValueError("Invalid assignment schema")
    for field in FIELDS:
        if assignment[field] is not None and assignment[field] not in scenes:
            raise ValueError("Assignment references unapproved scene")
    if assignment["setup_scene_id"] is not None and assignment["setup_scene_id"] == assignment["payoff_scene_id"]:
        raise ValueError("Setup and payoff must differ")


def assignment(thread):
    return {field: thread[field] for field in FIELDS}


def effective(threads, changes, scenes):
    by_id = {x["thread_id"]: dict(x) for x in threads}
    for change in sorted(changes, key=lambda x: int(x["change_id"][5:])):
        if change["status"] != "approved":
            continue
        tid = change["thread_id"]
        if tid not in by_id or by_id[tid]["status"] != "approved":
            raise ValueError("Change references unapproved thread")
        if assignment(by_id[tid]) != change["before"]:
            raise ValueError("Approved change has stale baseline")
        validate_assignment(by_id[tid], change["after"], scenes)
        by_id[tid].update(change["after"])
    return list(by_id.values())


def records(threads, scenes):
    by_id = {x["thread_id"]: x for x in threads}
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("FCHG-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"change_id", "request_id", "thread_id", "before", "after", "reason", "created_at"}:
            raise ValueError("Invalid change schema")
        cid, req = x["change_id"], x["request_id"]
        if not isinstance(cid, str) or not PATTERN.fullmatch(cid) or path.name != cid + ".json" or cid in proposals:
            raise ValueError("Invalid change ID")
        if not isinstance(req, str) or not 1 <= len(req) <= 128 or any(ord(c) < 32 for c in req) or req in requests:
            raise ValueError("Invalid request ID")
        if x["thread_id"] not in by_id or by_id[x["thread_id"]]["status"] != "approved":
            raise ValueError("Change requires approved thread")
        validate_assignment(by_id[x["thread_id"]], x["before"], scenes)
        validate_assignment(by_id[x["thread_id"]], x["after"], scenes)
        if x["before"] == x["after"]:
            raise ValueError("Change cannot be a no-op")
        if not isinstance(x["reason"], str) or not x["reason"].strip() or len(x["reason"]) > 20000:
            raise ValueError("Reason required")
        if not isinstance(x["created_at"], str) or not x["created_at"]:
            raise ValueError("Invalid timestamp")
        proposals[cid] = (x, path)
        requests.add(req)
    reviews = {}
    for path in sorted(REVIEWS.glob("FCHG-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"change_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid change review schema")
        cid = x["change_id"]
        if cid not in proposals or path.name != cid + ".json" or cid in reviews:
            raise ValueError("Review without change proposal")
        if x["proposal_sha256"] != hashlib.sha256(proposals[cid][1].read_bytes()).hexdigest():
            raise ValueError("Change proposal modified")
        if x["decision"] not in ("approved", "rejected") or x["actor"] != "user":
            raise ValueError("Invalid review")
        if not isinstance(x["reason"], str) or len(x["reason"]) > 20000 or not isinstance(x["reviewed_at"], str) or not x["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        reviews[cid] = x
    changes = [{**x, "status": reviews[cid]["decision"] if cid in reviews else "proposed"}
               for cid, (x, _) in proposals.items()]
    effective(threads, changes, scenes)
    return changes


def propose(threads, scenes, request_id, thread_id, setup, payoff, reason):
    changes = records(threads, scenes)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    current = {x["thread_id"]: x for x in effective(threads, changes, scenes)}
    if thread_id not in current or current[thread_id]["status"] != "approved":
        raise ValueError("Approved thread required")
    after = {"setup_scene_id": setup, "payoff_scene_id": payoff}
    validate_assignment(current[thread_id], after, scenes)
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 20000:
        raise ValueError("Reason required")
    for x in changes:
        if x["request_id"] == request_id:
            if (x["thread_id"], x["after"], x["reason"]) == (thread_id, after, reason):
                return {"status": "already_saved", "change_id": x["change_id"]}
            raise ValueError("Request ID reused")
    if assignment(current[thread_id]) == after:
        raise ValueError("No assignment change")
    if any(x["thread_id"] == thread_id and x["status"] == "proposed" for x in changes):
        raise ValueError("Pending change exists")
    cid = f"FCHG-{max((int(x['change_id'][5:]) for x in changes), default=0)+1:06d}"
    item = {"change_id": cid, "request_id": request_id, "thread_id": thread_id,
            "before": assignment(current[thread_id]), "after": after, "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (cid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "change_id": cid}


def review(threads, scenes, cid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review")
    changes = records(threads, scenes)
    matches = [x for x in changes if x["change_id"] == cid and x["status"] == "proposed"]
    if len(matches) != 1:
        raise ValueError("Pending change not found")
    if decision == "approved":
        effective(threads, changes + [{**matches[0], "status": "approved"}], scenes)
    path = PROPOSALS / (cid + ".json")
    item = {"change_id": cid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (cid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "change_id": cid, "decision": decision}


def main():
    p = argparse.ArgumentParser(description="Explicitly reviewed foreshadowing assignment changes")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--thread-id", required=True)
    a.add_argument("--setup-scene-id")
    a.add_argument("--payoff-scene-id")
    a.add_argument("--reason", required=True)
    a = sub.add_parser("review")
    a.add_argument("--change-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    sub.add_parser("list")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        cards = card_records()
        scenes = {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}
        threads = thread_records(cards)
        if args.command == "propose":
            result = propose(threads, scenes, args.request_id, args.thread_id, args.setup_scene_id, args.payoff_scene_id, args.reason)
        elif args.command == "review":
            result = review(threads, scenes, args.change_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            changes = records(threads, scenes)
            if args.command == "verify":
                result = {"changes": len(changes), "approved": sum(x["status"] == "approved" for x in changes),
                          "source_threads_modified": False}
            else:
                from foreshadowing import overview
                result = {"changes": changes, "foreshadowing": overview(effective(threads, changes, scenes)),
                          "source_threads_modified": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
