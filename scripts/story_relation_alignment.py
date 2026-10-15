#!/usr/bin/env python3
"""Read-only phase alignment of approved events and approved character relations.

Same-phase co-occurrence does NOT establish causality or event-level timing.
Unassigned/unknown relationship phases remain separate.
"""
import argparse
import json
import sys

from canon_catalog import build_catalog
from story_timeline import approved_phases
from event_placement import records as placement_records
from event_order import records as order_records
from character_relation_types import records as relation_records
from story_chronology_view import build_view


def align(entries, phases, placements, orders, relations, character_id=None):
    characters = {x["candidate_id"]: x for x in entries if x["kind"] == "character"}
    if character_id is not None and character_id not in characters:
        raise ValueError("Approved character not found")
    chronology = build_view(entries, phases, placements, orders)
    by_phase = {x["phase"]: x for x in chronology["phases"]}
    for item in chronology["phases"]:
        item["character_relations"] = []
    unassigned = []
    unknown = []
    for rel in relations:
        if rel["status"] != "approved":
            continue
        a, b = rel["from_character_id"], rel["to_character_id"]
        if a not in characters or b not in characters:
            raise ValueError("Approved relation references missing character")
        if character_id is not None and character_id not in (a, b):
            continue
        data = {"relation_id": rel["relation_id"], "from_character_id": a,
                "to_character_id": b, "relation_type": rel["relation_type"],
                "phase": rel["phase"], "description": rel["description"],
                "evidence": rel["evidence"]}
        phase = rel["phase"]
        if not phase:
            unassigned.append(data)
        elif phase not in by_phase:
            unknown.append(data)
        else:
            by_phase[phase]["character_relations"].append(data)
    for item in chronology["phases"]:
        item["character_relations"].sort(key=lambda x: x["relation_id"])
    chronology["relations_without_phase"] = sorted(unassigned, key=lambda x: x["relation_id"])
    chronology["relations_with_unrecognized_phase"] = sorted(unknown, key=lambda x: x["relation_id"])
    chronology["relation_event_causality"] = "not_established"
    chronology["relation_event_order"] = "not_established"
    chronology["phase_alignment_only"] = True
    return chronology


def main():
    p = argparse.ArgumentParser(description="Approved phase alignment of story events and character relationships")
    p.add_argument("--phase")
    p.add_argument("--character-id")
    p.add_argument("--summary", action="store_true")
    args = p.parse_args()
    try:
        phases = approved_phases()
        if args.phase is not None and args.phase not in phases:
            raise ValueError("Approved phase not found")
        result = align(build_catalog(), phases, placement_records(), order_records(),
                       relation_records(), args.character_id)
        if args.phase is not None:
            result["phases"] = [x for x in result["phases"] if x["phase"] == args.phase]
        if args.summary:
            result = {
                "phases": len(result["phases"]),
                "placed_events": sum(sum(len(tier) for tier in p["tiers"]) for p in result["phases"]),
                "character_relations": sum(len(p["character_relations"]) for p in result["phases"]),
                "relations_without_phase": len(result["relations_without_phase"]),
                "relations_with_unrecognized_phase": len(result["relations_with_unrecognized_phase"]),
                "unplaced_events": len(result["unplaced_events"]),
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
