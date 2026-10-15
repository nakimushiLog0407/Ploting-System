#!/usr/bin/env python3
"""Immutable, user-confirmed dispositions for structural prose findings."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from plot_cards import records as card_records, encode
from plot_moves import records as move_records
from prose_drafts import records as draft_records
from prose_revisions import records as revision_records
from prose_diagnostics import diagnose

REVIEWS = Path(__file__).resolve().parents[1] / "prose_diagnostic_reviews"
DECISIONS = ("intentional", "needs_revision", "defer")


def digest(f):
    return hashlib.sha256(json.dumps(f, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def key(f):
    return f["code"], f["subject_id"], digest(f)


def records(findings):
    history, requests = [], set()
    for path in sorted(REVIEWS.glob("PRDR-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        fields = {"review_id", "request_id", "code", "subject_id", "finding_sha256", "decision", "actor", "reason", "reviewed_at"}
        if not isinstance(x, dict) or set(x) != fields:
            raise ValueError("Invalid review schema")
        rid, req = x["review_id"], x["request_id"]
        if not isinstance(rid, str) or not re.fullmatch(r"PRDR-\d{6,}", rid) or path.name != rid + ".json" or any(y["review_id"] == rid for y in history):
            raise ValueError("Invalid review ID")
        if not isinstance(req, str) or not 1 <= len(req) <= 128 or req in requests or any(ord(c) < 32 for c in req):
            raise ValueError("Invalid request ID")
        if x["decision"] not in DECISIONS or x["actor"] != "user":
            raise ValueError("Explicit user decision required")
        if not isinstance(x["reason"], str) or not x["reason"].strip() or len(x["reason"]) > 20000:
            raise ValueError("Reason required")
        if not isinstance(x["reviewed_at"], str) or not x["reviewed_at"]:
            raise ValueError("Invalid timestamp")
        if not isinstance(x["code"], str) or not x["code"] or not isinstance(x["subject_id"], str) or not x["subject_id"] or not isinstance(x["finding_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", x["finding_sha256"]):
            raise ValueError("Invalid finding reference")
        history.append(x)
        requests.add(req)
    latest = {(x["code"], x["subject_id"], x["finding_sha256"]): x for x in history}
    return history, latest, {key(f): f for f in findings}


def review(findings, request_id, code, subject_id, finding_sha256, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user confirmation required")
    history, latest, current = records(findings)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if decision not in DECISIONS or not isinstance(reason, str) or not reason.strip() or len(reason) > 20000:
        raise ValueError("Invalid decision or reason")
    target = (code, subject_id, finding_sha256)
    for x in history:
        if x["request_id"] == request_id:
            if (x["code"], x["subject_id"], x["finding_sha256"], x["decision"], x["reason"]) == (*target, decision, reason):
                return {"status": "already_saved", "review_id": x["review_id"]}
            raise ValueError("Request ID reused")
    if target not in current:
        raise ValueError("Finding changed or no longer current")
    if target in latest:
        raise ValueError("Finding already reviewed")
    rid = f"PRDR-{max((int(x['review_id'][5:]) for x in history), default=0)+1:06d}"
    item = {"review_id": rid, "request_id": request_id, "code": code, "subject_id": subject_id,
            "finding_sha256": finding_sha256, "decision": decision, "actor": "user",
            "reason": reason, "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (rid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "review_id": rid, "decision": decision}


def overview(findings):
    history, latest, _ = records(findings)
    return {"findings": [{**f, "finding_sha256": digest(f),
                          "review": latest.get(key(f), {}).get("decision", "unreviewed"),
                          "review_id": latest.get(key(f), {}).get("review_id")} for f in findings],
            "review_history": history, "automatic_corrections": False, "source_records_modified": False}


def main():
    p = argparse.ArgumentParser(description="User review of structural prose findings")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("review")
    for flag in ("request-id", "code", "subject-id", "finding-sha256", "reason"):
        a.add_argument("--" + flag, required=True)
    a.add_argument("--decision", choices=DECISIONS, required=True)
    a.add_argument("--confirm-user-decision", action="store_true")
    sub.add_parser("list")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        cards = card_records()
        drafts = draft_records(cards)
        findings = diagnose(cards, move_records(cards), drafts, revision_records(drafts))["findings"]
        if args.command == "review":
            result = review(findings, args.request_id, args.code, args.subject_id,
                            args.finding_sha256, args.decision, args.reason, args.confirm_user_decision)
        elif args.command == "list":
            result = overview(findings)
        else:
            history, _, _ = records(findings)
            result = {"findings": len(findings), "reviews": len(history), "source_records_modified": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
