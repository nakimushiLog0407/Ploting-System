#!/usr/bin/env python3
"""Append-only, user-approved story chronology phases.

Only explicit phase ordering is canon; labels do not imply sequence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "chronology" / "proposals"
REVIEWS = ROOT / "chronology" / "reviews"
ID = re.compile(r"^CHR-\d{6,}$")


def encode(item):
    return (json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def records():
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("CHR-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"chronology_id", "request_id", "phase", "after_phase", "evidence", "created_at"}:
            raise ValueError("Invalid chronology proposal schema")
        cid = item["chronology_id"]
        if not isinstance(cid, str) or not ID.fullmatch(cid) or path.name != cid + ".json" or cid in proposals:
            raise ValueError("Invalid chronology ID")
        req = item["request_id"]
        if not isinstance(req, str) or not req or len(req) > 128 or any(ord(c) < 32 for c in req) or req in requests:
            raise ValueError("Invalid request ID")
        if not isinstance(item["phase"], str) or not item["phase"].strip() or len(item["phase"]) > 256:
            raise ValueError("Invalid phase")
        after = item["after_phase"]
        if after is not None and (not isinstance(after, str) or not after.strip() or len(after) > 256 or after == item["phase"]):
            raise ValueError("Invalid predecessor phase")
        if not isinstance(item["evidence"], str) or len(item["evidence"]) > 20000 or not isinstance(item["created_at"], str) or not item["created_at"]:
            raise ValueError("Invalid chronology metadata")
        proposals[cid] = (item, path)
        requests.add(req)
    reviews = {}
    for path in sorted(REVIEWS.glob("CHR-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"chronology_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid chronology review schema")
        cid = item["chronology_id"]
        if cid not in proposals or path.name != cid + ".json" or cid in reviews:
            raise ValueError("Review without proposal")
        if item["decision"] not in ("approved", "rejected") or item["actor"] != "user":
            raise ValueError("Invalid review decision")
        if not isinstance(item["reason"], str) or len(item["reason"]) > 20000 or not isinstance(item["reviewed_at"], str) or not item["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        if item["proposal_sha256"] != hashlib.sha256(proposals[cid][1].read_bytes()).hexdigest():
            raise ValueError("Chronology proposal modified")
        reviews[cid] = item
    result = [{**item, "status": reviews[cid]["decision"] if cid in reviews else "proposed"}
              for cid, (item, _) in proposals.items()]
    approved = [x for x in result if x["status"] == "approved"]
    phase_to_record = {}
    for item in approved:
        if item["phase"] in phase_to_record:
            raise ValueError("Conflicting approved phase definitions")
        phase_to_record[item["phase"]] = item
    for item in approved:
        if item["after_phase"] is not None and item["after_phase"] not in phase_to_record:
            raise ValueError("Approved phase references unapproved predecessor")
    # Explicit ordering only: each phase has at most one successor and no cycles.
    successors = {}
    for item in approved:
        predecessor = item["after_phase"]
        if predecessor is not None:
            if predecessor in successors:
                raise ValueError("Ambiguous phase order")
            successors[predecessor] = item["phase"]
    for phase in phase_to_record:
        seen, cursor = set(), phase
        while cursor is not None:
            if cursor in seen:
                raise ValueError("Chronology cycle")
            seen.add(cursor)
            cursor = successors.get(cursor)
    return result


def ordered_phases(items):
    approved = [x for x in items if x["status"] == "approved"]
    by_name = {x["phase"]: x for x in approved}
    successors = {x["after_phase"]: x["phase"] for x in approved if x["after_phase"] is not None}
    roots = sorted(x["phase"] for x in approved if x["after_phase"] is None)
    chains = []
    for root in roots:
        chain, current = [], root
        while current is not None:
            chain.append(current)
            current = successors.get(current)
        chains.append(chain)
    return chains


def propose(request_id, phase, after_phase, evidence):
    existing = records()
    if not isinstance(request_id, str) or not request_id or len(request_id) > 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if not isinstance(phase, str) or not phase.strip() or len(phase) > 256:
        raise ValueError("Invalid phase")
    if after_phase is not None and (not isinstance(after_phase, str) or not after_phase.strip() or len(after_phase) > 256 or after_phase == phase):
        raise ValueError("Invalid predecessor")
    if not isinstance(evidence, str) or len(evidence) > 20000:
        raise ValueError("Invalid evidence")
    for item in existing:
        if item["request_id"] == request_id:
            if (item["phase"], item["after_phase"], item["evidence"]) == (phase, after_phase, evidence):
                return {"status": "already_saved", "chronology_id": item["chronology_id"]}
            raise ValueError("Request ID reused")
        if item["phase"] == phase and item["status"] != "rejected":
            raise ValueError("Phase already pending or approved")
    if after_phase is not None and after_phase not in {x["phase"] for x in existing if x["status"] == "approved"}:
        raise ValueError("Predecessor must be approved")
    cid = f"CHR-{max((int(x['chronology_id'][4:]) for x in existing), default=0) + 1:06d}"
    item = {"chronology_id": cid, "request_id": request_id, "phase": phase,
            "after_phase": after_phase, "evidence": evidence,
            "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (cid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "chronology_id": cid}


def review(cid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review")
    existing = records()
    matches = [x for x in existing if x["chronology_id"] == cid and x["status"] == "proposed"]
    if len(matches) != 1:
        raise ValueError("Pending phase not found")
    item = matches[0]
    if decision == "approved":
        approved = [x for x in existing if x["status"] == "approved"]
        if any(x["phase"] == item["phase"] for x in approved):
            raise ValueError("Phase already approved")
        if item["after_phase"] is not None:
            if item["after_phase"] not in {x["phase"] for x in approved}:
                raise ValueError("Predecessor not approved")
            if any(x["after_phase"] == item["after_phase"] for x in approved):
                raise ValueError("Predecessor already has successor")
    path = PROPOSALS / (cid + ".json")
    record = {"chronology_id": cid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "decision": decision, "actor": "user", "reason": reason,
              "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (cid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(record))
    return {"status": "saved", "chronology_id": cid, "decision": decision}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--phase", required=True)
    a.add_argument("--after-phase")
    a.add_argument("--evidence", default="")
    a = sub.add_parser("review")
    a.add_argument("--chronology-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    a = sub.add_parser("list")
    a.add_argument("--status", choices=("approved", "rejected", "proposed", "all"), default="approved")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        items = records() if args.command in ("list", "verify") else None
        if args.command == "propose":
            result = propose(args.request_id, args.phase, args.after_phase, args.evidence)
        elif args.command == "review":
            result = review(args.chronology_id, args.decision, args.reason, args.confirm_user_decision)
        elif args.command == "verify":
            result = {"verified": len(items), "approved_chains": ordered_phases(items)}
        else:
            result = {"chronology": [x for x in items if args.status == "all" or x["status"] == args.status],
                      "approved_chains": ordered_phases(items)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
