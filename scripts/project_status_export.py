#!/usr/bin/env python3
"""Export aggregate-only project status as a versioned JSON file.

Never exports manuscript, character names, plot titles, IDs, or review text.
This is safe to inspect in a public repository workflow, unlike story content.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

from project_dashboard import collect

ALLOWED_CANON = ("total", "approved", "rejected", "pending")
ALLOWED_PLOT = ("total", "approved", "rejected", "pending")
ALLOWED_WRITING = ("scenes", "not_started", "awaiting_approval",
                   "approved", "revision_pending", "approved_prose_scenes")
ALLOWED_DIAGNOSTICS = ("plot_findings", "prose_findings")


def aggregate(dashboard):
    def pick(section, keys):
        source = dashboard[section]
        return {k: source[k] for k in keys}
    return {
        "schema_version": 1,
        "kind": "aggregate_project_status",
        "canon": pick("canon", ALLOWED_CANON),
        "plot_cards": pick("plot_cards", ALLOWED_PLOT),
        "writing": pick("writing", ALLOWED_WRITING),
        "review_inbox": {
            "total": dashboard["review_inbox"]["total"],
            "by_category": dict(dashboard["review_inbox"]["by_category"]),
        },
        "diagnostics": pick("diagnostics", ALLOWED_DIAGNOSTICS),
        "contains_story_text": False,
        "contains_identifiers": False,
        "read_only": True,
    }


def save(payload, destination):
    path = Path(destination)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("Unsafe destination")
    if path.exists():
        raise ValueError("Destination already exists; refusing overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    # Exclusive create prevents accidental overwrite or following a final symlink.
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as out:
        out.write(data)
    return {"path": str(path), "bytes": len(data), "schema_version": payload["schema_version"]}


def main():
    parser = argparse.ArgumentParser(description="Export only non-sensitive project counts")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(save(aggregate(collect()), args.output), ensure_ascii=False))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
