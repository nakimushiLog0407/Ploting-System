#!/usr/bin/env python3
"""Read-only effective canon: original evidence plus explicitly approved revision overlay.

All downstream views must opt into this function to see approved revisions.
The original source quote and provenance remain unchanged.
"""
import argparse
import json
import sys
from canon_catalog import build_catalog, search, KINDS
from canon_revision import load


def effective_entries(entries):
    current, history = load(entries)
    latest = {}
    for item in history:
        if item["status"] == "approved":
            latest[item["candidate_id"]] = item["revision_id"]
    return [{**item, "content": current[item["candidate_id"]],
             "original_content": item["content"],
             "effective_revision_id": latest.get(item["candidate_id"])}
            for item in entries]


def main():
    p = argparse.ArgumentParser(description="Read-only approved revision-aware canon catalog")
    p.add_argument("--kind", choices=KINDS)
    p.add_argument("--query")
    p.add_argument("--source-id")
    p.add_argument("--summary", action="store_true")
    args = p.parse_args()
    try:
        entries = search(effective_entries(build_catalog()), args.kind, args.query, args.source_id)
        result = ({"total": len(entries), "revised": sum(x["effective_revision_id"] is not None for x in entries)}
                  if args.summary else {"total": len(entries), "entries": entries})
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
