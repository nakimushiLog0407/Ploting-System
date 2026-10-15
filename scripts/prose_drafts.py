#!/usr/bin/env python3
"""Immutable prose draft proposals and explicit user approval.

Never overwrites manuscript or approved prose. A scene can have one approved
draft in this first version; revision/replacement requires a separate workflow.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from plot_cards import records as plot_records, encode

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "prose_drafts" / "proposals"
REVIEWS = ROOT / "prose_drafts" / "reviews"
ID = re.compile(r"^DRAFT-\d{6,}$")


def records(cards):
    scenes = {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("DRAFT-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"draft_id", "request_id", "scene_id", "text", "notes", "created_at"}:
            raise ValueError("Invalid draft schema")
        did, req = item["draft_id"], item["request_id"]
        if not isinstance(did, str) or not ID.fullmatch(did) or path.name != did + ".json" or did in proposals:
            raise ValueError("Invalid draft ID")
        if not isinstance(req, str) or not 1 <= len(req) <= 128 or any(ord(c) < 32 for c in req) or req in requests:
            raise ValueError("Invalid request ID")
        if item["scene_id"] not in scenes:
            raise ValueError("Draft requires an approved scene")
        if not isinstance(item["text"], str) or not item["text"].strip() or len(item["text"]) > 200000:
            raise ValueError("Invalid prose content")
        if not isinstance(item["notes"], str) or len(item["notes"]) > 20000:
            raise ValueError("Invalid draft notes")
        if not isinstance(item["created_at"], str) or not item["created_at"]:
            raise ValueError("Invalid timestamp")
        proposals[did] = (item, path)
        requests.add(req)
    reviews = {}
    for path in sorted(REVIEWS.glob("DRAFT-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"draft_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid draft review schema")
        did = item["draft_id"]
        if did not in proposals or path.name != did + ".json" or did in reviews:
            raise ValueError("Review without draft")
        if item["proposal_sha256"] != hashlib.sha256(proposals[did][1].read_bytes()).hexdigest():
            raise ValueError("Draft changed after review")
        if item["decision"] not in ("approved", "rejected") or item["actor"] != "user":
            raise ValueError("Explicit user review required")
        if not isinstance(item["reason"], str) or len(item["reason"]) > 20000 or not isinstance(item["reviewed_at"], str) or not item["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        reviews[did] = item
    result = [{**x, "status": reviews[did]["decision"] if did in reviews else "proposed"}
              for did, (x, _) in proposals.items()]
    approved_scenes = set()
    for item in result:
        if item["status"] == "approved":
            if item["scene_id"] in approved_scenes:
                raise ValueError("Multiple approved prose drafts for one scene")
            approved_scenes.add(item["scene_id"])
    return result


def propose(cards, request_id, scene_id, prose, notes):
    existing = records(cards)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    for x in existing:
        if x["request_id"] == request_id:
            if (x["scene_id"], x["text"], x["notes"]) == (scene_id, prose, notes):
                return {"status": "already_saved", "draft_id": x["draft_id"]}
            raise ValueError("Request ID reused")
    did = f"DRAFT-{max((int(x['draft_id'][6:]) for x in existing), default=0)+1:06d}"
    item = {"draft_id": did, "request_id": request_id, "scene_id": scene_id,
            "text": prose, "notes": notes, "created_at": datetime.now(timezone.utc).isoformat()}
    if scene_id not in {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}:
        raise ValueError("Draft requires approved scene")
    if not isinstance(prose, str) or not prose.strip() or len(prose) > 200000:
        raise ValueError("Invalid prose content")
    if not isinstance(notes, str) or len(notes) > 20000:
        raise ValueError("Invalid notes")
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (did + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "draft_id": did}


def review(cards, did, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid decision")
    drafts = records(cards)
    matches = [x for x in drafts if x["draft_id"] == did and x["status"] == "proposed"]
    if len(matches) != 1:
        raise ValueError("Pending draft not found")
    if decision == "approved" and any(x["status"] == "approved" and x["scene_id"] == matches[0]["scene_id"] for x in drafts):
        raise ValueError("Scene already has approved prose; revision workflow required")
    path = PROPOSALS / (did + ".json")
    item = {"draft_id": did, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (did + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "draft_id": did, "decision": decision}


def overview(drafts):
    return {"approved": [x for x in drafts if x["status"] == "approved"],
            "pending": [x for x in drafts if x["status"] == "proposed"],
            "rejected": [x for x in drafts if x["status"] == "rejected"],
            "drafts_automatically_approved": False, "original_plot_modified": False}


def main():
    p = argparse.ArgumentParser(description="Prose drafts require explicit user approval")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--scene-id", required=True)
    a.add_argument("--text", required=True)
    a.add_argument("--notes", default="")
    a = sub.add_parser("review")
    a.add_argument("--draft-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    sub.add_parser("list")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        cards = plot_records()
        if args.command == "propose":
            result = propose(cards, args.request_id, args.scene_id, args.text, args.notes)
        elif args.command == "review":
            result = review(cards, args.draft_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            drafts = records(cards)
            result = overview(drafts) if args.command == "list" else {
                "total": len(drafts), "approved": sum(x["status"] == "approved" for x in drafts),
                "pending": sum(x["status"] == "proposed" for x in drafts)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
