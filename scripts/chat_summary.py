#!/usr/bin/env python3
"""Bounded read-only summaries for use through the existing GitHub connector.

This module never calls an AI API, changes files, or silently truncates results.
"""
import argparse
import json
import sys
from chat_query import resolve
from project_query import query, snapshot

SUPPORTED = ("dashboard", "inbox", "progress")
MAX_ITEMS = 100


def compact(command, data, limit=20, offset=0):
    if command not in SUPPORTED:
        raise ValueError("Compact summaries only support dashboard, inbox and progress")
    if type(limit) is not int or not 1 <= limit <= MAX_ITEMS:
        raise ValueError("limit must be an integer from 1 to 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a nonnegative integer")
    full = query(command, data)
    body = full["data"]
    if command == "dashboard":
        return {"interface_version": 1, "command": command, "data": body,
                "read_only": True, "complete": True}
    if command == "inbox":
        items = body["items"]
        return {"interface_version": 1, "command": command,
                "total": len(items), "by_category": body["by_category"],
                "items": items[offset:offset + limit],
                "offset": offset, "limit": limit,
                "has_more": offset + limit < len(items),
                "read_only": True, "complete": offset == 0 and len(items) <= limit}
    # Keep the full progress summary and expose only a bounded chapter slice.
    chapters = body["chapters"]
    return {"interface_version": 1, "command": command,
            "summary": body["summary"],
            "unplaced_scene_ids": body["unplaced_scene_ids"],
            "chapters": chapters[offset:offset + limit],
            "total_chapters": len(chapters), "offset": offset, "limit": limit,
            "has_more": offset + limit < len(chapters),
            "read_only": True, "complete": offset == 0 and len(chapters) <= limit}


def main():
    parser = argparse.ArgumentParser(description="Bounded project summaries")
    parser.add_argument("message", help="制作状況 / 確認待ち / 執筆進捗")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    try:
        command = resolve(args.message)
        print(json.dumps(compact(command, snapshot(), args.limit, args.offset),
                         ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
