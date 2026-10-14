#!/usr/bin/env python3
"""Read-only approved canon index built from verified immutable records."""
import argparse
import json
import sys
from candidate_store import all_records
from decision_store import all_decisions, verify_all

KINDS = ("character", "event", "dialogue", "setting", "foreshadowing", "other")


def build_catalog():
    verify_all()
    approved = {d["candidate_id"]: d for _, d in all_decisions() if d["decision"] == "approved"}
    entries = []
    for _, candidate in all_records():
        decision = approved.get(candidate["candidate_id"])
        if decision is None:
            continue
        entries.append({
            "candidate_id": candidate["candidate_id"],
            "kind": candidate["kind"],
            "content": candidate["content"],
            "source_id": candidate["evidence"]["source_id"],
            "quote": candidate["evidence"]["quote"],
            "start": candidate["evidence"]["start"],
            "end": candidate["evidence"]["end"],
            "decision_id": decision["decision_id"],
            "approved_at": decision["created_at"],
        })
    return entries


def search(entries, kind=None, query=None, source_id=None):
    if kind is not None and kind not in KINDS:
        raise ValueError("Unknown kind")
    if query is not None and not query.strip():
        raise ValueError("Empty search query")
    return [
        entry for entry in entries
        if (kind is None or entry["kind"] == kind)
        and (source_id is None or entry["source_id"] == source_id)
        and (query is None or query.casefold() in (entry["content"] + "\n" + entry["quote"]).casefold())
    ]


def main():
    parser = argparse.ArgumentParser(description="Read-only approved novel settings catalog")
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--query")
    parser.add_argument("--source-id")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    try:
        entries = search(build_catalog(), args.kind, args.query, args.source_id)
        if args.summary:
            result = {"total": len(entries), "by_kind": {k: sum(e["kind"] == k for e in entries) for k in KINDS}}
        else:
            result = {"total": len(entries), "entries": entries}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
