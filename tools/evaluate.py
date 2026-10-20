#!/usr/bin/env python3
"""Evaluate a model on a labelled set and write metrics.json next to it (the playground shows it).

tools/evaluate.py runs/bert-tiny --data data/test.jsonl [--kind torch|onnx-int8|onnx-fp32]
"""

import argparse
import json
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import _path  # noqa: F401
import torch
from transformers import AutoTokenizer

from memo_extract.data import load_memos, read_jsonl
from memo_extract.decode import predict
from memo_extract.evaluate import score, score_suggestions
from memo_extract.export import OnnxTagger
from memo_extract.training import load

TODAY = date(2026, 10, 19)


def load_model(path, kind):
    if kind == "torch":
        model, tokenizer, meta = load(path)
        return model, tokenizer, meta["config"]["max_len"]
    meta = json.loads((Path(path) / "meta.json").read_text())
    return OnnxTagger(path, kind.removeprefix("onnx-")), AutoTokenizer.from_pretrained(Path(path) / "tokenizer"), meta["config"]["max_len"]


def latency_ms(model, tokenizer, texts, max_len):
    """Median single-memo latency on one thread, the closest proxy here for one phone core."""
    torch.set_num_threads(1)
    timings = []
    for text in texts:
        started = time.perf_counter()
        predict(model, tokenizer, [text], max_len)
        timings.append((time.perf_counter() - started) * 1000)
    return sorted(timings)[len(timings) // 2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--kind", default="torch")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--write", action="store_true", help="write metrics.json into the model directory")
    args = ap.parse_args()

    torch.set_num_threads(args.threads)
    memos, rejected = load_memos(args.data)
    records = {r["id"]: r for r in read_jsonl(args.data)}
    model, tokenizer, max_len = load_model(args.model, args.kind)
    preds = predict(model, tokenizer, [m.text for m in memos], max_len)

    labels = score(memos, preds)
    suggestions = score_suggestions(memos, preds, TODAY)
    by_style = defaultdict(lambda: ([], []))
    for gold, pred in zip(memos, preds):
        golds, predicted = by_style[records[gold.id].get("style", "?")]
        golds.append(gold)
        predicted.append(pred)
    styles = {style: round(score(g, p)["strict"]["f1"], 4) for style, (g, p) in sorted(by_style.items())}

    result = {
        "kind": args.kind,
        "data": args.data,
        "memos": len(memos),
        "rejected": len(rejected),
        "strict_f1": round(labels["strict"]["f1"], 4),
        "span_f1": round(labels["spans"]["f1"], 4),
        "memo_exact": round(labels["memo_exact"], 4),
        "reminder_f1": round(suggestions["reminders"]["f1"], 4),
        "reminder_intent_f1": round(suggestions["reminder_intents"]["f1"], 4),
        "detail_f1": round(suggestions["details"]["f1"], 4),
        "people_f1": round(suggestions["people"]["f1"], 4),
        "suggestions_fully_right": round(suggestions["memos_fully_right"], 4),
        "latency_ms_1thread": round(latency_ms(model, tokenizer, [m.text for m in memos[:200]], max_len), 2),
        "by_type": {t: round(m["f1"], 4) for t, m in labels["by_type"].items()},
        "by_style": styles,
        "checks": {k: round(v, 4) for k, v in labels["checks"].items()},
    }
    print(json.dumps(result, indent=2))
    if args.write:
        out = Path(args.model) / "metrics.json"
        existing = json.loads(out.read_text()) if out.exists() else {}
        existing[args.kind] = result
        out.write_text(json.dumps(existing, indent=2))


if __name__ == "__main__":
    main()
