#!/usr/bin/env python3
"""Check memo JSONL files against docs/labeling.md. Prints every problem and exits 1 if there are any."""

import argparse
import json

import _path  # noqa: F401

from memo_extract.constants import MAX_MEMO_CHARS
from memo_extract.records import parse


def validate(path, allow_drop, texts_only=False):
    errors, count, ids, texts = [], 0, set(), set()
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue

            where = f"{path}:{line_no}"
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"{where}: invalid JSON ({e})")
                continue

            memo_id = record.get("id")
            where = f"{where} {memo_id}"
            if memo_id in ids:
                errors.append(f"{where}: duplicate memo id")
            ids.add(memo_id)
            count += 1
            if record.get("drop"):
                if not allow_drop:
                    errors.append(f"{where}: drop records are only allowed in adjudication files")
                elif not record.get("reason"):
                    errors.append(f"{where}: drop needs a reason")
                continue

            if texts_only:
                errors += [f"{where}: {e}" for e in check_text(record, texts)]
                continue

            _, record_errors = parse(record)
            errors += [f"{where}: {e}" for e in record_errors]

    return count, errors


def check_text(record, seen):
    """Writer output: just {"id", "text"}, each text distinct and within the length limit."""
    text = record.get("text")
    if set(record) != {"id", "text"}:
        return ["text files hold only id and text"]
    if not isinstance(text, str) or not text.strip():
        return ["missing text"]
    if len(text) > MAX_MEMO_CHARS:
        return [f"text longer than {MAX_MEMO_CHARS} chars"]
    if text.casefold() in seen:
        return ["duplicate text"]
    seen.add(text.casefold())
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--allow-drop", action="store_true")
    ap.add_argument("--texts-only", action="store_true", help="check writer output (id + text, no labels)")
    args = ap.parse_args()

    total, all_errors = 0, []
    for path in args.files:
        count, errors = validate(path, args.allow_drop, args.texts_only)
        total += count
        all_errors += errors

    for e in all_errors:
        print(e)
    print(f"{len(all_errors)} errors in {total} records" if all_errors else f"OK {total} records")
    raise SystemExit(1 if all_errors else 0)


if __name__ == "__main__":
    main()
