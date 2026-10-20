#!/usr/bin/env python3
"""Merge generated, blind-relabelled and adjudicated files into one dataset file per split.

A memo is kept when both annotators agree, or when the adjudicator wrote a record for it. With
--allow-single, briefs that were never relabelled contribute their generator labels as-is.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import _path  # noqa: F401

from memo_extract.agreement import diff_kinds, normalise
from memo_extract.records import parse


def load(path):
    if not path.exists():
        return None
    return {r["id"]: r for r in map(json.loads, filter(str.strip, path.open(encoding="utf-8")))}


def agree(a, b):
    (memo_a, _), (memo_b, _) = parse(a), parse(b)
    return memo_a is not None and memo_b is not None and not diff_kinds(normalise(memo_a), normalise(memo_b))


def merge_brief(raw, brief, allow_single, stats, first="a", second="b"):
    gen = load(raw / f"{brief['id']}.{first}.jsonl")
    if gen is None:
        stats["missing_brief"] += 1
        return []

    lab = load(raw / f"{brief['id']}.{second}.jsonl")
    adj = load(raw / f"{brief['id']}.adj.jsonl") or {}
    if lab is None and not allow_single:
        stats["unreviewed_brief"] += 1
        return []

    kept = []
    for memo_id, record in gen.items():
        if memo_id in adj:
            if adj[memo_id].get("drop"):
                stats["dropped"] += 1
                continue
            record, source = adj[memo_id], "adjudicated"
        elif lab is None:
            source = "single"
        elif memo_id in lab and agree(record, lab[memo_id]):
            source = "agreed"
        else:
            stats["unresolved"] += 1
            continue

        if parse(record)[1]:
            stats["invalid"] += 1
            continue
        stats[source] += 1
        kept.append({**record, "brief": brief["id"], "style": brief["style"], "source": source})
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--briefs", nargs="+", required=True)
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data")
    ap.add_argument("--allow-single", action="store_true")
    ap.add_argument("--first", default="a", help="suffix of the first annotation file (pilot used 'gen')")
    ap.add_argument("--second", default="b", help="suffix of the second annotation file (pilot used 'lab')")
    args = ap.parse_args()

    by_split, stats = defaultdict(list), Counter()
    for briefs_file in args.briefs:
        for brief in json.loads(Path(briefs_file).read_text(encoding="utf-8")):
            by_split[brief["split"]] += merge_brief(Path(args.raw), brief, args.allow_single, stats, args.first, args.second)

    for split, records in by_split.items():
        path = Path(args.out) / f"{split}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"{path}: {len(records)} memos")
    print(json.dumps(dict(stats)))


if __name__ == "__main__":
    main()
