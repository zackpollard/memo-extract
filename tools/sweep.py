#!/usr/bin/env python3
"""Run a list of experiments: train, export to ONNX, evaluate torch + int8 on the test set, summarise.

tools/sweep.py experiments.json [--jobs 2] [--threads 8]

experiments.json is a list of {"name", "backbone", ...TrainConfig overrides}. Each finished run lands in
runs/<name> and models/onnx/<name>, so it shows up in the playground, and in runs/summary.md.
"""

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
DATA = {"train": ["data/train.jsonl"], "dev": ["data/dev.jsonl"], "test": ["data/test.jsonl"]}


def run(cmd, log):
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"$ {' '.join(cmd)}\n")
        f.flush()
        subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True)


def experiment(spec, threads):
    name = spec["name"]
    run_dir = ROOT / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    log = run_dir / "sweep.log"
    if not (run_dir / "model.pt").exists():
        flags = [f"--{k.replace('_', '-')}={v}" for k, v in spec.items() if k not in ("name", "train_files")]
        run(
            [
                PY,
                "tools/train.py",
                "--train",
                *spec.get("train_files", DATA["train"]),
                "--dev",
                *DATA["dev"],
                "--out",
                str(run_dir),
                "--threads",
                str(threads),
                *flags,
            ],
            log,
        )
    onnx_dir = ROOT / "models" / "onnx" / name
    if not (onnx_dir / "encoder.int8.onnx").exists():
        run([PY, "tools/export.py", str(run_dir), "--out", str(onnx_dir)], log)
    for path, kind in ((run_dir, "torch"), (onnx_dir, "onnx-int8")):
        run([PY, "tools/evaluate.py", str(path), "--data", *DATA["test"], "--kind", kind, "--threads", str(threads), "--write"], log)
    return name


def summarise():
    rows = []
    for run_dir in sorted((ROOT / "runs").glob("*/meta.json")):
        name = run_dir.parent.name
        meta = json.loads(run_dir.read_text())
        torch_m = (
            json.loads((run_dir.parent / "metrics.json").read_text()).get("torch", {}) if (run_dir.parent / "metrics.json").exists() else {}
        )
        onnx_path = ROOT / "models" / "onnx" / name
        int8 = json.loads((onnx_path / "metrics.json").read_text()).get("onnx-int8", {}) if (onnx_path / "metrics.json").exists() else {}
        size = sum(p.stat().st_size for p in onnx_path.glob("*.int8.onnx")) / 1e6 if onnx_path.exists() else None
        params = json.loads((onnx_path / "meta.json").read_text()).get("params") if (onnx_path / "meta.json").exists() else None
        rows.append((name, Path(meta["config"]["backbone"]).name, params, size, torch_m, int8))

    lines = [
        "| run | backbone | params | int8 MB | strict F1 | int8 strict F1 | reminder F1 | detail F1 | memos fully right | int8 ms (1 thread) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, backbone, params, size, t, q in sorted(rows, key=lambda r: r[2] or 0):
        cell = lambda d, k: f"{d[k]:.3f}" if k in d else "—"
        lines.append(
            f"| {name} | {backbone} | {params / 1e6:.2f}M | {size:.1f} | {cell(t, 'strict_f1')} | {cell(q, 'strict_f1')} | {cell(q, 'reminder_f1')} | {cell(q, 'detail_f1')} | {cell(q, 'suggestions_fully_right')} | {q.get('latency_ms_1thread', '—')} |"
            if params and size
            else f"| {name} | {backbone} | — | — | {cell(t, 'strict_f1')} | — | — | — | — | — |"
        )
    (ROOT / "runs" / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experiments")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()

    specs = json.loads(Path(args.experiments).read_text(encoding="utf-8"))
    with ThreadPoolExecutor(args.jobs) as pool:
        for future in [pool.submit(experiment, spec, args.threads) for spec in specs]:
            try:
                print("done", future.result(), flush=True)
            except subprocess.CalledProcessError as e:
                print("FAILED", e.cmd, flush=True)
    summarise()


if __name__ == "__main__":
    main()
