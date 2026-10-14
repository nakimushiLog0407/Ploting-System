#!/usr/bin/env python3
"""Append-only relationship proposals and user review records."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

from canon_catalog import build_catalog
from relationship_catalog import ROOT, TYPES, validate, verify_relationships

PROPOSALS = ROOT / "relationships" / "records"
REVIEWS = ROOT / "relationships" / "reviews"


def canonical_bytes(item):
    return (json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def proposal(request_id, source, target, relation, evidence):
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if not isinstance(evidence, str) or len(evidence) > 20000:
        raise ValueError("Invalid evidence")
    verify_reviews()
    entries = {e["candidate_id"]: e for e in build_catalog()}
    if source not in entries or target not in entries:
        raise ValueError("Both endpoints must be approved")
    if source == target or relation not in TYPES:
        raise ValueError("Invalid relationship")
    if relation == "spoken_by" and (entries[source]["kind"] != "dialogue" or entries[target]["kind"] != "character"):
        raise ValueError("spoken_by requires dialogue -> character")
    if relation == "occurs_in" and entries[target]["kind"] != "event":
        raise ValueError("occurs_in requires an event target")
    from relationship_catalog import all_relationships
    existing = list(all_relationships())
    for item in existing:
        if item["request_id"] == request_id:
            if (item["from_candidate_id"], item["to_candidate_id"], item["relation"], item["evidence"]) == (source, target, relation, evidence):
                return {"status": "already_saved", "relationship_id": item["relationship_id"]}
            raise ValueError("Request ID reused")
        if (item["from_candidate_id"], item["to_candidate_id"], item["relation"]) == (source, target, relation):
            raise ValueError("Relationship already proposed")
    number = max((int(item["relationship_id"][4:]) for item in existing), default=0) + 1
    rid = f"REL-{number:06d}"
    item = {"schema_version": 1, "relationship_id": rid, "request_id": request_id,
            "from_candidate_id": source, "to_candidate_id": target, "relation": relation,
            "status": "proposed", "evidence": evidence,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": None, "reviewed_at": None}
    validate(item, PROPOSALS / (rid + ".json"))
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    path = PROPOSALS / (rid + ".json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(canonical_bytes(item))
    return {"status": "saved", "relationship_id": rid}


def reviews():
    for path in sorted(REVIEWS.glob("REL-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"relationship_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid review schema")
        rid = item["relationship_id"]
        if path.name != rid + ".json" or item["decision"] not in ("approved", "rejected") or item["actor"] != "user":
            raise ValueError("Invalid review decision")
        if not isinstance(item["reason"], str) or len(item["reason"]) > 20000 or not isinstance(item["reviewed_at"], str) or not item["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        original = PROPOSALS / (rid + ".json")
        if not original.is_file() or item["proposal_sha256"] != hashlib.sha256(original.read_bytes()).hexdigest():
            raise ValueError("Proposal changed or missing")
        if json.loads(original.read_text(encoding="utf-8"))["status"] != "proposed":
            raise ValueError("Cannot review a non-proposal")
        yield item


def verify_reviews():
    verify_relationships()
    items = list(reviews())
    return len(items)


def review(rid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review")
    verify_reviews()
    path = PROPOSALS / (rid + ".json")
    item = validate(json.loads(path.read_text(encoding="utf-8")), path)
    if item["status"] != "proposed":
        raise ValueError("Already reviewed in proposal")
    dest = REVIEWS / (rid + ".json")
    if dest.exists():
        raise ValueError("Relationship already reviewed")
    result = {"relationship_id": rid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "decision": decision, "actor": "user", "reason": reason,
              "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(canonical_bytes(result))
    return {"status": "saved", "relationship_id": rid, "decision": decision}


def effective(status="approved"):
    if status not in ("approved", "rejected", "proposed", "all"):
        raise ValueError("Invalid status")
    verify_reviews()
    decisions = {r["relationship_id"]: r for r in reviews()}
    from relationship_catalog import all_relationships
    output = []
    for item in all_relationships():
        record = dict(item)
        review_item = decisions.get(item["relationship_id"])
        if review_item:
            record["status"] = review_item["decision"]
            record["reviewed_by"] = "user"
            record["reviewed_at"] = review_item["reviewed_at"]
        if status == "all" or record["status"] == status:
            output.append(record)
    return output


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--request-id", required=True)
    p.add_argument("--from-id", required=True)
    p.add_argument("--to-id", required=True)
    p.add_argument("--relation", choices=TYPES, required=True)
    p.add_argument("--evidence", default="")
    p = sub.add_parser("review")
    p.add_argument("--relationship-id", required=True)
    p.add_argument("--decision", choices=("approved", "rejected"), required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--confirm-user-decision", action="store_true", required=True)
    p = sub.add_parser("list")
    p.add_argument("--status", default="approved", choices=("approved", "rejected", "proposed", "all"))
    sub.add_parser("verify")
    args = parser.parse_args()
    try:
        if args.cmd == "propose":
            result = proposal(args.request_id, args.from_id, args.to_id, args.relation, args.evidence)
        elif args.cmd == "review":
            result = review(args.relationship_id, args.decision, args.reason, args.confirm_user_decision)
        elif args.cmd == "list":
            result = {"relationships": effective(args.status)}
        else:
            result = {"verified_reviews": verify_reviews()}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
