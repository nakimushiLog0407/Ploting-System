#!/usr/bin/env python3
"""Read-only character dossiers from approved candidates and relationships."""
import argparse
import json
import sys
from canon_catalog import build_catalog
from relationship_workflow import effective

def dossiers(entries, relations):
    by_id = {e["candidate_id"]: e for e in entries}
    output = []
    for character in entries:
        if character["kind"] != "character":
            continue
        cid = character["candidate_id"]
        linked = []
        for rel in relations:
            if rel["status"] != "approved":
                continue
            a, b = rel["from_candidate_id"], rel["to_candidate_id"]
            if cid not in (a, b):
                continue
            other_id = b if a == cid else a
            if other_id not in by_id:
                raise ValueError("Approved relationship points to missing candidate")
            other = by_id[other_id]
            linked.append({
                "relationship_id": rel["relationship_id"],
                "relation": rel["relation"],
                "direction": "outgoing" if a == cid else "incoming",
                "candidate_id": other_id,
                "kind": other["kind"],
                "content": other["content"],
                "source_id": other["source_id"],
                "decision_id": other["decision_id"],
            })
        linked.sort(key=lambda e: (e["relation"], e["candidate_id"]))
        output.append({
            "character_id": cid, "content": character["content"],
            "source_id": character["source_id"], "quote": character["quote"],
            "decision_id": character["decision_id"], "related": linked,
        })
    return sorted(output, key=lambda e: e["character_id"])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--character-id")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    try:
        items = dossiers(build_catalog(), effective("approved"))
        if args.character_id:
            items = [i for i in items if i["character_id"] == args.character_id]
            if not items:
                raise ValueError("Approved character not found")
        result = {"characters": len(items), "links": sum(len(i["related"]) for i in items)} if args.summary else {"characters": items}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
