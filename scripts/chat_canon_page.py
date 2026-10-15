#!/usr/bin/env python3
"""Paginated, explicitly separated canon and idea review for ChatGPT.

Read-only. The default is approved canon, never pending or rejected material.
"""
import argparse
import json
import sys
from candidate_store import all_records
from decision_store import all_decisions, verify_all
from canon_catalog import build_catalog
from canon_revision import load as load_revisions
from chat_canon_context import build

GROUPS = {"approved": "approved_canon", "pending": "pending_not_canon",
          "rejected": "rejected_not_canon", "pending_revisions": "pending_revisions_not_canon"}
KINDS = ("character", "event", "dialogue", "setting", "foreshadowing", "other")


def page(context, group="approved", kind=None, limit=20, offset=0):
    if group not in GROUPS:
        raise ValueError("Unknown group")
    if kind is not None and kind not in KINDS:
        raise ValueError("Unknown kind")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be nonnegative")
    key = GROUPS[group]
    entries = context[key]
    if kind is not None:
        if group == "pending_revisions":
            raise ValueError("Kind filter is not available for revision proposals")
        entries = [entry for entry in entries if entry["kind"] == kind]
    items = entries[offset:offset + limit]
    return {"schema_version": 1, "group": group, "kind": kind,
            "total": len(entries), "offset": offset, "limit": limit,
            "has_more": offset + limit < len(entries), "items": items,
            "is_approved_canon": group == "approved",
            "read_only": True, "approval_performed": False}


def main():
    parser = argparse.ArgumentParser(description="Page through explicitly separated novel settings")
    parser.add_argument("--group", choices=tuple(GROUPS), default="approved")
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    try:
        verify_all()
        canon = build_catalog()
        current, history = load_revisions(canon)
        context = build([item for _, item in all_records()],
                        [item for _, item in all_decisions()], canon, current, history)
        print(json.dumps(page(context, args.group, args.kind, args.limit, args.offset),
                         ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
