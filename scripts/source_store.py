#!/usr/bin/env python3
"""Append-only UTF-8 source archive; Python standard library only."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / 'sources' / 'records'
PAYLOADS = ROOT / 'sources' / 'payloads'
ID_RE = re.compile(r'^SRC-(\d{6,})$')
MAX_BYTES = 5 * 1024 * 1024

class StoreError(Exception):
    pass

@contextlib.contextmanager
def locked():
    # Linux (GitHub Codespaces/Actions). Only serializes writes on this filesystem.
    import fcntl
    lock_path = ROOT / '.source-store.lock'
    with lock_path.open('a+b') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def records():
    for path in sorted(RECORDS.glob('SRC-*.json')):
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError) as exc:
            raise StoreError(f'Invalid metadata: {path}: {exc}') from exc
        yield path, record

def validate_record(path, record):
    source_id = record.get('source_id')
    if not isinstance(source_id, str) or not ID_RE.fullmatch(source_id):
        raise StoreError(f'Invalid source ID in {path}')
    if path.name != f'{source_id}.json':
        raise StoreError(f'Metadata filename mismatch: {path}')
    if record.get('schema_version') != 1 or record.get('encoding') != 'UTF-8':
        raise StoreError(f'Invalid schema or encoding: {path}')
    request_id = record.get('request_id')
    if not isinstance(request_id, str) or not (1 <= len(request_id) <= 128):
        raise StoreError(f'Invalid request ID: {path}')
    payload = PAYLOADS / f'{source_id}.txt'
    if record.get('payload_path') != f'sources/payloads/{source_id}.txt':
        raise StoreError(f'Unexpected payload path: {path}')
    if not payload.is_file():
        raise StoreError(f'Missing payload: {payload}')
    data = payload.read_bytes()
    try:
        data.decode('utf-8', errors='strict')
    except UnicodeDecodeError as exc:
        raise StoreError(f'Payload is not UTF-8: {payload}') from exc
    if record.get('sha256') != digest(data) or record.get('byte_length') != len(data):
        raise StoreError(f'Hash or byte length mismatch: {payload}')
    return data

def inspect_all():
    seen_ids = set()
    seen_requests = set()
    count = 0
    for path, record in records():
        validate_record(path, record)
        sid = record['source_id']
        rid = record['request_id']
        if sid in seen_ids or rid in seen_requests:
            raise StoreError(f'Duplicate source ID or request ID: {path}')
        seen_ids.add(sid)
        seen_requests.add(rid)
        count += 1
    expected_payloads = {f'{sid}.txt' for sid in seen_ids}
    existing_payloads = {p.name for p in PAYLOADS.glob('SRC-*.txt')}
    if expected_payloads != existing_payloads:
        raise StoreError(f'Orphan/untracked payloads: {sorted(expected_payloads ^ existing_payloads)}')
    return count

def write_exclusive(path, data):
    # O_EXCL ensures an existing archive file is never overwritten.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())

def save(input_path, request_id):
    if not (1 <= len(request_id) <= 128) or any(ord(c) < 32 for c in request_id):
        raise StoreError('Request ID must be 1â128 printable characters')
    data = Path(input_path).read_bytes()
    if len(data) > MAX_BYTES:
        raise StoreError(f'Input exceeds {MAX_BYTES} bytes')
    try:
        data.decode('utf-8', errors='strict')
    except UnicodeDecodeError as exc:
        raise StoreError('Input must be valid UTF-8; no automatic conversion') from exc
    with locked():
        inspect_all()  # refuse to append to a damaged archive
        highest = 0
        for _, rec in records():
            highest = max(highest, int(ID_RE.fullmatch(rec['source_id']).group(1)))
            if rec['request_id'] == request_id:
                if rec['sha256'] == digest(data) and rec['byte_length'] == len(data):
                    return {'status': 'already_saved', 'source_id': rec['source_id'], 'sha256': digest(data)}
                raise StoreError('Request ID already used with different content')
        source_id = f'SRC-{highest + 1:06d}'
        payload_path = PAYLOADS / f'{source_id}.txt'
        record_path = RECORDS / f'{source_id}.json'
        record = {
            'schema_version': 1,
            'source_id': source_id,
            'request_id': request_id,
            'payload_path': f'sources/payloads/{source_id}.txt',
            'encoding': 'UTF-8',
            'sha256': digest(data),
            'byte_length': len(data),
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        # If interrupted between these writes, verify fails closed. Git commits
        # must include both files together.
        write_exclusive(payload_path, data)
        write_exclusive(record_path, (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        validate_record(record_path, record)
        return {'status': 'saved', 'source_id': source_id, 'sha256': digest(data)}

def get_record(source_id):
    if not ID_RE.fullmatch(source_id):
        raise StoreError('Invalid source ID')
    path = RECORDS / f'{source_id}.json'
    if not path.is_file():
        raise StoreError(f'Source not found: {source_id}')
    rec = json.loads(path.read_text(encoding='utf-8'))
    return path, rec

def main():
    parser = argparse.ArgumentParser(description='Immutable source archive')
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('save', help='Save UTF-8 bytes from a file')
    s.add_argument('--file', required=True)
    s.add_argument('--request-id', required=True)
    r = sub.add_parser('read', help='Write original bytes to an output file or stdout')
    r.add_argument('source_id')
    r.add_argument('--output', help='Destination file (recommended for byte-exact reading)')
    v = sub.add_parser('verify', help='Verify all archived sources')
    v.add_argument('source_id', nargs='?')
    args = parser.parse_args()
    try:
        if args.command == 'save':
            print(json.dumps(save(args.file, args.request_id), ensure_ascii=False))
        elif args.command == 'read':
            path, rec = get_record(args.source_id)
            data = validate_record(path, rec)
            if args.output:
                out = Path(args.output)
                if out.exists():
                    raise StoreError('Output already exists; refusing to overwrite')
                write_exclusive(out, data)
                print(json.dumps({'source_id': args.source_id, 'output': str(out), 'sha256': digest(data)}))
            else:
                sys.stdout.buffer.write(data)
        elif args.command == 'verify':
            if args.source_id:
                path, rec = get_record(args.source_id)
                validate_record(path, rec)
                print(json.dumps({'status': 'verified', 'source_id': args.source_id}))
            else:
                print(json.dumps({'status': 'verified', 'count': inspect_all()}))
    except (StoreError, OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
