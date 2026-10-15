#!/usr/bin/env python3
"""Fixed Japanese aliases for safe, read-only project queries."""
import argparse
import json
import sys
from project_query import query, snapshot

ALIASES = {
    "制作状況": "dashboard",
    "作品の状況": "dashboard",
    "確認待ち": "inbox",
    "確認事項": "inbox",
    "執筆進捗": "progress",
    "本文の進捗": "progress",
    "承認済み原稿": "manuscript",
    "原稿を表示": "manuscript",
}


def resolve(message):
    if not isinstance(message, str) or not message.strip() or len(message) > 200:
        raise ValueError("A short explicit query is required")
    command = ALIASES.get(message.strip())
    if command is None:
        raise ValueError("Unknown or ambiguous request; ask user to clarify")
    return command


def execute(message, data):
    command = resolve(message)
    return query(command, data)


def main():
    parser = argparse.ArgumentParser(description="Read-only Japanese project queries")
    parser.add_argument("message", choices=sorted(ALIASES))
    args = parser.parse_args()
    try:
        print(json.dumps(execute(args.message, snapshot()), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
