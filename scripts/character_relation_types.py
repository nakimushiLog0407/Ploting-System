#!/usr/bin/env python3
"""Explicitly approved, directional character relationships with optional story phase."""
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
PROPOSALS = ROOT / "character_relations" / "proposals"
REVIEWS = ROOT / "character_relations" / "reviews"
TYPES = ("friend", "family", "hostile", "mentor", "student", "ally", "rival", "other")
ID = re.compile(r"^CRL-\d{6,}$")


def encode(item):
    return (json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def records():
    characters = {x["candidate_id"] for x in build_catalog() if x["kind"] == "character"}
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("CRL-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"relation_id", "request_id", "from_character_id", "to_character_id", "relation_type", "phase", "description", "evidence", "created_at"}:
            raise ValueError("Invalid character relation schema")
        rid = item["relation_id"]
        if not isinstance(rid, str) or not ID.fullmatch(rid) or path.name != rid + ".json" or rid in proposals:
            raise ValueError("Invalid relation ID")
        if not isinstance(item["request_id"], str) or not item["request_id"] or len(item["request_id"]) > 128 or any(ord(c) < 32 for c in item["request_id"]) or item["request_id"] in requests:
            raise ValueError("Invalid request ID")
        a, b = item["from_character_id"], item["to_character_id"]
        if a not in characters or b not in characters or a == b or item["relation_type"] not in TYPES:
            raise ValueError("Relation requires two distinct approved characters")
        for key in ("phase", "description", "evidence"):
            v = item[key]
            if not isinstance(v, str) or len(v) > 20000 or (key == "description" and not v.strip()):
                raise ValueError("Invalid " + key)
        if not isinstance(item["created_at"], str) or not item["created_at"]:
            raise ValueError("Invalid timestamp")
        proposals[rid] = (item, path)
        requests.add(item["request_id"])
    reviews = {}
    for path in sorted(REVIEWS.glob("CRL-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"relation_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid relation review schema")
        rid = item["relation_id"]
        if rid not in proposals or path.name != rid + ".json" or rid in reviews:
            raise ValueError("Review without proposal")
        if item["decision"] not in ("approved", "rejected") or item["actor"] != "user":
            raise ValueError("Invalid review")
        if not isinstance(item["reason"], str) or len(item["reason"]) > 20000 or not isinstance(item["reviewed_at"], str) or not item["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        if item["proposal_sha256"] != hashlib.sha256(proposals[rid][1].read_bytes()).hexdigest():
            raise ValueError("Relation proposal changed")
        reviews[rid] = item
    return [{**item, "status": reviews[rid]["decision"] if rid in reviews else "proposed"}
            for rid, (item, _) in proposals.items()]


def propose(request_id, source, target, relation_type, phase, description, evidence):
    existing = records()
    if not isinstance(request_id, str) or not request_id or len(request_id) > 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if relation_type not in TYPES:
        raise ValueError("Invalid relation type")
    for key, value in (("phase", phase), ("description", description), ("evidence", evidence)):
        if not isinstance(value, str) or len(value) > 20000 or (key == "description" and not value.strip()):
            raise ValueError("Invalid " + key)
    characters = {x["candidate_id"] for x in build_catalog() if x["kind"] == "character"}
    if source not in characters or target not in characters or source == target:
        raise ValueError("Two distinct approved characters required")
    for item in existing:
        if item["request_id"] == request_id:
            if (item["from_character_id"], item["to_character_id"], item["relation_type"], item["phase"], item["description"], item["evidence"]) == (source, target, relation_type, phase, description, evidence):
                return {"status": "already_saved", "relation_id": item["relation_id"]}
            raise ValueError("Request ID reused")
    rid = f"CRL-{max((int(x['relation_id'][4:]) for x in existing), default=0) + 1:06d}"
    item = {"relation_id": rid, "request_id": request_id, "from_character_id": source,
            "to_character_id": target, "relation_type": relation_type, "phase": phase,
            "description": description, "evidence": evidence,
            "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (rid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "relation_id": rid}


def review(rid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review")
    matches = [x for x in records() if x["relation_id"] == rid]
    if len(matches) != 1 or matches[0]["status"] != "proposed":
        raise ValueError("Pending relation not found")
    path = PROPOSALS / (rid + ".json")
    item = {"relation_id": rid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (rid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "relation_id": rid, "decision": decision}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    for name in ("request-id", "from-id", "to-id", "relation-type", "description"):
        a.add_argument("--" + name, required=True)
    a.add_argument("--phase", default="")
    a.add_argument("--evidence", default="")
    a = sub.add_parser("review")
    a.add_argument("--relation-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    a = sub.add_parser("list")
    a.add_argument("--status", choices=("approved", "rejected", "proposed", "all"), default="approved")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        if args.command == "propose":
            result = propose(args.request_id, args.from_id, args.to_id, args.relation_type, args.phase, args.description, args.evidence)
        elif args.command == "review":
            result = review(args.relation_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            items = records()
            result = {"verified": len(items)} if args.command == "verify" else {"relations": [x for x in items if args.status == "all" or x["status"] == args.status]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
