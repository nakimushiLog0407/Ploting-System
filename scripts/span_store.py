
#!/usr/bin/env python3
"""Validate provenance spans against immutable Stage 1 sources."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r'^SRC-\d{6,}$')


def extract(source_id, start, end):
    if not ID.fullmatch(source_id):
        raise ValueError('Invalid source ID')

    record_path = (
        ROOT / 'sources' / 'records' / (source_id + '.json')
    )
    record = json.loads(
        record_path.read_text(encoding='utf-8')
    )

    if (
        record.get('source_id') != source_id
        or record.get('payload_path')
        != f'sources/payloads/{source_id}.txt'
    ):
        raise ValueError('Source metadata mismatch')

    payload = (
        ROOT / 'sources' / 'payloads' / (source_id + '.txt')
    ).read_bytes()

    if (
        record.get('sha256')
        != hashlib.sha256(payload).hexdigest()
        or record.get('byte_length') != len(payload)
    ):
        raise ValueError('Source integrity verification failed')

    text = payload.decode('utf-8', errors='strict')

    if not (0 <= start < end <= len(text)):
        raise ValueError(
            f'Invalid character span: {start}:{end}; '
            f'source length={len(text)}'
        )

    quote = text[start:end]

    return {
        'schema_version': 1,
        'source_id': source_id,
        'source_sha256': record['sha256'],
        'unit': 'unicode_codepoint',
        'start': start,
        'end': end,
        'quote': quote,
        'quote_sha256': hashlib.sha256(
            quote.encode('utf-8')
        ).hexdigest(),
        'status': 'candidate',
    }


def verify(item):
    if (
        item.get('schema_version') != 1
        or item.get('unit') != 'unicode_codepoint'
        or item.get('status') != 'candidate'
    ):
        raise ValueError('Invalid span schema')

    if (
        type(item.get('start')) is not int
        or type(item.get('end')) is not int
    ):
        raise ValueError('Offsets must be integers')

    actual = extract(
        item['source_id'],
        item['start'],
        item['end'],
    )

    if item != actual:
        raise ValueError(
            'Span record does not match original source'
        )

    return actual


def main():
    parser = argparse.ArgumentParser(
        description='Stage 2 provenance span tool'
    )
    sub = parser.add_subparsers(
        dest='cmd',
        required=True,
    )

    p = sub.add_parser('extract')
    p.add_argument('source_id')
    p.add_argument('start', type=int)
    p.add_argument('end', type=int)

    p = sub.add_parser('verify')
    p.add_argument('file', type=Path)

    args = parser.parse_args()

    try:
        if args.cmd == 'extract':
            result = extract(
                args.source_id,
                args.start,
                args.end,
            )
        else:
            result = verify(
                json.loads(
                    args.file.read_text(encoding='utf-8')
                )
            )

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )

    except (
        ValueError,
        KeyError,
        OSError,
        UnicodeError,
        TypeError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
