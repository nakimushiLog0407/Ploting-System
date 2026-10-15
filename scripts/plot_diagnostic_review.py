#!/usr/bin/env python3
"""User-reviewed immutable dispositions for plot diagnostic findings.

Review is tied to exact finding content; a changed finding needs fresh review.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from plot_diagnostics import diagnose
from plot_cards import records as card_records, encode
from plot_moves import records as move_records, effective as effective_cards
from scene_links import records as link_records
from foreshadowing import records as thread_records
from foreshadowing_changes import records as change_records, effective as effective_threads

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = ROOT / "plot_diagnostic_reviews"
PATTERN = re.compile(r"^PDR-\d{6,}$")
DECISIONS = ("intentional", "needs_revision", "defer")


def digest(finding):
    return hashlib.sha256(json.dumps(finding, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()


def key(finding):
    return (finding["code"], finding["subject_id"], digest(finding))


def records(findings):
    current = {key(x): x for x in findings}
    reviews, requests = [], set()
    for path in sorted(REVIEWS.glob("PDR-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"review_id", "request_id", "code", "subject_id",
                                                 "finding_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid diagnostic review schema")
        rid, req = x["review_id"], x["request_id"]
        if not isinstance(rid, str) or not PATTERN.fullmatch(rid) or path.name != rid + ".json" or any(y["review_id"] == rid for y in reviews):
            raise ValueError("Invalid review ID")
        if not isinstance(req, str) or not 1 <= len(req) <= 128 or any(ord(c) < 32 for c in req) or req in requests:
            raise ValueError("Invalid request ID")
        if x["decision"] not in DECISIONS or x["actor"] != "user":
            raise ValueError("Invalid user decision")
        if not isinstance(x["reason"], str) or not x["reason"].strip() or len(x["reason"]) > 20000:
            raise ValueError("Reason required")
        if not isinstance(x["reviewed_at"], str) or not x["reviewed_at"]:
            raise ValueError("Invalid timestamp")
        if not isinstance(x["code"], str) or not isinstance(x["subject_id"], str) or not isinstance(x["finding_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", x["finding_sha256"]):
            raise ValueError("Invalid finding reference")
        reviews.append(x)
        requests.add(req)
    # Historical reviews are retained even after findings disappear/change.
    latest = {}
    for x in reviews:
        k = (x["code"], x["subject_id"], x["finding_sha256"])
        latest[k] = x
    return reviews, latest, current


def propose(findings, request_id, code, subject_id, finding_sha256, decision, reason):
    reviews, latest, current = records(findings)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if decision not in DECISIONS or not isinstance(reason, str) or not reason.strip() or len(reason) > 20000:
        raise ValueError("Invalid decision or reason")
    k = (code, subject_id, finding_sha256)
    if k not in current:
        raise ValueError("Finding is no longer current or fingerprint changed")
    for x in reviews:
        if x["request_id"] == request_id:
            if (x["code"], x["subject_id"], x["finding_sha256"], x["decision"], x["reason"]) == (code, subject_id, finding_sha256, decision, reason):
                return {"status": "already_saved", "review_id": x["review_id"]}
            raise ValueError("Request ID reused")
    if k in latest:
        raise ValueError("Finding already reviewed; use a new review workflow for changed judgment")
    rid = f"PDR-{max((int(x['review_id'][4:]) for x in reviews), default=0)+1:06d}"
    item = {"review_id": rid, "request_id": request_id, "code": code,
            "subject_id": subject_id, "finding_sha256": finding_sha256,
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (rid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "review_id": rid}


def overview(findings):
    reviews, latest, _ = records(findings)
    return {"findings": [{**f, "finding_sha256": digest(f),
                          "review": latest.get(key(f), {}).get("decision", "unreviewed"),
                          "review_id": latest.get(key(f), {}).get("review_id")}
                         for f in findings],
            "review_history": reviews, "canon_modified": False, "auto_fix": False}


def main():
    p = argparse.ArgumentParser(description="User disposition for structural plot findings")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("review")
    a.add_argument("--request-id", required=True)
    a.add_argument("--code", required=True)
    a.add_argument("--subject-id", required=True)
    a.add_argument("--finding-sha256", required=True)
    a.add_argument("--decision", choices=DECISIONS, required=True)
    a.add_argument("--reason", required=True)
    a.add_argument("--confirm-user-decision", action="store_true")
    sub.add_parser("list")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        cards = card_records()
        moves = move_records(cards)
        links = link_records(cards)
        threads = thread_records(cards)
        scenes = {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}
        changes = change_records(threads, scenes)
        findings = diagnose(effective_cards(cards, moves), links, effective_threads(threads, changes, scenes))["findings"]
        if args.command == "review":
            if not args.confirm_user_decision:
                raise ValueError("Explicit user decision required")
            result = propose(findings, args.request_id, args.code, args.subject_id, args.finding_sha256,
                             args.decision, args.reason)
        elif args.command == "list":
            result = overview(findings)
        else:
            reviews, _, _ = records(findings)
            result = {"findings": len(findings), "reviews": len(reviews), "canon_modified": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
