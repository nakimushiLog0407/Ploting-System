#!/usr/bin/env python3
"""Read-only integrated view of explicitly approved story phases, events and precedence.

Parallel tiers are a visualization aid, NOT proof of ordering within a tier.
No proposed/rejected information becomes canon.
"""
import argparse
import json
import sys

from canon_catalog import build_catalog
from story_timeline import approved_phases
from event_placement import records as placement_records
from event_order import records as order_records, approved_locations, layers


def build_view(entries, phases, placements, orders):
    if not isinstance(phases, list) or len(set(phases)) != len(phases):
        raise ValueError("Invalid phase order")
    events = {x["candidate_id"]: x for x in entries if x["kind"] == "event"}
    locations = approved_locations(placements, phases)
    for eid in locations:
        if eid not in events:
            raise ValueError("Approved placement references missing event")
    result = []
    for phase in phases:
        ids = sorted(eid for eid, p in locations.items() if p == phase)
        relevant = [x for x in orders if x["status"] == "approved"
                    and x["before_event_id"] in ids]
        edges = []
        links = []
        for item in relevant:
            a, b = item["before_event_id"], item["after_event_id"]
            if b not in ids:
                raise ValueError("Approved order crosses phase or references missing event")
            edges.append((a, b))
            links.append({"order_id": item["order_id"], "before_event_id": a,
                          "after_event_id": b, "evidence": item["evidence"]})
        tiers = layers(ids, edges)
        by_id = {eid: {"event_id": eid, "content": events[eid]["content"],
                       "source_id": events[eid]["source_id"],
                       "decision_id": events[eid]["decision_id"]}
                 for eid in ids}
        result.append({"phase": phase,
                       "tiers": [[by_id[eid] for eid in tier] for tier in tiers],
                       "precedence": sorted(links, key=lambda x: x["order_id"]),
                       "events_without_explicit_precedence": [
                           by_id[eid] for eid in ids
                           if not any(eid in edge for edge in edges)]})
    return {
        "phases": result,
        "unplaced_events": [
            {"event_id": eid, "content": x["content"],
             "source_id": x["source_id"], "decision_id": x["decision_id"]}
            for eid, x in sorted(events.items()) if eid not in locations
        ],
        "tier_semantics": "Events within a tier have no established order; different tiers do not imply all pairwise precedence.",
        "canon_source": "approved_only",
    }


def main():
    p = argparse.ArgumentParser(description="Integrated approved story chronology")
    p.add_argument("--summary", action="store_true")
    p.add_argument("--phase")
    args = p.parse_args()
    try:
        phases = approved_phases()
        if args.phase is not None and args.phase not in phases:
            raise ValueError("Approved phase not found")
        result = build_view(build_catalog(), phases, placement_records(), order_records())
        if args.phase is not None:
            result["phases"] = [x for x in result["phases"] if x["phase"] == args.phase]
        if args.summary:
            result = {"phases": len(result["phases"]),
                      "placed_events": sum(sum(len(t) for t in p["tiers"]) for p in result["phases"]),
                      "approved_precedence": sum(len(p["precedence"]) for p in result["phases"]),
                      "unplaced_events": len(result["unplaced_events"])}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
