#!/usr/bin/env python3
"""Train a MemoTagger: tools/train.py --backbone models/backbones/X --train data/train.jsonl --dev data/dev.jsonl --out runs/X"""

import argparse
from dataclasses import fields

import _path  # noqa: F401

from memo_extract.data import load_memos
from memo_extract.training import TrainConfig, train


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", nargs="+", required=True)
    ap.add_argument("--dev", nargs="+", required=True)
    for f in fields(TrainConfig):
        ap.add_argument(
            f"--{f.name.replace('_', '-')}",
            type=f.type if f.type in (int, float, str) else str,
            default=f.default,
            required=f.name in ("backbone", "out"),
        )
    args = ap.parse_args()

    train_memos, train_rejected = load_memos(args.train)
    dev_memos, dev_rejected = load_memos(args.dev)
    print(f"train {len(train_memos)} (rejected {len(train_rejected)}), dev {len(dev_memos)} (rejected {len(dev_rejected)})")
    cfg = TrainConfig(**{f.name: getattr(args, f.name) for f in fields(TrainConfig)})
    best = train(cfg, train_memos, dev_memos)
    print(f"best strict dev F1 {best:.4f}")


if __name__ == "__main__":
    main()
