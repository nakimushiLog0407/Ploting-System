#!/usr/bin/env python3
"""Append-only chapter/scene plot cards; user-approved placement only.

Unplaced cards remain in an idea inbox. Chapter numbers and scene sequence
are never inferred. No prose or canon is created from plot metadata.
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
PROPOSALS = ROOT / "plot_cards" / "proposals"
REVIEWS = ROOT / "plot_cards" / "reviews"
ID = re.compile(r"^PLOT-\d{6,}$")
KINDS = ("chapter", "scene")
DECISIONS = ("approved", "rejected")


def encode(item):
    return (json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def records():
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("PLOT-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        required = {"plot_id", "request_id", "kind", "title", "description",
                    "parent_chapter_id", "position", "related_candidate_ids", "created_at"}
        if not isinstance(item, dict) or set(item) != required:
            raise ValueError("Invalid plot card schema")
        pid, req = item["plot_id"], item["request_id"]
        if not isinstance(pid, str) or not ID.fullmatch(pid) or path.name != pid + ".json" or pid in proposals:
            raise ValueError("Invalid plot card ID")
        if not isinstance(req, str) or not 1 <= len(req) <= 128 or req in requests or any(ord(c) < 32 for c in req):
            raise ValueError("Invalid request ID")
        if item["kind"] not in KINDS or not isinstance(item["title"], str) or not item["title"].strip() or len(item["title"]) > 200:
            raise ValueError("Invalid plot card kind or title")
        if not isinstance(item["description"], str) or len(item["description"]) > 20000:
            raise ValueError("Invalid plot description")
        if item["parent_chapter_id"] is not None and (not isinstance(item["parent_chapter_id"], str) or not ID.fullmatch(item["parent_chapter_id"])):
            raise ValueError("Invalid chapter reference")
        if item["position"] is not None and (type(item["position"]) is not int or item["position"] < 1):
            raise ValueError("Invalid explicit position")
        if item["kind"] == "chapter" and item["parent_chapter_id"] is not None:
            raise ValueError("Chapter cannot have parent chapter")
        if item["kind"] == "scene" and item["position"] is not None and item["parent_chapter_id"] is None:
            raise ValueError("Scene position requires parent chapter")
        refs = item["related_candidate_ids"]
        if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs) or len(refs) != len(set(refs)):
            raise ValueError("Invalid candidate references")
        if not isinstance(item["created_at"], str) or not item["created_at"]:
            raise ValueError("Invalid created timestamp")
        proposals[pid] = (item, path)
        requests.add(req)
    reviews = {}
    for path in sorted(REVIEWS.glob("PLOT-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"plot_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid plot review schema")
        pid = item["plot_id"]
        if pid not in proposals or path.name != pid + ".json" or pid in reviews:
            raise ValueError("Review without plot proposal")
        if item["proposal_sha256"] != hashlib.sha256(proposals[pid][1].read_bytes()).hexdigest():
            raise ValueError("Plot proposal modified after review")
        if item["decision"] not in DECISIONS or item["actor"] != "user":
            raise ValueError("Explicit user review required")
        if not isinstance(item["reason"], str) or len(item["reason"]) > 20000 or not isinstance(item["reviewed_at"], str) or not item["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        reviews[pid] = item
    result = [{**item, "status": reviews[pid]["decision"] if pid in reviews else "proposed"}
              for pid, (item, _) in proposals.items()]
    by_id = {x["plot_id"]: x for x in result}
    for x in result:
        parent = x["parent_chapter_id"]
        if parent is not None:
            if parent not in by_id or by_id[parent]["kind"] != "chapter":
                raise ValueError("Scene references missing chapter")
            if x["status"] == "approved" and by_id[parent]["status"] != "approved":
                raise ValueError("Approved scene requires approved parent chapter")
    positions = set()
    for x in result:
        if x["status"] != "approved" or x["position"] is None:
            continue
        key = (x["kind"], x["parent_chapter_id"], x["position"])
        if key in positions:
            raise ValueError("Duplicate approved plot position")
        positions.add(key)
    return result


def propose(request_id, kind, title, description, parent, position, refs):
    existing = records()
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if kind not in KINDS or not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("Invalid kind or title")
    if not isinstance(description, str) or len(description) > 20000:
        raise ValueError("Invalid description")
    if position is not None and (type(position) is not int or position < 1):
        raise ValueError("Invalid position")
    if kind == "chapter" and parent is not None:
        raise ValueError("Chapters cannot have parents")
    if kind == "scene" and position is not None and parent is None:
        raise ValueError("Scene position requires chapter")
    if parent is not None and not any(x["plot_id"] == parent and x["kind"] == "chapter" for x in existing):
        raise ValueError("Unknown parent chapter")
    if len(refs) != len(set(refs)):
        raise ValueError("Duplicate candidate references")
    from effective_canon import effective_entries
    from canon_catalog import build_catalog
    known = {x["candidate_id"] for x in effective_entries(build_catalog())}
    if any(x not in known for x in refs):
        raise ValueError("Related candidate must be approved")
    for x in existing:
        if x["request_id"] == request_id:
            if (x["kind"], x["title"], x["description"], x["parent_chapter_id"], x["position"], x["related_candidate_ids"]) == (kind, title, description, parent, position, refs):
                return {"status": "already_saved", "plot_id": x["plot_id"]}
            raise ValueError("Request ID reused")
    pid = f"PLOT-{max((int(x['plot_id'][5:]) for x in existing), default=0)+1:06d}"
    item = {"plot_id": pid, "request_id": request_id, "kind": kind, "title": title,
            "description": description, "parent_chapter_id": parent, "position": position,
            "related_candidate_ids": refs, "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (pid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "plot_id": pid}


def review(pid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in DECISIONS or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review")
    existing = records()
    found = [x for x in existing if x["plot_id"] == pid and x["status"] == "proposed"]
    if len(found) != 1:
        raise ValueError("Pending plot card not found")
    x = found[0]
    if decision == "approved":
        if x["parent_chapter_id"] is not None:
            if not any(y["plot_id"] == x["parent_chapter_id"] and y["status"] == "approved" for y in existing):
                raise ValueError("Parent chapter must be approved first")
        if x["position"] is not None and any(y["status"] == "approved" and y["kind"] == x["kind"] and
                y["parent_chapter_id"] == x["parent_chapter_id"] and y["position"] == x["position"] for y in existing):
            raise ValueError("Approved plot position already occupied")
    path = PROPOSALS / (pid + ".json")
    item = {"plot_id": pid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (pid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "plot_id": pid, "decision": decision}


def overview(items):
    approved = [x for x in items if x["status"] == "approved"]
    chapters = sorted((x for x in approved if x["kind"] == "chapter" and x["position"] is not None),
                      key=lambda x: (x["position"], x["plot_id"]))
    return {"ordered_chapters": [
                {**c, "scenes": sorted((s for s in approved if s["kind"] == "scene"
                                       and s["parent_chapter_id"] == c["plot_id"] and s["position"] is not None),
                                      key=lambda s: (s["position"], s["plot_id"]))}
                for c in chapters],
            "unplaced_chapters": [x for x in approved if x["kind"] == "chapter" and x["position"] is None],
            "unplaced_scenes": [x for x in approved if x["kind"] == "scene" and
                                (x["parent_chapter_id"] is None or x["position"] is None)],
            "pending": [x for x in items if x["status"] == "proposed"],
            "rejected": [x for x in items if x["status"] == "rejected"],
            "sequence_inferred": False, "canon_modified": False}


def main():
    p = argparse.ArgumentParser(description="Explicitly reviewed plot cards and unplaced idea inbox")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--kind", choices=KINDS, required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--description", default="")
    a.add_argument("--parent-chapter-id")
    a.add_argument("--position", type=int)
    a.add_argument("--related-candidate-id", action="append", default=[])
    a = sub.add_parser("review")
    a.add_argument("--plot-id", required=True)
    a.add_argument("--decision", choices=DECISIONS, required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    sub.add_parser("list")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        if args.command == "propose":
            result = propose(args.request_id, args.kind, args.title, args.description,
                             args.parent_chapter_id, args.position, args.related_candidate_id)
        elif args.command == "review":
            result = review(args.plot_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            items = records()
            result = overview(items) if args.command == "list" else {
                "total": len(items), "approved": sum(x["status"] == "approved" for x in items),
                "pending": sum(x["status"] == "proposed" for x in items)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
