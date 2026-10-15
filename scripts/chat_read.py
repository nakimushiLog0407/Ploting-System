#!/usr/bin/env python3
"""Unified explicit Japanese read-only entry point for project summaries and canon.

No API calls, file mutations, or fuzzy command interpretation.
"""
import argparse
import json
import sys

from chat_query import resolve as resolve_project
from chat_canon_japanese import ALIASES as CANON_ALIASES, lookup as lookup_canon
from chat_summary import compact
from project_query import snapshot
from chat_canon_context import build as build_canon_context
from candidate_store import all_records
from decision_store import all_decisions, verify_all
from canon_catalog import build_catalog
from canon_revision import load as load_revisions

SUMMARY_COMMANDS = ("dashboard", "inbox", "progress")


def route(message):
    if not isinstance(message, str) or not message.strip():
        raise ValueError("An explicit Japanese query is required")
    name = message.strip()
    if name in CANON_ALIASES:
        return "canon"
    try:
        command = resolve_project(name)
    except ValueError:
        raise ValueError("Unknown or ambiguous command; no action performed") from None
    if command not in SUMMARY_COMMANDS:
        raise ValueError("Manuscript is not supported by this bounded entry point")
    return command


def execute(message, *, limit=20, offset=0, project_data=None, canon_context=None):
    command = route(message)
    if command == "canon":
        if canon_context is None:
            verify_all()
            canon = build_catalog()
            current, history = load_revisions(canon)
            canon_context = build_canon_context(
                [record for _, record in all_records()],
                [record for _, record in all_decisions()],
                canon, current, history)
        result = lookup_canon(message, canon_context, limit, offset)
    else:
        result = compact(command, snapshot() if project_data is None else project_data,
                         limit, offset)
    return {"interface_version": 1, "requested_command": message.strip(),
            "route": command, "result": result, "read_only": True,
            "approval_performed": False}


def main():
    parser = argparse.ArgumentParser(description="Unified Japanese read-only novel project queries")
    parser.add_argument("message")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    try:
        print(json.dumps(execute(args.message, limit=args.limit, offset=args.offset),
                         ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
