#!/usr/bin/env python3
"""Explicitly reviewed classifications for approved setting candidates.

Classifications are append-only: proposal and user review are separate files.
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
PROPOSALS = ROOT / "classifications" / "proposals"
REVIEWS = ROOT / "classifications" / "reviews"
CATEGORIES = ("world_rule", "organization", "place", "term")
ID_PATTERN = re.compile(r"^CLS-\d{6,}$")


def encoded(item):
    return (json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def all_classifications():
    catalog = {x["candidate_id"]: x for x in build_catalog()}
    proposals = {}
    requests = set()
    for path in sorted(PROPOSALS.glob("CLS-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"classification_id", "request_id", "candidate_id", "category", "evidence", "created_at"}:
            raise ValueError("Invalid classification proposal schema")
        cid = item["classification_id"]
        if not isinstance(cid, str) or not ID_PATTERN.fullmatch(cid) or path.name != cid + ".json" or cid in proposals:
            raise ValueError("Invalid classification ID")
        if not isinstance(item["request_id"], str) or not item["request_id"] or len(item["request_id"]) > 128 or any(ord(c) < 32 for c in item["request_id"]) or item["request_id"] in requests:
            raise ValueError("Invalid or duplicate request ID")
        if item["category"] not in CATEGORIES or item["candidate_id"] not in catalog or catalog[item["candidate_id"]]["kind"] != "setting":
            raise ValueError("Classification requires approved setting")
        if not isinstance(item["evidence"], str) or len(item["evidence"]) > 20000 or not isinstance(item["created_at"], str) or not item["created_at"]:
            raise ValueError("Invalid proposal metadata")
        requests.add(item["request_id"])
        proposals[cid] = (item, path)
    decisions = {}
    for path in sorted(REVIEWS.glob("CLS-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"classification_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid classification review schema")
        cid = item["classification_id"]
        if cid not in proposals or path.name != cid + ".json" or cid in decisions:
            raise ValueError("Review without proposal")
        if item["decision"] not in ("approved", "rejected") or item["actor"] != "user":
            raise ValueError("Invalid classification review")
        if not isinstance(item["reason"], str) or len(item["reason"]) > 20000 or not isinstance(item["reviewed_at"], str) or not item["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        if item["proposal_sha256"] != hashlib.sha256(proposals[cid][1].read_bytes()).hexdigest():
            raise ValueError("Classification proposal changed")
        decisions[cid] = item
    approved_by_setting = {}
    result = []
    for cid, (item, _) in proposals.items():
        decision = decisions.get(cid)
        status = decision["decision"] if decision else "proposed"
        if status == "approved":
            key = item["candidate_id"]
            if key in approved_by_setting:
                raise ValueError("Conflicting approved classifications")
            approved_by_setting[key] = cid
        result.append({**item, "status": status, "reviewed_at": decision["reviewed_at"] if decision else None})
    return result


def propose(request_id, candidate_id, category, evidence):
    existing = all_classifications()
    if not isinstance(request_id, str) or not request_id or len(request_id) > 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if category not in CATEGORIES or not isinstance(evidence, str) or len(evidence) > 20000:
        raise ValueError("Invalid category or evidence")
    catalog = {x["candidate_id"]: x for x in build_catalog()}
    if candidate_id not in catalog or catalog[candidate_id]["kind"] != "setting":
        raise ValueError("Approved setting required")
    for item in existing:
        if item["request_id"] == request_id:
            if (item["candidate_id"], item["category"], item["evidence"]) == (candidate_id, category, evidence):
                return {"status": "already_saved", "classification_id": item["classification_id"]}
            raise ValueError("Request ID reused")
        if item["candidate_id"] == candidate_id and item["status"] != "rejected":
            raise ValueError("Setting already has a pending or approved classification")
    highest = max((int(x["classification_id"][4:]) for x in existing), default=0)
    cid = f"CLS-{highest + 1:06d}"
    item = {"classification_id": cid, "request_id": request_id, "candidate_id": candidate_id,
            "category": category, "evidence": evidence, "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (cid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encoded(item))
    return {"status": "saved", "classification_id": cid}


def review(cid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user approval or rejection required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review")
    existing = all_classifications()
    matches = [x for x in existing if x["classification_id"] == cid]
    if len(matches) != 1 or matches[0]["status"] != "proposed":
        raise ValueError("Unreviewed classification not found")
    path = PROPOSALS / (cid + ".json")
    item = {"classification_id": cid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (cid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encoded(item))
    return {"status": "saved", "classification_id": cid, "decision": decision}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--request-id", required=True)
    p.add_argument("--candidate-id", required=True)
    p.add_argument("--category", choices=CATEGORIES, required=True)
    p.add_argument("--evidence", default="")
    p = sub.add_parser("review")
    p.add_argument("--classification-id", required=True)
    p.add_argument("--decision", choices=("approved", "rejected"), required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--confirm-user-decision", action="store_true")
    p = sub.add_parser("list")
    p.add_argument("--status", choices=("all", "approved", "rejected", "proposed"), default="approved")
    p.add_argument("--category", choices=CATEGORIES)
    sub.add_parser("verify")
    args = parser.parse_args()
    try:
        if args.command == "propose":
            result = propose(args.request_id, args.candidate_id, args.category, args.evidence)
        elif args.command == "review":
            result = review(args.classification_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            entries = all_classifications()
            if args.command == "verify":
                result = {"verified": len(entries)}
            else:
                entries = [x for x in entries if (args.status == "all" or x["status"] == args.status)
                           and (args.category is None or x["category"] == args.category)]
                result = {"classifications": entries}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
