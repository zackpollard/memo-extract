"""Turn parsed memos into model targets: BIO tags per token, span token bounds, attribute and pointer targets."""

from dataclasses import dataclass

import torch

from .constants import ATTRIBUTES, LAYER_OF, POINTERS, SPAN_TYPES, TAG_LAYERS

LAYER_TAGS = {layer: ("O", *(f"{prefix}-{t}" for t in types for prefix in ("B", "I"))) for layer, types in TAG_LAYERS.items()}
TAG_INDEX = {layer: {tag: i for i, tag in enumerate(tags)} for layer, tags in LAYER_TAGS.items()}
TYPE_INDEX = {span_type: i for i, span_type in enumerate(SPAN_TYPES)}
# one classification head per (span type, attribute)
HEADS = {f"{span_type}.{attr}": (span_type, attr, values) for span_type, attrs in ATTRIBUTES.items() for attr, values in attrs.items()}
IGNORE = -100


@dataclass
class Encoded:
    input_ids: list[int]
    offsets: list[tuple[int, int]]
    tags: dict[str, list[int]]  # layer -> per-token tag
    span_bounds: list[tuple[int, int]]  # first and last token of each span, inclusive
    span_types: list[int]
    attrs: dict[str, list[int]]  # head -> per-span target
    pointers: dict[str, list[int]]  # pointer -> per-span index into [null, *spans]


def tokenize(tokenizer, text, max_len):
    enc = tokenizer(text, return_offsets_mapping=True, truncation=True, max_length=max_len)
    return enc["input_ids"], [tuple(o) for o in enc["offset_mapping"]]


def is_special(offset):
    return offset[0] == offset[1]


def token_bounds(offsets, start, end):
    """First and last token overlapping chars [start, end), or None when truncated away."""
    covered = [i for i, (s, e) in enumerate(offsets) if not is_special((s, e)) and s < end and start < e]
    return (covered[0], covered[-1]) if covered else None


def char_bounds(text, offsets, first, last):
    """Character range covered by tokens first..last, without the leading space byte-level BPE folds in."""
    start, end = offsets[first][0], offsets[last][1]
    while start < end and text[start].isspace():
        start += 1
    return start, end


def encode(memo, tokenizer, max_len):
    input_ids, offsets = tokenize(tokenizer, memo.text, max_len)
    tags = {layer: [IGNORE if is_special(o) else 0 for o in offsets] for layer in TAG_LAYERS}

    kept, bounds = [], []
    for span in memo.spans:
        span_bounds = token_bounds(offsets, span.start, span.end)
        if span_bounds is None:
            continue

        first, last = span_bounds
        layer_tags, index = tags[LAYER_OF[span.type]], TAG_INDEX[LAYER_OF[span.type]]
        if char_bounds(memo.text, offsets, first, last) != (span.start, span.end):
            # truncated, or glued to text the tokenizer cannot split ("jazz🎺"): teach nothing about it
            for i in range(first, last + 1):
                layer_tags[i] = IGNORE
            continue

        layer_tags[first] = index[f"B-{span.type}"]
        for i in range(first + 1, last + 1):
            layer_tags[i] = index[f"I-{span.type}"]
        kept.append(span)
        bounds.append(span_bounds)

    position = {span.id: i for i, span in enumerate(kept)}
    attrs = {
        head: [values.index(span.attrs[attr]) if span.type == span_type else IGNORE for span in kept]
        for head, (span_type, attr, values) in HEADS.items()
    }
    pointers = {pointer: [pointer_target(span, pointer, targets, position) for span in kept] for pointer, targets in POINTERS.items()}
    return Encoded(input_ids, offsets, tags, bounds, [TYPE_INDEX[s.type] for s in kept], attrs, pointers)


def pointer_target(span, pointer, targets, position):
    if span.type not in targets:
        return IGNORE

    target_id = getattr(span, pointer)
    if target_id is None:
        return 0
    if target_id not in position:
        return IGNORE  # target truncated away

    return position[target_id] + 1


def collate(batch, pad_id):
    """Pad a list of Encoded into a dict of tensors."""
    n_tokens = max(len(e.input_ids) for e in batch)
    n_spans = max(1, max(len(e.span_bounds) for e in batch))

    def pad(rows, width, value):
        return torch.tensor([row + [value] * (width - len(row)) for row in rows])

    return {
        "input_ids": pad([e.input_ids for e in batch], n_tokens, pad_id),
        "attention_mask": pad([[1] * len(e.input_ids) for e in batch], n_tokens, 0),
        "tags": {layer: pad([e.tags[layer] for e in batch], n_tokens, IGNORE) for layer in TAG_LAYERS},
        "span_bounds": torch.tensor([[list(b) for b in e.span_bounds] + [[0, 0]] * (n_spans - len(e.span_bounds)) for e in batch]),
        "span_types": pad([e.span_types for e in batch], n_spans, 0),
        "span_mask": pad([[True] * len(e.span_bounds) for e in batch], n_spans, False),
        "attrs": {head: pad([e.attrs[head] for e in batch], n_spans, IGNORE) for head in HEADS},
        "pointers": {pointer: pad([e.pointers[pointer] for e in batch], n_spans, IGNORE) for pointer in POINTERS},
    }
