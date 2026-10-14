#!/usr/bin/env python3
"""Append-only human decisions for candidates; never edits source/candidate."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "decisions" / "records"
sys.path.insert(0, str(ROOT / "scripts"))
from candidate_store import validate as validate_candidate, verify_all as verify_candidates

CAND_RE = re.compile(r"^CAND-\d{6,}$")
DEC_RE = re.compile(r"^DEC-\d{6,}$")


def candidate(cid):
    if not CAND_RE.fullmatch(cid):
        raise ValueError("Invalid candidate ID")
    path = ROOT / "candidates" / "records" / (cid + ".json")
    item = json.loads(path.read_text(encoding="utf-8"))
    validate_candidate(item, path)
    return item, hashlib.sha256(path.read_bytes()).hexdigest()


def validate(item, path):
    if not isinstance(item, dict) or set(item) != {
        "schema_version", "decision_id", "request_id", "candidate_id",
        "candidate_sha256", "decision", "actor", "reason", "created_at",
    }:
        raise ValueError("Invalid decision schema")
    did = item["decision_id"]
    if not isinstance(did, str) or not DEC_RE.fullmatch(did) or path.name != did + ".json":
        raise ValueError("Invalid decision ID")
    if item["schema_version"] != 1 or item["decision"] not in ("approved", "rejected"):
        raise ValueError("Invalid decision")
    for field, limit in (("request_id", 128), ("actor", 128), ("reason", 20000)):
        value = item[field]
        if not isinstance(value, str) or len(value) > limit or (field != "reason" and not value):
            raise ValueError("Invalid " + field)
        if field != "reason" and any(ord(c) < 32 for c in value):
            raise ValueError("Control character in " + field)
    if item["actor"] != "user":
        raise ValueError("Only explicit user decisions allowed")
    if not isinstance(item["created_at"], str) or not item["created_at"]:
        raise ValueError("Invalid timestamp")
    _, digest = candidate(item["candidate_id"])
    if item["candidate_sha256"] != digest:
        raise ValueError("Candidate content changed")
    return item


def all_decisions():
    for path in sorted(DECISIONS.glob("DEC-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        validate(item, path)
        yield path, item


def verify_all():
    verify_candidates()
    seen_requests, seen_candidates, seen_ids = set(), set(), set()
    count = 0
    for _, item in all_decisions():
        if (item["request_id"] in seen_requests or item["candidate_id"] in seen_candidates
                or item["decision_id"] in seen_ids):
            raise ValueError("Duplicate decision")
        seen_requests.add(item["request_id"])
        seen_candidates.add(item["candidate_id"])
        seen_ids.add(item["decision_id"])
        count += 1
    return count


def record(request_id, cid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit confirmation is required")
    if decision not in ("approved", "rejected"):
        raise ValueError("Decision must be approved or rejected")
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid reason")
    lock = ROOT / ".decision-store.lock"
    with lock.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            verify_all()
            _, digest = candidate(cid)
            highest = 0
            for _, existing in all_decisions():
                highest = max(highest, int(existing["decision_id"][4:]))
                if existing["request_id"] == request_id:
                    if (existing["candidate_id"], existing["decision"], existing["reason"]) == (cid, decision, reason):
                        return {"status": "already_saved", "decision_id": existing["decision_id"]}
                    raise ValueError("Request ID reused with different decision")
                if existing["candidate_id"] == cid:
                    raise ValueError("Candidate already has a decision")
            did = f"DEC-{highest + 1:06d}"
            item = {
                "schema_version": 1, "decision_id": did, "request_id": request_id,
                "candidate_id": cid, "candidate_sha256": digest, "decision": decision,
                "actor": "user", "reason": reason,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            DECISIONS.mkdir(parents=True, exist_ok=True)
            path = DECISIONS / (did + ".json")
            validate(item, path)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write((json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            return {"status": "saved", "decision_id": did}
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("record")
    p.add_argument("--request-id", required=True)
    p.add_argument("--candidate-id", required=True)
    p.add_argument("--decision", choices=("approved", "rejected"), required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--confirm-user-decision", action="store_true", required=True)
    sub.add_parser("verify")
    args = parser.parse_args()
    try:
        if args.cmd == "record":
            result = record(args.request_id, args.candidate_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            result = {"status": "verified", "count": verify_all()}
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
