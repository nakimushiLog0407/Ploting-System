#!/usr/bin/env python3
"""Append-only foreshadowing threads with explicit user approval.

A thread can be approved without a payoff. Missing payoff is 'unassigned',
never automatically a narrative defect. No inferred scenes or plot canon.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from plot_cards import records as card_records, encode

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "foreshadowing" / "proposals"
REVIEWS = ROOT / "foreshadowing" / "reviews"
ID = re.compile(r"^FSDW-\d{6,}$")


def validate(item, scenes):
    if not isinstance(item, dict) or set(item) != {"thread_id", "request_id", "title", "description",
                                                    "setup_scene_id", "payoff_scene_id", "notes", "created_at"}:
        raise ValueError("Invalid foreshadowing schema")
    fid, req = item["thread_id"], item["request_id"]
    if not isinstance(fid, str) or not ID.fullmatch(fid):
        raise ValueError("Invalid thread ID")
    if not isinstance(req, str) or not 1 <= len(req) <= 128 or any(ord(c) < 32 for c in req):
        raise ValueError("Invalid request ID")
    if not isinstance(item["title"], str) or not item["title"].strip() or len(item["title"]) > 200:
        raise ValueError("Invalid thread title")
    for key in ("description", "notes"):
        if not isinstance(item[key], str) or len(item[key]) > 20000:
            raise ValueError("Invalid " + key)
    for key in ("setup_scene_id", "payoff_scene_id"):
        if item[key] is not None and item[key] not in scenes:
            raise ValueError("Foreshadowing scene must be an approved scene")
    if item["setup_scene_id"] is not None and item["setup_scene_id"] == item["payoff_scene_id"]:
        raise ValueError("Setup and payoff must be different scenes")
    if not isinstance(item["created_at"], str) or not item["created_at"]:
        raise ValueError("Invalid timestamp")


def records(cards):
    scenes = {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("FSDW-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        validate(x, scenes)
        fid = x["thread_id"]
        if path.name != fid + ".json" or fid in proposals or x["request_id"] in requests:
            raise ValueError("Duplicate or invalid foreshadowing record")
        proposals[fid] = (x, path)
        requests.add(x["request_id"])
    reviews = {}
    for path in sorted(REVIEWS.glob("FSDW-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"thread_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid foreshadowing review schema")
        fid = x["thread_id"]
        if fid not in proposals or path.name != fid + ".json" or fid in reviews:
            raise ValueError("Review without thread proposal")
        if x["proposal_sha256"] != hashlib.sha256(proposals[fid][1].read_bytes()).hexdigest():
            raise ValueError("Foreshadowing proposal modified")
        if x["decision"] not in ("approved", "rejected") or x["actor"] != "user":
            raise ValueError("Explicit user review required")
        if not isinstance(x["reason"], str) or len(x["reason"]) > 20000 or not isinstance(x["reviewed_at"], str) or not x["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        reviews[fid] = x
    return [{**x, "status": reviews[fid]["decision"] if fid in reviews else "proposed"}
            for fid, (x, _) in proposals.items()]


def propose(cards, request_id, title, description, setup, payoff, notes):
    existing = records(cards)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    for x in existing:
        if x["request_id"] == request_id:
            if (x["title"], x["description"], x["setup_scene_id"], x["payoff_scene_id"], x["notes"]) == (title, description, setup, payoff, notes):
                return {"status": "already_saved", "thread_id": x["thread_id"]}
            raise ValueError("Request ID reused")
    fid = f"FSDW-{max((int(x['thread_id'][5:]) for x in existing), default=0)+1:06d}"
    item = {"thread_id": fid, "request_id": request_id, "title": title,
            "description": description, "setup_scene_id": setup,
            "payoff_scene_id": payoff, "notes": notes,
            "created_at": datetime.now(timezone.utc).isoformat()}
    scenes = {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}
    validate(item, scenes)
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (fid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "thread_id": fid}


def review(cards, fid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review")
    existing = records(cards)
    if not any(x["thread_id"] == fid and x["status"] == "proposed" for x in existing):
        raise ValueError("Pending foreshadowing thread not found")
    path = PROPOSALS / (fid + ".json")
    item = {"thread_id": fid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (fid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "thread_id": fid, "decision": decision}


def overview(threads):
    approved = [x for x in threads if x["status"] == "approved"]
    return {"approved": [{**x, "setup_assignment": "assigned" if x["setup_scene_id"] else "unassigned",
                          "payoff_assignment": "assigned" if x["payoff_scene_id"] else "unassigned"}
                         for x in approved],
            "without_setup": [x["thread_id"] for x in approved if x["setup_scene_id"] is None],
            "without_payoff": [x["thread_id"] for x in approved if x["payoff_scene_id"] is None],
            "pending": [x for x in threads if x["status"] == "proposed"],
            "rejected": [x for x in threads if x["status"] == "rejected"],
            "actual_payoff_verified": False, "missing_payoff_is_error": False,
            "canon_modified": False}


def main():
    p = argparse.ArgumentParser(description="Approved foreshadowing setup and payoff tracking")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--description", default="")
    a.add_argument("--setup-scene-id")
    a.add_argument("--payoff-scene-id")
    a.add_argument("--notes", default="")
    a = sub.add_parser("review")
    a.add_argument("--thread-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    sub.add_parser("list")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        cards = card_records()
        if args.command == "propose":
            result = propose(cards, args.request_id, args.title, args.description,
                             args.setup_scene_id, args.payoff_scene_id, args.notes)
        elif args.command == "review":
            result = review(cards, args.thread_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            threads = records(cards)
            result = overview(threads) if args.command == "list" else {
                "total": len(threads), "approved": sum(x["status"] == "approved" for x in threads),
                "pending": sum(x["status"] == "proposed" for x in threads)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
