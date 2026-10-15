#!/usr/bin/env python3
"""Append-only approved plot relocation overlay; no implicit reordering.

Each move specifies the entire destination (chapter and position), or unplaces
the card. Moves to occupied positions are rejected; no automatic shifting.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from plot_cards import records as card_records, overview as card_overview, encode

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "plot_moves" / "proposals"
REVIEWS = ROOT / "plot_moves" / "reviews"
PATTERN = re.compile(r"^PMOV-\d{6,}$")


def location(card):
    return {"parent_chapter_id": card["parent_chapter_id"], "position": card["position"]}


def validate_target(card, target, cards):
    if not isinstance(target, dict) or set(target) != {"parent_chapter_id", "position"}:
        raise ValueError("Invalid destination")
    parent, position = target["parent_chapter_id"], target["position"]
    if position is not None and (type(position) is not int or position < 1):
        raise ValueError("Invalid destination position")
    if card["kind"] == "chapter":
        if parent is not None:
            raise ValueError("Chapter cannot have a parent")
    else:
        if parent is not None and (parent not in cards or cards[parent]["kind"] != "chapter" or cards[parent]["status"] != "approved"):
            raise ValueError("Destination chapter must be approved")
        if parent is None and position is not None:
            raise ValueError("Unassigned scene cannot have a position")


def effective(cards, moves):
    by_id = {x["plot_id"]: dict(x) for x in cards}
    for move in moves:
        if move["status"] != "approved":
            continue
        cid = move["plot_id"]
        if cid not in by_id or by_id[cid]["status"] != "approved":
            raise ValueError("Move references unapproved card")
        card = by_id[cid]
        if location(card) != move["before"]:
            raise ValueError("Approved move has stale baseline")
        validate_target(card, move["after"], by_id)
        card.update(move["after"])
    positions = set()
    for card in by_id.values():
        if card["status"] != "approved" or card["position"] is None:
            continue
        key = (card["kind"], card["parent_chapter_id"], card["position"])
        if key in positions:
            raise ValueError("Duplicate approved plot position after moves")
        positions.add(key)
    return list(by_id.values())


def records(cards):
    by_id = {x["plot_id"]: x for x in cards}
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("PMOV-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"move_id", "request_id", "plot_id", "before", "after", "reason", "created_at"}:
            raise ValueError("Invalid move proposal schema")
        mid, req = x["move_id"], x["request_id"]
        if not isinstance(mid, str) or not PATTERN.fullmatch(mid) or path.name != mid + ".json" or mid in proposals:
            raise ValueError("Invalid move ID")
        if not isinstance(req, str) or not 1 <= len(req) <= 128 or any(ord(c) < 32 for c in req) or req in requests:
            raise ValueError("Invalid request ID")
        if x["plot_id"] not in by_id or by_id[x["plot_id"]]["status"] != "approved":
            raise ValueError("Move requires approved card")
        validate_target(by_id[x["plot_id"]], x["before"], by_id)
        validate_target(by_id[x["plot_id"]], x["after"], by_id)
        if x["before"] == x["after"]:
            raise ValueError("Move cannot be a no-op")
        if not isinstance(x["reason"], str) or not x["reason"].strip() or len(x["reason"]) > 20000:
            raise ValueError("Move reason required")
        if not isinstance(x["created_at"], str) or not x["created_at"]:
            raise ValueError("Invalid timestamp")
        proposals[mid] = (x, path)
        requests.add(req)
    reviews = {}
    for path in sorted(REVIEWS.glob("PMOV-*.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(x, dict) or set(x) != {"move_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid move review schema")
        mid = x["move_id"]
        if mid not in proposals or path.name != mid + ".json" or mid in reviews:
            raise ValueError("Review without move proposal")
        if x["proposal_sha256"] != hashlib.sha256(proposals[mid][1].read_bytes()).hexdigest():
            raise ValueError("Move proposal modified")
        if x["decision"] not in ("approved", "rejected") or x["actor"] != "user":
            raise ValueError("Invalid move review")
        if not isinstance(x["reason"], str) or len(x["reason"]) > 20000 or not isinstance(x["reviewed_at"], str) or not x["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        reviews[mid] = x
    moves = [{**x, "status": reviews[mid]["decision"] if mid in reviews else "proposed"}
             for mid, (x, _) in proposals.items()]
    effective(cards, sorted(moves, key=lambda x: int(x["move_id"][5:])))
    return moves


def propose(cards, request_id, plot_id, parent, position, reason):
    moves = records(cards)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    current = {x["plot_id"]: x for x in effective(cards, sorted(moves, key=lambda x: int(x["move_id"][5:])))}
    if plot_id not in current or current[plot_id]["status"] != "approved":
        raise ValueError("Approved plot card required")
    after = {"parent_chapter_id": parent, "position": position}
    validate_target(current[plot_id], after, current)
    if after == location(current[plot_id]):
        raise ValueError("No change requested")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 20000:
        raise ValueError("Move reason required")
    for move in moves:
        if move["request_id"] == request_id:
            if (move["plot_id"], move["after"], move["reason"]) == (plot_id, after, reason):
                return {"status": "already_saved", "move_id": move["move_id"]}
            raise ValueError("Request ID reused")
        if move["plot_id"] == plot_id and move["status"] == "proposed":
            raise ValueError("Pending move already exists")
    mid = f"PMOV-{max((int(x['move_id'][5:]) for x in moves), default=0)+1:06d}"
    item = {"move_id": mid, "request_id": request_id, "plot_id": plot_id,
            "before": location(current[plot_id]), "after": after, "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (mid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "move_id": mid}


def review(cards, mid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review")
    moves = records(cards)
    match = [x for x in moves if x["move_id"] == mid and x["status"] == "proposed"]
    if len(match) != 1:
        raise ValueError("Pending move not found")
    move = match[0]
    if decision == "approved":
        effective(cards, sorted(moves + [{**move, "status": "approved"}], key=lambda x: int(x["move_id"][5:])))
    path = PROPOSALS / (mid + ".json")
    item = {"move_id": mid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (mid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "move_id": mid, "decision": decision}


def main():
    p = argparse.ArgumentParser(description="User-reviewed chapter/scene placement changes")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--plot-id", required=True)
    a.add_argument("--parent-chapter-id")
    a.add_argument("--position", type=int)
    a.add_argument("--reason", required=True)
    a = sub.add_parser("review")
    a.add_argument("--move-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    sub.add_parser("list")
    sub.add_parser("verify")
    args = p.parse_args()
    try:
        cards = card_records()
        if args.command == "propose":
            result = propose(cards, args.request_id, args.plot_id, args.parent_chapter_id, args.position, args.reason)
        elif args.command == "review":
            result = review(cards, args.move_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            moves = records(cards)
            result = {"moves": moves, "plot": card_overview(effective(cards, sorted(moves, key=lambda x: int(x["move_id"][5:])))),
                      "source_cards_modified": False} if args.command == "list" else {
                          "moves": len(moves), "approved": sum(x["status"] == "approved" for x in moves),
                          "source_cards_modified": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
