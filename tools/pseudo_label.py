#!/usr/bin/env python3
"""Label unlabelled memo texts with a trained teacher, keeping only records that pass validation.

tools/pseudo_label.py runs/minilm-l6 --texts data/raw/u*.txt.jsonl --out data/silver.jsonl
"""

import argparse
import json
from collections import Counter

import _path  # noqa: F401
import torch

from memo_extract.data import read_jsonl
from memo_extract.decode import predict
from memo_extract.records import parse
from memo_extract.training import load


def to_record(memo_id, memo):
    spans = []
    for span in memo.spans:
        raw = {"id": span.id, "type": span.type, "text": span.text, "start": span.start, **span.attrs}
        raw |= {k: v for k in ("owner", "anchor", "same_as") if (v := getattr(span, k))}
        spans.append(raw)
    return {"id": memo_id, "text": memo.text, "spans": spans}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("teacher")
    ap.add_argument("--texts", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--threads", type=int, default=16)
    args = ap.parse_args()

    torch.set_num_threads(args.threads)
    model, tokenizer, meta = load(args.teacher)
    rows = read_jsonl(args.texts)
    memos = predict(model, tokenizer, [r["text"] for r in rows], meta["config"]["max_len"])

    kept, rejected = 0, Counter()
    with open(args.out, "w", encoding="utf-8") as f:
        for row, memo in zip(rows, memos):
            record = to_record(row["id"], memo)
            _, errors = parse(record)
            if errors:
                rejected[errors[0].split(":")[-1].strip()[:60]] += 1
                continue
            f.write(json.dumps({**record, "source": "silver"}, ensure_ascii=False) + "\n")
            kept += 1
    print(f"{args.out}: kept {kept} of {len(rows)}; rejected {sum(rejected.values())}: {rejected.most_common(5)}")


if __name__ == "__main__":
    main()
