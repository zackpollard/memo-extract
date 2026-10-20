"""Small encoder with a BIO tagger plus span heads: one classifier per attribute and one pointer per link type."""

import math

import torch
from torch import nn
from torch.nn import functional as F
from transformers import AutoModel

from .constants import POINTERS, SPAN_TYPES
from .encoding import HEADS, IGNORE, LAYER_TAGS, TYPE_INDEX

SPAN_DIM = 128
MAX_SPAN_DISTANCE = 8
DROPOUT = 0.1
MASKED = -1e4  # finite so the graph stays safe under fp16 and int8 export


class Pointer(nn.Module):
    """Scores every other span (plus a learned null) as the target of a link from each span."""

    def __init__(self, dim, allowed):
        super().__init__()
        self.query = nn.Linear(dim, dim)
        self.key = nn.Linear(dim, dim)
        self.null = nn.Parameter(torch.zeros(dim))
        self.distance = nn.Embedding(2 * MAX_SPAN_DISTANCE + 1, 1)
        self.register_buffer("allowed", allowed, persistent=False)

    def forward(self, reps, span_types, span_mask):
        n_spans = reps.shape[1]
        query, key = self.query(reps), self.key(reps)
        scores = query @ key.transpose(1, 2) / math.sqrt(reps.shape[-1])

        index = torch.arange(n_spans, device=reps.device)
        distance = (index[None, :] - index[:, None]).clamp(-MAX_SPAN_DISTANCE, MAX_SPAN_DISTANCE) + MAX_SPAN_DISTANCE
        scores = scores + self.distance(distance).squeeze(-1)

        valid = self.allowed[span_types[:, :, None], span_types[:, None, :]] & span_mask[:, None, :]
        valid = valid & ~torch.eye(n_spans, dtype=torch.bool, device=reps.device)
        scores = scores.masked_fill(~valid, MASKED)
        null = (query @ self.null)[..., None]
        return torch.cat([null, scores], dim=-1)


def allowed_matrix(targets):
    allowed = torch.zeros(len(SPAN_TYPES), len(SPAN_TYPES), dtype=torch.bool)
    for source, target_types in targets.items():
        for target in target_types:
            allowed[TYPE_INDEX[source], TYPE_INDEX[target]] = True
    return allowed


class MemoTagger(nn.Module):
    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder
        hidden = encoder.config.hidden_size
        self.taggers = nn.ModuleDict(
            {layer: nn.Sequential(nn.Dropout(DROPOUT), nn.Linear(hidden, len(tags))) for layer, tags in LAYER_TAGS.items()}
        )
        self.span_proj = nn.Sequential(nn.Linear(2 * hidden, SPAN_DIM), nn.GELU(), nn.Dropout(DROPOUT))
        self.type_embedding = nn.Embedding(len(SPAN_TYPES), SPAN_DIM)
        self.attr_heads = nn.ModuleDict(
            {head.replace(".", "_"): nn.Linear(SPAN_DIM, len(values)) for head, (_, _, values) in HEADS.items()}
        )
        self.pointers = nn.ModuleDict({pointer: Pointer(SPAN_DIM, allowed_matrix(targets)) for pointer, targets in POINTERS.items()})

    @classmethod
    def from_backbone(cls, path):
        return cls(AutoModel.from_pretrained(path))

    def encode(self, input_ids, attention_mask):
        hidden = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        return hidden, {layer: tagger(hidden) for layer, tagger in self.taggers.items()}

    def span_heads(self, hidden, span_bounds, span_types, span_mask):
        """Attribute logits per head and pointer logits over [null, *spans] for each span."""
        gather = lambda index: torch.gather(hidden, 1, index[..., None].expand(-1, -1, hidden.shape[-1]))
        edges = torch.cat([gather(span_bounds[..., 0]), gather(span_bounds[..., 1])], dim=-1)
        reps = self.span_proj(edges) + self.type_embedding(span_types)
        attrs = {head: self.attr_heads[head.replace(".", "_")](reps) for head in HEADS}
        pointers = {name: pointer(reps, span_types, span_mask) for name, pointer in self.pointers.items()}
        return attrs, pointers

    def forward(self, batch):
        hidden, tag_logits = self.encode(batch["input_ids"], batch["attention_mask"])
        attrs, pointers = self.span_heads(hidden, batch["span_bounds"], batch["span_types"], batch["span_mask"])
        return tag_logits, attrs, pointers


def ce(logits, target):
    if (target != IGNORE).sum() == 0:
        return logits.sum() * 0.0
    return F.cross_entropy(logits.reshape(-1, logits.shape[-1]), target.reshape(-1), ignore_index=IGNORE)


def loss(outputs, batch):
    """Sum of tagging, attribute and pointer losses, plus the parts for logging."""
    tag_logits, attrs, pointers = outputs
    parts = {f"tags.{layer}": ce(logits, batch["tags"][layer]) for layer, logits in tag_logits.items()}
    parts.update({head: ce(attrs[head], batch["attrs"][head]) for head in HEADS})
    parts.update({pointer: ce(pointers[pointer], batch["pointers"][pointer]) for pointer in POINTERS})
    return sum(parts.values()), {k: v.item() for k, v in parts.items()}


def kl(student_logits, teacher_logits, temperature):
    if student_logits.numel() == 0:
        return student_logits.sum() * 0.0
    log_p = F.log_softmax(student_logits / temperature, dim=-1)
    q = F.softmax(teacher_logits / temperature, dim=-1)
    return F.kl_div(log_p, q, reduction="batchmean") * temperature**2


def distill_loss(student, teacher, batch, temperature):
    """KL from the teacher's softened distributions on every labelled token, span attribute and pointer."""
    (s_tags, s_attrs, s_pointers), (t_tags, t_attrs, t_pointers) = student, teacher
    parts = {}
    for layer, logits in s_tags.items():
        mask = batch["tags"][layer] != IGNORE
        parts[f"kd.tags.{layer}"] = kl(logits[mask], t_tags[layer][mask], temperature)
    for head, logits in s_attrs.items():
        mask = batch["attrs"][head] != IGNORE
        parts[f"kd.{head}"] = kl(logits[mask], t_attrs[head][mask], temperature)
    for pointer, logits in s_pointers.items():
        mask = batch["pointers"][pointer] != IGNORE
        parts[f"kd.{pointer}"] = kl(logits[mask], t_pointers[pointer][mask], temperature)
    return sum(parts.values()), {k: v.item() for k, v in parts.items()}
