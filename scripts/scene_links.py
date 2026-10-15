#!/usr/bin/env python3
"""Explicitly approved scene links: chronology is not causality.

Append-only proposals and decisions. No inferred edges, no automatic canon edits.
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
PROPOSALS = ROOT / "scene_links" / "proposals"
REVIEWS = ROOT / "scene_links" / "reviews"
ID = re.compile(r"^SLNK-\d{6,}$")
TYPES = ("precedes", "causes", "enables", "foreshadows", "pays_off", "related_to")
DIRECTED = set(TYPES) - {"related_to"}


def records(cards):
    scenes = {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("SLNK-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"link_id", "request_id", "from_scene_id", "to_scene_id",
                                                 "relation_type", "reason", "created_at"}:
            raise ValueError("Invalid scene link schema")
        lid, req = x["link_id"], x["request_id"]
        if not isinstance(lid, str) or not ID.fullmatch(lid) or path.name != lid + ".json" or lid in proposals:
            raise ValueError("Invalid link ID")
        if not isinstance(req, str) or not 1 <= len(req) <= 128 or any(ord(c) < 32 for c in req) or req in requests:
            raise ValueError("Invalid request ID")
        if x["from_scene_id"] not in scenes or x["to_scene_id"] not in scenes or x["from_scene_id"] == x["to_scene_id"]:
            raise ValueError("Scene link requires distinct approved scenes")
        if x["relation_type"] not in TYPES:
            raise ValueError("Invalid relation type")
        if not isinstance(x["reason"], str) or not x["reason"].strip() or len(x["reason"]) > 20000:
            raise ValueError("Explicit relationship rationale required")
        if not isinstance(x["created_at"], str) or not x["created_at"]:
            raise ValueError("Invalid timestamp")
        proposals[lid] = (x, path)
        requests.add(req)
    reviews = {}
    for path in sorted(REVIEWS.glob("SLNK-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"link_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid link review schema")
        lid = x["link_id"]
        if lid not in proposals or path.name != lid + ".json" or lid in reviews:
            raise ValueError("Review without proposal")
        if x["proposal_sha256"] != hashlib.sha256(proposals[lid][1].read_bytes()).hexdigest():
            raise ValueError("Link proposal modified")
        if x["decision"] not in ("approved", "rejected") or x["actor"] != "user":
            raise ValueError("Invalid review decision")
        if not isinstance(x["reason"], str) or len(x["reason"]) > 20000 or not isinstance(x["reviewed_at"], str) or not x["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        reviews[lid] = x
    result = [{**x, "status": reviews[lid]["decision"] if lid in reviews else "proposed"}
              for lid, (x, _) in proposals.items()]
    keys = set()
    for x in result:
        if x["status"] != "approved":
            continue
        a, b = x["from_scene_id"], x["to_scene_id"]
        key = (x["relation_type"], a, b) if x["relation_type"] in DIRECTED else (x["relation_type"], *sorted((a, b)))
        if key in keys:
            raise ValueError("Duplicate approved scene relationship")
        keys.add(key)
    return result


def propose(cards, request_id, from_id, to_id, relation, reason):
    links = records(cards)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    scenes = {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}
    if from_id not in scenes or to_id not in scenes or from_id == to_id:
        raise ValueError("Two distinct approved scenes required")
    if relation not in TYPES or not isinstance(reason, str) or not reason.strip() or len(reason) > 20000:
        raise ValueError("Invalid relationship or rationale")
    for x in links:
        if x["request_id"] == request_id:
            if (x["from_scene_id"], x["to_scene_id"], x["relation_type"], x["reason"]) == (from_id, to_id, relation, reason):
                return {"status": "already_saved", "link_id": x["link_id"]}
            raise ValueError("Request ID reused")
    lid = f"SLNK-{max((int(x['link_id'][5:]) for x in links), default=0)+1:06d}"
    item = {"link_id": lid, "request_id": request_id, "from_scene_id": from_id,
            "to_scene_id": to_id, "relation_type": relation, "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (lid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "link_id": lid}


def review(cards, lid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review")
    links = records(cards)
    match = [x for x in links if x["link_id"] == lid and x["status"] == "proposed"]
    if len(match) != 1:
        raise ValueError("Pending scene link not found")
    x = match[0]
    if decision == "approved":
        a, b = x["from_scene_id"], x["to_scene_id"]
        key = (x["relation_type"], a, b) if x["relation_type"] in DIRECTED else (x["relation_type"], *sorted((a, b)))
        for y in links:
            if y["status"] != "approved":
                continue
            c, d = y["from_scene_id"], y["to_scene_id"]
            other = (y["relation_type"], c, d) if y["relation_type"] in DIRECTED else (y["relation_type"], *sorted((c, d)))
            if key == other:
                raise ValueError("Relationship already approved")
    path = PROPOSALS / (lid + ".json")
    item = {"link_id": lid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (lid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "link_id": lid, "decision": decision}


def overview(links):
    return {"approved_by_type": {t: [x for x in links if x["status"] == "approved" and x["relation_type"] == t] for t in TYPES},
            "pending": [x for x in links if x["status"] == "proposed"],
            "rejected": [x for x in links if x["status"] == "rejected"],
            "causality_inferred": False, "chronology_inferred": False, "canon_modified": False}


def main():
    p = argparse.ArgumentParser(description="Approved scene chronology, causality and thematic links")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--from-scene-id", required=True)
    a.add_argument("--to-scene-id", required=True)
    a.add_argument("--relation-type", choices=TYPES, required=True)
    a.add_argument("--reason", required=True)
    a = sub.add_parser("review")
    a.add_argument("--link-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    sub.add_parser("list")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        cards = card_records()
        if args.command == "propose":
            result = propose(cards, args.request_id, args.from_scene_id, args.to_scene_id, args.relation_type, args.reason)
        elif args.command == "review":
            result = review(cards, args.link_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            links = records(cards)
            result = overview(links) if args.command == "list" else {
                "total": len(links), "approved": sum(x["status"] == "approved" for x in links),
                "pending": sum(x["status"] == "proposed" for x in links)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
