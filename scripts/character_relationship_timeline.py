#!/usr/bin/env python3
"""Approved-only character relationship history.

Phase labels are NOT chronologically sortable. Explicit display order is temporary
and never saved as canon; unlisted phases remain unordered.
"""
import argparse
import json
import sys
from canon_catalog import build_catalog
from character_relation_types import records


def timeline(entries, relations, character_id=None, phase_order=()):
    characters = {x["candidate_id"]: x for x in entries if x["kind"] == "character"}
    if character_id is not None and character_id not in characters:
        raise ValueError("Approved character not found")
    if len(set(phase_order)) != len(phase_order) or any(not isinstance(p, str) or not p.strip() for p in phase_order):
        raise ValueError("Invalid or duplicate phase order")
    pairs = {}
    for item in relations:
        if item["status"] != "approved":
            continue
        a, b = item["from_character_id"], item["to_character_id"]
        if a not in characters or b not in characters:
            raise ValueError("Approved relation references missing character")
        if character_id and character_id not in (a, b):
            continue
        key = tuple(sorted((a, b)))
        pairs.setdefault(key, []).append({
            "relation_id": item["relation_id"], "from_character_id": a,
            "to_character_id": b, "relation_type": item["relation_type"],
            "phase": item["phase"], "description": item["description"],
            "evidence": item["evidence"],
        })
    result = []
    order = {p: i for i, p in enumerate(phase_order)}
    for key, items in sorted(pairs.items()):
        known = sorted((x for x in items if x["phase"] in order),
                       key=lambda x: (order[x["phase"]], x["relation_id"]))
        unknown = sorted((x for x in items if x["phase"] not in order),
                         key=lambda x: (x["phase"], x["relation_id"]))
        result.append({
            "character_ids": list(key),
            "ordered": known,
            "unordered": unknown,
        })
    return {"pairs": result, "phase_order": list(phase_order),
            "order_is_temporary": True}


def main():
    p = argparse.ArgumentParser(description="Approved character relationship history")
    p.add_argument("--character-id")
    p.add_argument("--phase-order", nargs="*", default=[],
                   help="Explicit temporary display order; no order is inferred or saved")
    p.add_argument("--summary", action="store_true")
    args = p.parse_args()
    try:
        result = timeline(build_catalog(), records(), args.character_id, args.phase_order)
        if args.summary:
            result = {"pairs": len(result["pairs"]),
                      "ordered": sum(len(x["ordered"]) for x in result["pairs"]),
                      "unordered": sum(len(x["unordered"]) for x in result["pairs"])}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
