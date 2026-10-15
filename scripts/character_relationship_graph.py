#!/usr/bin/env python3
"""Read-only character relationship graph from explicitly approved records.

Existing generic relationships are not interpreted as friendship or family.
"""
import argparse
import json
import sys
from canon_catalog import build_catalog
from relationship_workflow import effective
from character_relation_types import records as typed_records


def build_graph(entries, relations, typed_relations=()):
    characters = {e["candidate_id"]: e for e in entries if e["kind"] == "character"}
    nodes = [{"character_id": cid, "content": e["content"],
              "source_id": e["source_id"], "decision_id": e["decision_id"]}
             for cid, e in sorted(characters.items())]
    edges = []
    for rel in relations:
        if rel["status"] != "approved":
            continue
        a, b = rel["from_candidate_id"], rel["to_candidate_id"]
        if a not in characters or b not in characters:
            continue
        edges.append({"relationship_id": rel["relationship_id"],
                      "from_character_id": a, "to_character_id": b,
                      "relation": rel["relation"], "evidence": rel["evidence"]})
    for rel in typed_relations:
        if rel["status"] != "approved":
            continue
        a, b = rel["from_character_id"], rel["to_character_id"]
        if a not in characters or b not in characters:
            raise ValueError("Approved typed relation references missing character")
        edges.append({"relationship_id": rel["relation_id"],
                      "from_character_id": a, "to_character_id": b,
                      "relation": rel["relation_type"], "evidence": rel["evidence"],
                      "phase": rel["phase"], "description": rel["description"],
                      "source": "typed"})
    edges.sort(key=lambda x: x["relationship_id"])
    return {"nodes": nodes, "edges": edges}


def main():
    parser = argparse.ArgumentParser(description="Approved character-to-character graph")
    parser.add_argument("--character-id")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    try:
        graph = build_graph(build_catalog(), effective("approved"), typed_records())
        if args.character_id:
            if not any(n["character_id"] == args.character_id for n in graph["nodes"]):
                raise ValueError("Approved character not found")
            graph["edges"] = [e for e in graph["edges"] if args.character_id in (e["from_character_id"], e["to_character_id"])]
            selected = {args.character_id}
            for e in graph["edges"]:
                selected.update((e["from_character_id"], e["to_character_id"]))
            graph["nodes"] = [n for n in graph["nodes"] if n["character_id"] in selected]
        result = {"characters": len(graph["nodes"]), "relationships": len(graph["edges"])} if args.summary else graph
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
