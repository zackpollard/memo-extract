"""Export a trained MemoTagger to two ONNX graphs (encoder + tagger, span heads), quantise to int8, and run them.

The app runs the encoder graph, decodes BIO tags itself (Viterbi over a few dozen tokens), then runs the
heads graph on the decoded spans, exactly like `decode.predict` does with the PyTorch model.
"""

import json
from pathlib import Path

import onnxruntime as ort
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic
from torch import nn

from .constants import POINTERS, TAG_LAYERS
from .encoding import HEADS

OPSET = 18


class EncoderGraph(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, input_ids, attention_mask):
        hidden, tags = self.model.encode(input_ids, attention_mask)
        return (hidden, *(tags[layer] for layer in TAG_LAYERS))


class HeadsGraph(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, hidden, span_bounds, span_types, span_mask):
        attrs, pointers = self.model.span_heads(hidden, span_bounds, span_types, span_mask)
        return (*(attrs[h] for h in HEADS), *(pointers[p] for p in POINTERS))


ENCODER_OUTPUTS = ["hidden", *(f"tags_{layer}" for layer in TAG_LAYERS)]
HEAD_OUTPUTS = [*(f"attr_{h.replace('.', '_')}" for h in HEADS), *(f"pointer_{p}" for p in POINTERS)]


def export(model, out_dir, tokenizer, meta, quantize=True):
    """Write encoder.onnx and heads.onnx (fp32, and int8 versions when `quantize`), the tokenizer and meta into out_dir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(out / "tokenizer")
    (out / "meta.json").write_text(json.dumps({**meta, "params": sum(p.numel() for p in model.parameters())}, indent=2))
    model.eval()
    hidden_size = model.encoder.config.hidden_size
    ids = torch.ones(2, 12, dtype=torch.long)
    mask = torch.ones(2, 12, dtype=torch.long)
    hidden = torch.zeros(2, 12, hidden_size)
    bounds = torch.zeros(2, 3, 2, dtype=torch.long)
    types = torch.zeros(2, 3, dtype=torch.long)
    span_mask = torch.ones(2, 3, dtype=torch.bool)

    batch, tokens, spans = (torch.export.Dim(n, min=1, max=1024) for n in ("batch", "tokens", "spans"))
    torch.onnx.export(
        EncoderGraph(model),
        (ids, mask),
        out / "encoder.fp32.onnx",
        input_names=["input_ids", "attention_mask"],
        output_names=ENCODER_OUTPUTS,
        opset_version=OPSET,
        dynamo=True,
        external_data=False,
        dynamic_shapes={"input_ids": {0: batch, 1: tokens}, "attention_mask": {0: batch, 1: tokens}},
    )
    torch.onnx.export(
        HeadsGraph(model),
        (hidden, bounds, types, span_mask),
        out / "heads.fp32.onnx",
        input_names=["hidden", "span_bounds", "span_types", "span_mask"],
        output_names=HEAD_OUTPUTS,
        opset_version=OPSET,
        dynamo=True,
        external_data=False,
        dynamic_shapes={
            "hidden": {0: batch, 1: tokens},
            "span_bounds": {0: batch, 1: spans},
            "span_types": {0: batch, 1: spans},
            "span_mask": {0: batch, 1: spans},
        },
    )
    if quantize:
        for name in ("encoder", "heads"):
            quantize_dynamic(
                out / f"{name}.fp32.onnx",
                out / f"{name}.int8.onnx",
                weight_type=QuantType.QInt8,
                op_types_to_quantize=["MatMul", "Gemm", "Gather"],
            )

    sizes = {p.name: p.stat().st_size for p in sorted(out.glob("*.onnx"))}
    (out / "manifest.json").write_text(
        json.dumps({"encoder_outputs": ENCODER_OUTPUTS, "head_outputs": HEAD_OUTPUTS, "sizes": sizes}, indent=2)
    )
    return sizes


class OnnxTagger:
    """Drop-in for MemoTagger in decode.predict, backed by onnxruntime sessions."""

    def __init__(self, out_dir, precision="int8", threads=1):
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        out = Path(out_dir)
        self.encoder = ort.InferenceSession(str(out / f"encoder.{precision}.onnx"), options, providers=["CPUExecutionProvider"])
        self.heads = ort.InferenceSession(str(out / f"heads.{precision}.onnx"), options, providers=["CPUExecutionProvider"])

    def eval(self):
        return self

    def encode(self, input_ids, attention_mask):
        hidden, *tags = self.encoder.run(None, {"input_ids": input_ids.numpy(), "attention_mask": attention_mask.numpy()})
        return torch.from_numpy(hidden), {layer: torch.from_numpy(t) for layer, t in zip(TAG_LAYERS, tags)}

    def span_heads(self, hidden, span_bounds, span_types, span_mask):
        feeds = {
            "hidden": hidden.numpy(),
            "span_bounds": span_bounds.numpy(),
            "span_types": span_types.numpy(),
            "span_mask": span_mask.numpy(),
        }
        outputs = [torch.from_numpy(o) for o in self.heads.run(None, feeds)]
        return dict(zip(HEADS, outputs[: len(HEADS)])), dict(zip(POINTERS, outputs[len(HEADS) :]))
