#!/usr/bin/env python3
"""Read-only diagnostic candidates. Never edits canon or declares literary contradictions.

Hard structural conflicts are separated from review-only gaps. Pending proposals
are not treated as canon. Relationship types are never assumed mutually exclusive.
"""
import argparse
import json
import sys
from effective_canon import effective_entries
from canon_catalog import build_catalog
from story_timeline import approved_phases
from event_placement import records as placement_records
from event_order import records as order_records, approved_locations, layers
from character_relation_types import records as relation_records


def diagnose(entries, phases, placements, orders, relations):
    events = {x["candidate_id"] for x in entries if x["kind"] == "event"}
    characters = {x["candidate_id"] for x in entries if x["kind"] == "character"}
    locations = approved_locations(placements, phases)
    findings = []

    def add(code, severity, references, detail):
        findings.append({"code": code, "severity": severity,
                         "references": sorted(set(references)), "detail": detail,
                         "requires_user_review": True})

    for eid in sorted(events - locations.keys()):
        add("event_unplaced", "review", [eid], "Approved event has no approved phase placement")

    for rel in relations:
        if rel["status"] != "approved":
            continue
        a, b = rel["from_character_id"], rel["to_character_id"]
        if a not in characters or b not in characters:
            add("missing_character", "structural", [rel["relation_id"], a, b],
                "Approved relationship references a non-approved character")
        if not rel["phase"]:
            add("relation_phase_unset", "review", [rel["relation_id"]],
                "Approved relationship has no phase")
        elif rel["phase"] not in phases:
            add("relation_phase_unrecognized", "review", [rel["relation_id"]],
                "Relationship phase does not match the approved global timeline")

    for placement in placements:
        if placement["status"] == "approved":
            if placement["event_id"] not in events or placement["phase"] not in phases:
                add("invalid_event_placement", "structural",
                    [placement["placement_id"], placement["event_id"]],
                    "Approved placement references missing event or phase")

    for order in orders:
        if order["status"] != "approved":
            continue
        a, b = order["before_event_id"], order["after_event_id"]
        if a not in locations or b not in locations or locations[a] != locations[b]:
            add("invalid_event_order", "structural", [order["order_id"], a, b],
                "Approved precedence references unplaced events or crosses phases")

    # A cycle is a structural conflict, not a subjective story contradiction.
    for phase in phases:
        nodes = [eid for eid, p in locations.items() if p == phase]
        phase_orders = [x for x in orders if x["status"] == "approved"
                        and x["before_event_id"] in nodes and x["after_event_id"] in nodes]
        try:
            layers(nodes, [(x["before_event_id"], x["after_event_id"]) for x in phase_orders])
        except ValueError:
            add("event_order_cycle", "structural",
                [x["order_id"] for x in phase_orders],
                "Approved event precedence contains an invalid edge or cycle")

    # Pending reverse edges are only a review candidate, never a canon conflict.
    approved_edges = {(x["before_event_id"], x["after_event_id"]): x["order_id"]
                      for x in orders if x["status"] == "approved"}
    for order in orders:
        if order["status"] != "proposed":
            continue
        reverse = approved_edges.get((order["after_event_id"], order["before_event_id"]))
        if reverse:
            add("pending_reverse_order", "review", [order["order_id"], reverse],
                "Pending precedence reverses an approved precedence")

    findings.sort(key=lambda x: (x["severity"], x["code"], x["references"]))
    return {"findings": findings,
            "structural_count": sum(x["severity"] == "structural" for x in findings),
            "review_count": sum(x["severity"] == "review" for x in findings),
            "canon_modified": False,
            "scope": "structural_integrity_and_review_gaps_only",
            "literary_contradictions_automatically_determined": False}


def main():
    parser = argparse.ArgumentParser(description="Read-only canon integrity diagnostics")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    try:
        result = diagnose(effective_entries(build_catalog()), approved_phases(),
                          placement_records(), order_records(), relation_records())
        if args.summary:
            result = {"structural_count": result["structural_count"],
                      "review_count": result["review_count"],
                      "canon_modified": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
