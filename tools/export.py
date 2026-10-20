#!/usr/bin/env python3
"""Export a training run to ONNX (fp32 + int8): tools/export.py runs/bert-tiny [--out models/onnx/bert-tiny]"""

import argparse
from pathlib import Path

import _path  # noqa: F401

from memo_extract.export import export
from memo_extract.training import load


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--out")
    ap.add_argument("--no-quantize", action="store_true")
    args = ap.parse_args()

    out = args.out or f"models/onnx/{Path(args.run).name}"
    model, tokenizer, meta = load(args.run)
    sizes = export(model, out, tokenizer, meta, quantize=not args.no_quantize)
    for name, size in sizes.items():
        print(f"{out}/{name}: {size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
