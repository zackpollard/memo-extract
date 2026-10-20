"""Turn model outputs back into labelled spans: constrained BIO decoding per layer, then the span heads on the decoded spans."""

from collections import Counter

import torch

from .constants import POINTERS, TAG_LAYERS
from .encoding import HEADS, LAYER_TAGS, TYPE_INDEX, char_bounds, collate, is_special, tokenize
from .records import Memo, Span, first_mention, first_name, owner_cycle

NEG = -1e9


def transition_mask(tags):
    """allowed[i, j]: tag j may follow tag i. I-X only continues B-X or I-X."""
    allowed = torch.ones(len(tags), len(tags), dtype=torch.bool)
    for j, tag in enumerate(tags):
        if tag.startswith("I-"):
            continuing = {f"B-{tag[2:]}", f"I-{tag[2:]}"}
            allowed[:, j] = torch.tensor([prev in continuing for prev in tags])
    return allowed


TRANSITIONS = {layer: transition_mask(tags) for layer, tags in LAYER_TAGS.items()}
STARTS = {layer: torch.tensor([not tag.startswith("I-") for tag in tags]) for layer, tags in LAYER_TAGS.items()}


def viterbi(log_probs, layer):
    """Best tag sequence for [tokens, tags] log-probs under the BIO constraints."""
    transitions = torch.where(TRANSITIONS[layer], 0.0, NEG)
    score = log_probs[0].masked_fill(~STARTS[layer], NEG)
    back = []
    for row in log_probs[1:]:
        score, best_prev = (score[:, None] + transitions).max(dim=0)
        score = score + row
        back.append(best_prev)

    path = [int(score.argmax())]
    for best_prev in reversed(back):
        path.append(int(best_prev[path[-1]]))
    return path[::-1]


def tags_to_spans(path, tags):
    """[(type, first, last)] positions in `path` from a sequence of tag indices."""
    spans = []
    for i, tag in enumerate(tags[t] for t in path):
        if tag.startswith("B-"):
            spans.append([tag[2:], i, i])
        elif tag.startswith("I-") and spans and spans[-1][0] == tag[2:] and spans[-1][2] == i - 1:
            spans[-1][2] = i
    return [tuple(s) for s in spans]


def decode_tags(tag_logits, row, offsets):
    """Decoded (type, first token, last token) across all layers, ordered by start then layer order."""
    content = [i for i, o in enumerate(offsets) if not is_special(o)]
    if not content:
        return []

    spans = []
    for layer_order, layer in enumerate(TAG_LAYERS):
        path = viterbi(tag_logits[layer][row, content].log_softmax(-1), layer)
        spans += [(content[f], -layer_order, t, content[l]) for t, f, l in tags_to_spans(path, LAYER_TAGS[layer])]
    return [(t, f, l) for f, _, t, l in sorted(spans)]


@torch.inference_mode()
def predict(model, tokenizer, texts, max_len, batch_size=64):
    """Predicted Memo for each text."""
    model.eval()
    memos = []
    for i in range(0, len(texts), batch_size):
        memos += predict_batch(model, tokenizer, texts[i : i + batch_size], max_len)
    return memos


def predict_batch(model, tokenizer, texts, max_len):
    tokenized = [tokenize(tokenizer, text, max_len) for text in texts]
    batch = collate([_Stub(ids) for ids, _ in tokenized], tokenizer.pad_token_id)
    hidden, tag_logits = model.encode(batch["input_ids"], batch["attention_mask"])
    decoded = [decode_tags(tag_logits, row, offsets) for row, (_, offsets) in enumerate(tokenized)]

    n_spans = max(1, max(len(d) for d in decoded))
    bounds = torch.tensor([[[f, l] for _, f, l in d] + [[0, 0]] * (n_spans - len(d)) for d in decoded])
    types = torch.tensor([[TYPE_INDEX[t] for t, _, _ in d] + [0] * (n_spans - len(d)) for d in decoded])
    mask = torch.tensor([[True] * len(d) + [False] * (n_spans - len(d)) for d in decoded])
    attrs, pointers = model.span_heads(hidden, bounds, types, mask)

    return [
        build_memo(text, offsets, decoded[row], {h: a[row] for h, a in attrs.items()}, {p: v[row] for p, v in pointers.items()})
        for row, (text, (_, offsets)) in enumerate(zip(texts, tokenized))
    ]


def snap_to_words(text, start, end):
    """Widen a span that starts or ends inside a word ("find P" for "find Peck") to whole words."""
    while 0 < start < len(text) and text[start - 1].isalnum() and text[start].isalnum():
        start -= 1
    while 0 < end < len(text) and text[end - 1].isalnum() and text[end].isalnum():
        end += 1
    return start, end


def build_memo(text, offsets, decoded, attrs, pointers):
    spans = []
    for k, (span_type, first, last) in enumerate(decoded):
        start, end = snap_to_words(text, *char_bounds(text, offsets, first, last))
        span_attrs = {attr: values[int(attrs[head][k].argmax())] for head, (t, attr, values) in HEADS.items() if t == span_type}
        spans.append(Span(f"s{k}", span_type, text[start:end], start, end, span_attrs))

    for k, span in enumerate(spans):
        for pointer, targets in POINTERS.items():
            if span.type in targets and (target := int(pointers[pointer][k, : len(spans) + 1].argmax())):
                setattr(span, pointer, spans[target - 1].id)

    for span in spans:
        if owner_cycle(spans, span):
            span.owner = None
    link_nicknames(spans)
    by_id = {s.id: s for s in spans}
    for span in spans:
        for pointer in POINTERS:
            if getattr(span, pointer):
                setattr(span, pointer, first_mention(spans, by_id[getattr(span, pointer)]).id)
    harmonise_mentions(spans)
    return Memo("pred", text, spans)


def harmonise_mentions(spans):
    """Give every mention of a person the same pronoun (the most common specific one) and owner (the first set)."""
    groups = {}
    for span in spans:
        if span.type in ("PERSON", "RELATION"):
            groups.setdefault(first_mention(spans, span).id, []).append(span)

    for mentions in groups.values():
        owner = next((m.owner for m in mentions if m.owner), None)
        pronouns = Counter(m.attrs["pronoun"] for m in mentions if m.type == "PERSON" and m.attrs["pronoun"] != "unknown")
        for m in mentions:
            m.owner = owner if not owner_cycle_with(spans, m, owner) else m.owner
            if m.type == "PERSON":
                m.attrs["pronoun"] = pronouns.most_common(1)[0][0] if pronouns else "unknown"


def owner_cycle_with(spans, span, owner):
    previous, span.owner = span.owner, owner
    cycle = owner_cycle(spans, span)
    span.owner = previous
    return cycle


def link_nicknames(spans):
    """Stand-in for the labelled same_as, which the model does not predict: a later name that is a 3+ letter
    prefix of an earlier one ("Sid" after "Siddharth", "Kris" after "Krisztina") is the same person."""
    people = []
    for span in (s for s in spans if s.type == "PERSON"):
        name = first_name(span)
        earlier = next((p for p in people if first_name(p) != name and len(name) >= 3 and first_name(p).startswith(name)), None)
        if earlier is not None:
            span.same_as = earlier.id
        elif all(first_name(p) != name for p in people):
            people.append(span)


class _Stub:
    """Just enough of Encoded for collate() to pad token ids at inference time."""

    def __init__(self, input_ids):
        self.input_ids = input_ids
        self.tags = {layer: [0] * len(input_ids) for layer in TAG_LAYERS}
        self.span_bounds, self.span_types = [], []
        self.attrs = {head: [] for head in HEADS}
        self.pointers = {pointer: [] for pointer in POINTERS}
