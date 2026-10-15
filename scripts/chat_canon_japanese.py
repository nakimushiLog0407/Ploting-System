#!/usr/bin/env python3
"""Explicit Japanese aliases for read-only, approved-only canon lookups.

No fuzzy matching: an ambiguous or write-like request is rejected.
"""
import argparse
import json
import sys
from chat_canon_page import page
from chat_canon_context import build
from candidate_store import all_records
from decision_store import all_decisions, verify_all
from canon_catalog import build_catalog
from canon_revision import load as load_revisions

ALIASES = {
    "正式設定": None,
    "承認済み設定": None,
    "人物設定": "character",
    "登場人物の設定": "character",
    "出来事の設定": "event",
    "台詞の設定": "dialogue",
    "世界設定": "setting",
    "伏線の設定": "foreshadowing",
    "その他の設定": "other",
}

def resolve(message):
    if not isinstance(message, str) or message.strip() not in ALIASES:
        raise ValueError("Unsupported or ambiguous query: specify an exact approved-canon alias")
    return ALIASES[message.strip()]

def lookup(message, context, limit=20, offset=0):
    kind = resolve(message)
    result = page(context, group="approved", kind=kind, limit=limit, offset=offset)
    result["requested_alias"] = message.strip()
    return result

def main():
    parser = argparse.ArgumentParser(description="Read only approved novel settings in Japanese")
    parser.add_argument("message", choices=sorted(ALIASES))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    try:
        verify_all()
        canon = build_catalog()
        current, history = load_revisions(canon)
        context = build([item for _, item in all_records()],
                        [item for _, item in all_decisions()], canon, current, history)
        print(json.dumps(lookup(args.message, context, args.limit, args.offset),
                         ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
