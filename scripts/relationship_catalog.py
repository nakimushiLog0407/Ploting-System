#!/usr/bin/env python3
"""Read-only, explicitly reviewed relationships between approved candidates."""
import argparse
import json
from pathlib import Path
import re
import sys

from canon_catalog import build_catalog
from decision_store import verify_all

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "relationships" / "records"
REL_ID = re.compile(r"^REL-\d{6,}$")
CAND_ID = re.compile(r"^CAND-\d{6,}$")
TYPES = ("spoken_by", "occurs_in", "involves", "related_to", "precedes", "foreshadows")
STATUSES = ("proposed", "approved", "rejected")


def validate(record, path=None):
    required = {"schema_version", "relationship_id", "request_id", "from_candidate_id",
                "to_candidate_id", "relation", "status", "evidence", "created_at",
                "reviewed_by", "reviewed_at"}
    if not isinstance(record, dict) or set(record) != required:
        raise ValueError("Invalid relationship schema")
    rid = record["relationship_id"]
    if not isinstance(rid, str) or not REL_ID.fullmatch(rid) or (path is not None and path.name != rid + ".json"):
        raise ValueError("Invalid relationship ID")
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise ValueError("Invalid schema version")
    for field in ("request_id", "created_at"):
        value = record[field]
        if not isinstance(value, str) or not value or len(value) > 128 or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid " + field)
    a, b = record["from_candidate_id"], record["to_candidate_id"]
    if not isinstance(a, str) or not isinstance(b, str) or not CAND_ID.fullmatch(a) or not CAND_ID.fullmatch(b) or a == b:
        raise ValueError("Invalid relationship endpoints")
    if record["relation"] not in TYPES or record["status"] not in STATUSES:
        raise ValueError("Invalid relation or status")
    if not isinstance(record["evidence"], str) or len(record["evidence"]) > 20000:
        raise ValueError("Invalid evidence")
    if record["status"] == "proposed":
        if record["reviewed_by"] is not None or record["reviewed_at"] is not None:
            raise ValueError("Proposal cannot have a reviewer")
    else:
        if record["reviewed_by"] != "user" or not isinstance(record["reviewed_at"], str) or not record["reviewed_at"]:
            raise ValueError("Explicit user review required")
    return record


def all_relationships():
    for path in sorted(RECORDS.glob("REL-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        yield validate(item, path)


def verify_relationships():
    verify_all()
    catalog = {e["candidate_id"]: e for e in build_catalog()}
    ids, requests, edges = set(), set(), set()
    count = 0
    for item in all_relationships():
        if item["relationship_id"] in ids or item["request_id"] in requests:
            raise ValueError("Duplicate relationship ID or request")
        ids.add(item["relationship_id"])
        requests.add(item["request_id"])
        edge = (item["from_candidate_id"], item["to_candidate_id"], item["relation"])
        if edge in edges:
            raise ValueError("Duplicate relationship")
        edges.add(edge)
        if item["from_candidate_id"] not in catalog or item["to_candidate_id"] not in catalog:
            raise ValueError("Relationships require approved candidates")
        if item["relation"] == "spoken_by" and (
            catalog[item["from_candidate_id"]]["kind"] != "dialogue"
            or catalog[item["to_candidate_id"]]["kind"] != "character"
        ):
            raise ValueError("spoken_by requires dialogue -> character")
        if item["relation"] == "occurs_in" and catalog[item["to_candidate_id"]]["kind"] != "event":
            raise ValueError("occurs_in requires event target")
        count += 1
    return count


def browse(candidate_id=None, status="approved", relation=None):
    verify_relationships()
    if candidate_id is not None and not CAND_ID.fullmatch(candidate_id):
        raise ValueError("Invalid candidate ID")
    if status not in STATUSES + ("all",):
        raise ValueError("Invalid status")
    if relation is not None and relation not in TYPES:
        raise ValueError("Invalid relation")
    return [r for r in all_relationships()
            if (status == "all" or r["status"] == status)
            and (relation is None or r["relation"] == relation)
            and (candidate_id is None or candidate_id in (r["from_candidate_id"], r["to_candidate_id"]))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id")
    parser.add_argument("--status", choices=STATUSES + ("all",), default="approved")
    parser.add_argument("--relation", choices=TYPES)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        result = {"verified": verify_relationships()} if args.verify else {"relationships": browse(args.candidate_id, args.status, args.relation)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
