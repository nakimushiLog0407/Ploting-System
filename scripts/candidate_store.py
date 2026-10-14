#!/usr/bin/env python3
"""Append-only candidate records. Candidates never become canon automatically."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "candidates" / "records"
SRC_RE = re.compile(r"^SRC-\d{6,}$")
CAND_RE = re.compile(r"^CAND-\d{6,}$")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_span(source_id, start, end):
    if not SRC_RE.fullmatch(source_id):
        raise ValueError("Invalid source ID")
    record = json.loads((ROOT / "sources" / "records" / (source_id + ".json")).read_text(encoding="utf-8"))
    data = (ROOT / "sources" / "payloads" / (source_id + ".txt")).read_bytes()
    if (record.get("source_id") != source_id
            or record.get("payload_path") != f"sources/payloads/{source_id}.txt"
            or record.get("encoding") != "UTF-8"
            or record.get("sha256") != sha(data)
            or record.get("byte_length") != len(data)):
        raise ValueError("Source integrity verification failed")
    text = data.decode("utf-8", errors="strict")
    if type(start) is not int or type(end) is not int or not (0 <= start < end <= len(text)):
        raise ValueError("Invalid source span")
    quote = text[start:end]
    return {
        "source_id": source_id,
        "source_sha256": sha(data),
        "unit": "unicode_codepoint",
        "start": start,
        "end": end,
        "quote": quote,
        "quote_sha256": sha(quote.encode("utf-8")),
    }


def validate(item, path=None):
    if not isinstance(item, dict) or set(item) != {
        "schema_version", "candidate_id", "request_id", "kind", "content",
        "evidence", "status", "created_at",
    }:
        raise ValueError("Invalid candidate schema")
    cid = item["candidate_id"]
    if not isinstance(cid, str) or not CAND_RE.fullmatch(cid):
        raise ValueError("Invalid candidate ID")
    if path is not None and path.name != cid + ".json":
        raise ValueError("Candidate filename mismatch")
    if item["schema_version"] != 1 or item["status"] != "candidate":
        raise ValueError("Candidate must remain unapproved")
    if (not isinstance(item["request_id"], str)
            or not 1 <= len(item["request_id"]) <= 128
            or any(ord(c) < 32 for c in item["request_id"])):
        raise ValueError("Invalid request ID")
    if item["kind"] not in ("character", "event", "dialogue", "setting", "foreshadowing", "other"):
        raise ValueError("Invalid candidate kind")
    if not isinstance(item["content"], str) or not item["content"].strip() or len(item["content"]) > 20000:
        raise ValueError("Invalid candidate content")
    if not isinstance(item["created_at"], str) or not item["created_at"]:
        raise ValueError("Invalid timestamp")
    evidence = item["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != {
        "source_id", "source_sha256", "unit", "start", "end", "quote", "quote_sha256"
    }:
        raise ValueError("Invalid evidence schema")
    expected = source_span(evidence["source_id"], evidence["start"], evidence["end"])
    if evidence != expected:
        raise ValueError("Evidence does not match original source")
    return item


def all_records():
    for path in sorted(CANDIDATES.glob("CAND-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        validate(item, path)
        yield path, item


def verify_all():
    ids, requests = set(), set()
    count = 0
    for _, item in all_records():
        if item["candidate_id"] in ids or item["request_id"] in requests:
            raise ValueError("Duplicate candidate or request ID")
        ids.add(item["candidate_id"])
        requests.add(item["request_id"])
        count += 1
    return count


@contextlib.contextmanager
def locked():
    lock_path = ROOT / ".candidate-store.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def save(request_id, kind, content, source_id, start, end):
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(ord(c) < 32 for c in request_id):
        raise ValueError("Invalid request ID")
    if kind not in ("character", "event", "dialogue", "setting", "foreshadowing", "other"):
        raise ValueError("Invalid kind")
    if not content or not content.strip() or len(content) > 20000:
        raise ValueError("Invalid content")
    with locked():
        verify_all()
        evidence = source_span(source_id, start, end)
        for _, existing in all_records():
            if existing["request_id"] == request_id:
                if (existing["kind"] == kind and existing["content"] == content
                        and existing["evidence"] == evidence):
                    return {"status": "already_saved", "candidate_id": existing["candidate_id"]}
                raise ValueError("Request ID already used with different candidate")
        highest = max((int(p.stem.split("-")[1]) for p in CANDIDATES.glob("CAND-*.json")), default=0)
        cid = f"CAND-{highest + 1:06d}"
        item = {
            "schema_version": 1,
            "candidate_id": cid,
            "request_id": request_id,
            "kind": kind,
            "content": content,
            "evidence": evidence,
            "status": "candidate",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        validate(item)
        CANDIDATES.mkdir(parents=True, exist_ok=True)
        dest = CANDIDATES / (cid + ".json")
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write((json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        return {"status": "saved", "candidate_id": cid}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("save")
    p.add_argument("--request-id", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--content", required=True)
    p.add_argument("--source-id", required=True)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--end", type=int, required=True)
    sub.add_parser("verify")
    args = parser.parse_args()
    try:
        if args.cmd == "save":
            result = save(args.request_id, args.kind, args.content, args.source_id, args.start, args.end)
        else:
            result = {"status": "verified", "count": verify_all()}
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
