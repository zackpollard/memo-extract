"""Find trained runs and exported models on disk, and load them on demand for the playground."""

import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from transformers import AutoTokenizer

from .decode import predict
from .export import OnnxTagger
from .suggest import suggest
from .training import load

ONNX_PRECISIONS = ("int8", "fp32")


class NotFound(LookupError):
    pass


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    kind: str  # "torch" | "onnx-int8" | "onnx-fp32"
    path: str
    backbone: str
    size_mb: float
    params_m: float | None
    max_len: int
    dev_strict_f1: float | None
    test: dict | None


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def describe(path, meta, kind, size_bytes, params):
    config = meta.get("config", {})
    dev = meta.get("dev", {}).get("strict", {}).get("f1")
    return ModelInfo(
        id=f"{path.name}:{kind}",
        name=path.name,
        kind=kind,
        path=str(path),
        backbone=Path(config.get("backbone", "?")).name,
        size_mb=round(size_bytes / 1e6, 2),
        params_m=round(params / 1e6, 2) if params else None,
        max_len=config.get("max_len", 160),
        dev_strict_f1=round(dev, 4) if dev is not None else None,
        test=(read_json(path / "metrics.json") or {}).get(kind),
    )


def discover(runs_dir, onnx_dir):
    """Every loadable model: PyTorch runs (runs/*/model.pt) and ONNX exports (models/onnx/*/encoder.<precision>.onnx)."""
    found = []
    for path in sorted(Path(runs_dir).glob("*/model.pt")):
        meta = read_json(path.parent / "meta.json") or {}
        size = path.stat().st_size
        found.append(describe(path.parent, meta, "torch", size, size // 4))
    for path in sorted(Path(onnx_dir).glob("*/meta.json")):
        meta = read_json(path) or {}
        for precision in ONNX_PRECISIONS:
            files = [path.parent / f"{part}.{precision}.onnx" for part in ("encoder", "heads")]
            if all(f.exists() for f in files):
                found.append(describe(path.parent, meta, f"onnx-{precision}", sum(f.stat().st_size for f in files), meta.get("params")))
    return found


def serialise(memo):
    return [
        {"id": s.id, "type": s.type, "text": s.text, "start": s.start, "end": s.end, "attrs": s.attrs, "owner": s.owner, "anchor": s.anchor}
        for s in memo.spans
    ]


class Registry:
    """Discovers models on every listing and keeps loaded ones in memory. Prediction is serialised by a lock."""

    def __init__(self, runs_dir, onnx_dir):
        self.runs_dir, self.onnx_dir = runs_dir, onnx_dir
        self.loaded = {}
        self.lock = threading.Lock()

    def models(self):
        return [asdict(m) for m in discover(self.runs_dir, self.onnx_dir)]

    def get(self, model_id):
        info = next((m for m in discover(self.runs_dir, self.onnx_dir) if m.id == model_id), None)
        if info is None:
            raise NotFound(f"Model not found: {model_id}")
        if model_id not in self.loaded:
            self.loaded[model_id] = (info, *self.load(info))
        return self.loaded[model_id]

    def load(self, info):
        if info.kind == "torch":
            model, tokenizer, _ = load(info.path)
            return model, tokenizer
        return OnnxTagger(info.path, info.kind.removeprefix("onnx-")), AutoTokenizer.from_pretrained(Path(info.path) / "tokenizer")

    def run(self, model_id, texts, today, contacts=None, day_first=True):
        """Prediction and suggestions for each text, with per-text latency in milliseconds."""
        with self.lock:
            info, model, tokenizer = self.get(model_id)
            results = []
            for text in texts:
                started = time.perf_counter()
                (memo,) = predict(model, tokenizer, [text], info.max_len)
                ms = (time.perf_counter() - started) * 1000
                results.append({"ms": round(ms, 2), "spans": serialise(memo), "suggestions": suggest(memo, today, contacts, day_first)})
            return results
