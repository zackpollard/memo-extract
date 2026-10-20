"""Load labelled memo JSONL files."""

import json

from .records import parse


def read_jsonl(paths):
    """Every record in the given JSONL files, in file order, skipping blank lines."""
    records = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            records.extend(json.loads(line) for line in f if line.strip())
    return records


def load_memos(paths):
    """Parsed memos from JSONL files, plus the ids of records that failed validation."""
    memos, rejected = [], []
    for record in read_jsonl(paths):
        memo, errors = parse(record)
        if errors:
            rejected.append(record.get("id"))
            continue
        memos.append(memo)
    return memos, rejected
