#!/usr/bin/env python3
"""Read-only dossiers for approved setting candidates and their approved links.

No automatic inference of place, organization, or terminology is performed.
"""
import argparse
import json
import sys

from canon_catalog import build_catalog
from relationship_workflow import effective


def build_dossiers(entries, relations):
    by_id = {e["candidate_id"]: e for e in entries}
    output = []
    for setting in entries:
        if setting["kind"] != "setting":
            continue
        sid = setting["candidate_id"]
        links = []
        for relation in relations:
            if relation["status"] != "approved":
                continue
            a, b = relation["from_candidate_id"], relation["to_candidate_id"]
            if sid not in (a, b):
                continue
            other_id = b if a == sid else a
            if other_id not in by_id:
                raise ValueError("Approved relation references missing candidate")
            other = by_id[other_id]
            links.append({
                "relationship_id": relation["relationship_id"],
                "relation": relation["relation"],
                "direction": "outgoing" if a == sid else "incoming",
                "candidate_id": other_id,
                "kind": other["kind"],
                "content": other["content"],
                "source_id": other["source_id"],
                "decision_id": other["decision_id"],
            })
        links.sort(key=lambda x: (x["relation"], x["candidate_id"], x["relationship_id"]))
        output.append({
            "setting_id": sid,
            "content": setting["content"],
            "source_id": setting["source_id"],
            "quote": setting["quote"],
            "decision_id": setting["decision_id"],
            "related": links,
        })
    return sorted(output, key=lambda x: x["setting_id"])


def main():
    parser = argparse.ArgumentParser(description="Approved-only worldbuilding dossiers")
    parser.add_argument("--setting-id")
    parser.add_argument("--query")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    try:
        if args.query is not None and not args.query.strip():
            raise ValueError("Empty query")
        result = build_dossiers(build_catalog(), effective("approved"))
        if args.setting_id:
            result = [x for x in result if x["setting_id"] == args.setting_id]
            if not result:
                raise ValueError("Approved setting not found")
        if args.query:
            q = args.query.casefold()
            result = [x for x in result if q in x["content"].casefold() or q in x["quote"].casefold()]
        data = ({"total": len(result), "linked": sum(len(x["related"]) for x in result)}
                if args.summary else {"total": len(result), "settings": result})
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
