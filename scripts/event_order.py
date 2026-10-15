#!/usr/bin/env python3
"""Append-only, explicitly reviewed precedence between approved events in one phase.

A DAG defines partial order, not a total order. Concurrent events are not sorted
chronologically by their IDs. Transitive precedence is derived only from approved edges.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from event_placement import records as placement_records
from story_timeline import approved_phases

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "event_order" / "proposals"
REVIEWS = ROOT / "event_order" / "reviews"
PATTERN = re.compile(r"EOR-\d{6,}")


def encode(item):
    return (json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def approved_locations(placements, phases):
    if len(set(phases)) != len(phases):
        raise ValueError("Duplicate approved phase")
    locations = {}
    for x in placements:
        if x["status"] != "approved":
            continue
        eid, phase = x["event_id"], x["phase"]
        if phase not in phases or eid in locations:
            raise ValueError("Invalid approved event placement")
        locations[eid] = phase
    return locations


def layers(nodes, edges):
    """Return parallel tiers; a tier does NOT assert order between its events."""
    remaining = set(nodes)
    outgoing = {n: set() for n in remaining}
    incoming = {n: set() for n in remaining}
    for a, b in edges:
        if a not in remaining or b not in remaining or a == b:
            raise ValueError("Invalid event precedence edge")
        outgoing[a].add(b)
        incoming[b].add(a)
    result = []
    while remaining:
        ready = sorted(n for n in remaining if not (incoming[n] & remaining))
        if not ready:
            raise ValueError("Event order cycle detected")
        result.append(ready)
        remaining.difference_update(ready)
    return result


def records(placements=None, phases=None):
    if placements is None:
        placements = placement_records()
    if phases is None:
        phases = approved_phases()
    locations = approved_locations(placements, phases)
    proposals, requests = {}, set()
    for path in sorted(PROPOSALS.glob("EOR-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"order_id", "request_id", "before_event_id", "after_event_id", "evidence", "created_at"}:
            raise ValueError("Invalid event order proposal")
        oid, request = item["order_id"], item["request_id"]
        if not isinstance(oid, str) or not PATTERN.fullmatch(oid) or path.name != oid + ".json" or oid in proposals:
            raise ValueError("Invalid event order ID")
        if not isinstance(request, str) or not 1 <= len(request) <= 128 or any(ord(c) < 32 for c in request) or request in requests:
            raise ValueError("Invalid request ID")
        a, b = item["before_event_id"], item["after_event_id"]
        if a not in locations or b not in locations or a == b or locations[a] != locations[b]:
            raise ValueError("Events must be distinct and approved in the same phase")
        if not isinstance(item["evidence"], str) or len(item["evidence"]) > 20000 or not isinstance(item["created_at"], str) or not item["created_at"]:
            raise ValueError("Invalid order metadata")
        proposals[oid] = (item, path)
        requests.add(request)
    reviews = {}
    for path in sorted(REVIEWS.glob("EOR-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or set(item) != {"order_id", "proposal_sha256", "decision", "actor", "reason", "reviewed_at"}:
            raise ValueError("Invalid order review")
        oid = item["order_id"]
        if oid not in proposals or path.name != oid + ".json" or oid in reviews:
            raise ValueError("Review without proposal")
        if item["decision"] not in ("approved", "rejected") or item["actor"] != "user":
            raise ValueError("Invalid review decision")
        if not isinstance(item["reason"], str) or len(item["reason"]) > 20000 or not isinstance(item["reviewed_at"], str) or not item["reviewed_at"]:
            raise ValueError("Invalid review metadata")
        if item["proposal_sha256"] != hashlib.sha256(proposals[oid][1].read_bytes()).hexdigest():
            raise ValueError("Event order proposal changed")
        reviews[oid] = item
    result = [{**item, "status": reviews[oid]["decision"] if oid in reviews else "proposed"}
              for oid, (item, _) in proposals.items()]
    for phase in phases:
        edges = [(x["before_event_id"], x["after_event_id"]) for x in result
                 if x["status"] == "approved" and locations[x["before_event_id"]] == phase]
        layers([n for n, p in locations.items() if p == phase], edges)
    return result


def propose(request_id, before, after, evidence):
    existing = records()
    locations = approved_locations(placement_records(), approved_phases())
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if before not in locations or after not in locations or before == after or locations[before] != locations[after]:
        raise ValueError("Both events must have approved placements in the same phase")
    if not isinstance(evidence, str) or len(evidence) > 20000:
        raise ValueError("Invalid evidence")
    for item in existing:
        if item["request_id"] == request_id:
            if (item["before_event_id"], item["after_event_id"], item["evidence"]) == (before, after, evidence):
                return {"status": "already_saved", "order_id": item["order_id"]}
            raise ValueError("Request ID reused")
        if item["before_event_id"] == before and item["after_event_id"] == after and item["status"] != "rejected":
            raise ValueError("Precedence already pending or approved")
    oid = f"EOR-{max((int(x['order_id'][4:]) for x in existing), default=0) + 1:06d}"
    item = {"order_id": oid, "request_id": request_id, "before_event_id": before,
            "after_event_id": after, "evidence": evidence,
            "created_at": datetime.now(timezone.utc).isoformat()}
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PROPOSALS / (oid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "order_id": oid}


def review(oid, decision, reason, confirmed):
    if confirmed is not True:
        raise ValueError("Explicit user decision required")
    if decision not in ("approved", "rejected") or not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid review")
    existing = records()
    match = [x for x in existing if x["order_id"] == oid and x["status"] == "proposed"]
    if len(match) != 1:
        raise ValueError("Pending order not found")
    if decision == "approved":
        placements, phases = placement_records(), approved_phases()
        locations = approved_locations(placements, phases)
        phase = locations[match[0]["before_event_id"]]
        edges = [(x["before_event_id"], x["after_event_id"]) for x in existing
                 if x["status"] == "approved" and locations[x["before_event_id"]] == phase]
        edges.append((match[0]["before_event_id"], match[0]["after_event_id"]))
        layers([n for n, p in locations.items() if p == phase], edges)
    path = PROPOSALS / (oid + ".json")
    item = {"order_id": oid, "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decision": decision, "actor": "user", "reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(REVIEWS / (oid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(encode(item))
    return {"status": "saved", "order_id": oid, "decision": decision}


def overview(placements, phases, orders):
    locations = approved_locations(placements, phases)
    output = []
    for phase in phases:
        nodes = [n for n, p in locations.items() if p == phase]
        approved = [x for x in orders if x["status"] == "approved" and locations[x["before_event_id"]] == phase]
        tiers = layers(nodes, [(x["before_event_id"], x["after_event_id"]) for x in approved])
        output.append({"phase": phase, "parallel_tiers": tiers,
                       "approved_precedence": [{"order_id": x["order_id"],
                                                "before_event_id": x["before_event_id"],
                                                "after_event_id": x["after_event_id"],
                                                "evidence": x["evidence"]} for x in approved]})
    return {"phases": output, "tiers_are_not_total_order": True}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--request-id", required=True)
    a.add_argument("--before-event-id", required=True)
    a.add_argument("--after-event-id", required=True)
    a.add_argument("--evidence", default="")
    a = sub.add_parser("review")
    a.add_argument("--order-id", required=True)
    a.add_argument("--decision", choices=("approved", "rejected"), required=True)
    a.add_argument("--reason", default="")
    a.add_argument("--confirm-user-decision", action="store_true")
    a = sub.add_parser("list")
    a.add_argument("--status", choices=("approved", "proposed", "rejected", "all"), default="approved")
    sub.add_parser("verify")
    a = sub.add_parser("overview")
    a.add_argument("--summary", action="store_true")
    args = p.parse_args()
    try:
        if args.command == "propose":
            result = propose(args.request_id, args.before_event_id, args.after_event_id, args.evidence)
        elif args.command == "review":
            result = review(args.order_id, args.decision, args.reason, args.confirm_user_decision)
        else:
            items = records()
            if args.command == "verify":
                result = {"verified": len(items)}
            elif args.command == "list":
                result = {"orders": [x for x in items if args.status == "all" or x["status"] == args.status]}
            else:
                result = overview(placement_records(), approved_phases(), items)
                if args.summary:
                    result = {"phases": len(result["phases"]),
                              "approved_precedence": sum(len(x["approved_precedence"]) for x in result["phases"])}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
