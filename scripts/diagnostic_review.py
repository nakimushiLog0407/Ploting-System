#!/usr/bin/env python3
"""Append-only user decisions on diagnostic findings, never edits story canon.

A finding identity hashes its full diagnostic payload. Changed findings get new IDs.
A prior decision never automatically applies to changed evidence.
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
from event_placement import records as placement_records
from event_order import records as order_records
from character_relation_types import records as relation_records
from canon_diagnostics import diagnose

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = ROOT / "diagnostic_reviews"
ID = re.compile(r"^[0-9a-f]{64}$")
DECISIONS = ("acknowledged", "needs_fix", "not_an_issue")


def fingerprint(finding):
    payload = json.dumps(finding, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def index_findings(findings):
    result = {}
    for finding in findings:
        fid = fingerprint(finding)
        if fid in result:
            raise ValueError("Duplicate diagnostic finding")
        result[fid] = finding
    return result


def read_reviews():
    result = {}
    for path in sorted(REVIEWS.glob("*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"finding_id", "finding", "decision", "reason", "actor", "reviewed_at"}:
            raise ValueError("Invalid diagnostic review schema")
        fid = item["finding_id"]
        if not isinstance(fid, str) or not ID.fullmatch(fid) or path.name != fid + ".json" or fid in result:
            raise ValueError("Invalid diagnostic review ID")
        if fingerprint(item["finding"]) != fid:
            raise ValueError("Diagnostic review finding was modified")
        if item["decision"] not in DECISIONS or item["actor"] != "user":
            raise ValueError("Invalid diagnostic review decision")
        if not isinstance(item["reason"], str) or len(item["reason"]) > 20000:
            raise ValueError("Invalid review reason")
        if not isinstance(item["reviewed_at"], str) or not item["reviewed_at"]:
            raise ValueError("Invalid review timestamp")
        result[fid] = item
    return result


def overview(findings, reviews):
    current = index_findings(findings)
    return {
        "active": [{"finding_id": fid, **finding,
                    "review": ({"decision": reviews[fid]["decision"],
                                "reason": reviews[fid]["reason"]}
                               if fid in reviews else None)}
                   for fid, finding in sorted(current.items())],
        "historical_not_current": [
            {"finding_id": fid, "decision": item["decision"], "reason": item["reason"]}
            for fid, item in sorted(reviews.items()) if fid not in current
        ],
        "canon_modified": False,
        "decisions_do_not_change_canon": True,
    }


def review(findings, finding_id, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if not isinstance(finding_id, str) or not ID.fullmatch(finding_id):
        raise ValueError("Invalid finding ID")
    if decision not in DECISIONS or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review decision or reason")
    current = index_findings(findings)
    if finding_id not in current:
        raise ValueError("Finding is no longer current; run diagnostics again")
    reviews = read_reviews()
    if finding_id in reviews:
        if reviews[finding_id]["decision"] == decision and reviews[finding_id]["reason"] == reason:
            return {"status": "already_saved", "finding_id": finding_id}
        raise ValueError("Review is immutable; cannot overwrite an existing decision")
    item = {"finding_id": finding_id, "finding": current[finding_id],
            "decision": decision, "reason": reason, "actor": "user",
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    path = REVIEWS / (finding_id + ".json")
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return {"status": "saved", "finding_id": finding_id, "decision": decision}


def main():
    parser = argparse.ArgumentParser(description="Explicit user review of diagnostic findings")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("verify")
    a = sub.add_parser("review")
    a.add_argument("--finding-id", required=True)
    a.add_argument("--decision", choices=DECISIONS, required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    args = parser.parse_args()
    try:
        findings = diagnose(build_catalog(), approved_phases(), placement_records(),
                            order_records(), relation_records())["findings"]
        if args.command == "review":
            result = review(findings, args.finding_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            reviews = read_reviews()
            result = overview(findings, reviews)
            if args.command == "verify":
                result = {"active": len(result["active"]),
                          "historical_not_current": len(result["historical_not_current"]),
                          "saved_reviews": len(reviews)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
