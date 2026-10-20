#!/usr/bin/env python3
"""Compare two labellings of the same memos. Prints a summary line, then every disagreement with both versions."""

import argparse
import json
from collections import Counter

import _path  # noqa: F401

from memo_extract.agreement import describe, diff_kinds, normalise
from memo_extract.records import parse


def load(path):
    return {r["id"]: r for r in map(json.loads, filter(str.strip, open(path, encoding="utf-8")))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first")
    ap.add_argument("second")
    args = ap.parse_args()

    first, second = load(args.first), load(args.second)
    agreed, disagreements, kinds = 0, [], Counter()
    for memo_id, rec_a in first.items():
        rec_b = second.get(memo_id)
        if rec_b is None or rec_b["text"] != rec_a["text"]:
            disagreements.append({"id": memo_id, "text": rec_a["text"], "diffs": ["missing or changed text in second file"]})
            kinds["text"] += 1
            continue

        (memo_a, _), (memo_b, _) = parse(rec_a), parse(rec_b)
        if memo_a is None or memo_b is None:
            disagreements.append({"id": memo_id, "text": rec_a["text"], "diffs": ["invalid record, run validate.py"]})
            kinds["invalid"] += 1
            continue

        diffs = diff_kinds(normalise(memo_a), normalise(memo_b))
        if not diffs:
            agreed += 1
            continue

        kinds.update(diffs)
        disagreements.append({"id": memo_id, "text": rec_a["text"], "diffs": diffs, "first": describe(memo_a), "second": describe(memo_b)})

    print(json.dumps({"agreed": agreed, "disagreed": len(disagreements), "kinds": dict(kinds.most_common())}))
    for d in disagreements:
        print(json.dumps(d, ensure_ascii=False))


if __name__ == "__main__":
    main()
