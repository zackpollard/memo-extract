"""Fine-tune a pretrained encoder into a MemoTagger, keeping the checkpoint with the best strict dev F1."""

import json
import math
import random
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from transformers import AutoConfig, AutoModel, AutoTokenizer

from .augment import augment
from .decode import predict
from .encoding import collate, encode
from .evaluate import score
from .model import MemoTagger, distill_loss, loss
from .names import TRAIN_NAMES

LENGTH_BUCKET_BATCHES = 50  # batches per length-sorted chunk; sorting cuts padding on CPU
GRAD_CLIP = 1.0


@dataclass
class TrainConfig:
    backbone: str
    out: str
    epochs: int = 15
    batch_size: int = 32
    lr: float = 2e-4
    head_lr: float = 1e-3
    weight_decay: float = 0.01
    warmup: float = 0.06
    max_len: int = 160
    swap_rate: float = 0.5
    dictate_rate: float = 0.25
    seed: int = 0
    threads: int = 16
    teacher: str | None = None  # a training run whose soft predictions the student also learns from
    distill_weight: float = 0.5
    temperature: float = 2.0


def batches(encoded, batch_size, rng):
    order = list(range(len(encoded)))
    rng.shuffle(order)
    chunk = batch_size * LENGTH_BUCKET_BATCHES
    result = []
    for i in range(0, len(order), chunk):
        part = sorted(order[i : i + chunk], key=lambda j: len(encoded[j].input_ids))
        result += [part[k : k + batch_size] for k in range(0, len(part), batch_size)]
    rng.shuffle(result)
    return result


def student_to_teacher_ids(student_tokenizer, teacher_tokenizer):
    """Map each student token id to the teacher's id for the same piece, so the teacher reads exactly the pieces
    the student reads and token-level distillation lines up by construction. Needs the student's vocabulary to
    be a subset of the teacher's (true for a pruned copy of the same WordPiece family)."""
    pieces = student_tokenizer.convert_ids_to_tokens(list(range(len(student_tokenizer))))
    vocab = teacher_tokenizer.get_vocab()
    missing = [p for p in pieces if p not in vocab]
    if missing:
        raise ValueError(f"Student vocabulary is not a subset of the teacher's ({len(missing)} pieces missing, e.g. {missing[:3]})")
    return torch.tensor([vocab[p] for p in pieces])


def summary(metrics):
    return {
        "strict_f1": round(metrics["strict"]["f1"], 4),
        "span_f1": round(metrics["spans"]["f1"], 4),
        "memo_exact": round(metrics["memo_exact"], 4),
        "by_type": {t: round(m["f1"], 3) for t, m in metrics["by_type"].items()},
    }


def load_backbone(path):
    config = AutoConfig.from_pretrained(path)
    if hasattr(config, "reference_compile"):
        config.reference_compile = False
    return AutoModel.from_pretrained(path, config=config)


def train(cfg, train_memos, dev_memos, log=print):
    torch.manual_seed(cfg.seed)
    torch.set_num_threads(cfg.threads)
    rng = random.Random(cfg.seed)
    out = Path(cfg.out)
    out.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(cfg.backbone)
    model = MemoTagger(load_backbone(cfg.backbone))
    teacher, teacher_ids = None, None
    if cfg.teacher:
        teacher, teacher_tokenizer, _ = load(cfg.teacher)
        teacher.requires_grad_(False)
        teacher_ids = student_to_teacher_ids(tokenizer, teacher_tokenizer)
    encoder_ids = {id(p) for p in model.encoder.parameters()}
    optimizer = torch.optim.AdamW(
        [
            {"params": list(model.encoder.parameters()), "lr": cfg.lr},
            {"params": [p for p in model.parameters() if id(p) not in encoder_ids], "lr": cfg.head_lr},
        ],
        weight_decay=cfg.weight_decay,
    )
    total_steps = math.ceil(len(train_memos) / cfg.batch_size) * cfg.epochs
    warmup_steps = max(1, int(total_steps * cfg.warmup))
    schedule = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda s: (s + 1) / warmup_steps if s < warmup_steps else max(0.0, (total_steps - s) / (total_steps - warmup_steps))
    )

    best = -1.0
    for epoch in range(1, cfg.epochs + 1):
        started = time.perf_counter()
        model.train()
        encoded = [encode(augment(m, rng, TRAIN_NAMES, cfg.swap_rate, cfg.dictate_rate), tokenizer, cfg.max_len) for m in train_memos]
        epoch_batches = batches(encoded, cfg.batch_size, rng)
        totals = Counter()
        for index in epoch_batches:
            batch = collate([encoded[i] for i in index], tokenizer.pad_token_id)
            outputs = model(batch)
            total_loss, parts = loss(outputs, batch)
            if teacher is not None:
                teacher_batch = {**batch, "input_ids": teacher_ids[batch["input_ids"]]}
                with torch.no_grad():
                    teacher_outputs = teacher(teacher_batch)
                soft_loss, soft_parts = distill_loss(outputs, teacher_outputs, batch, cfg.temperature)
                total_loss = (1 - cfg.distill_weight) * total_loss + cfg.distill_weight * soft_loss
                parts |= soft_parts
            optimizer.zero_grad(set_to_none=True)
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            optimizer.step()
            schedule.step()
            totals.update(parts)

        train_seconds = time.perf_counter() - started
        metrics = score(dev_memos, predict(model, tokenizer, [m.text for m in dev_memos], cfg.max_len))
        record = {
            "epoch": epoch,
            "train_seconds": round(train_seconds, 1),
            "loss": round(sum(totals.values()) / len(epoch_batches), 4),
            "dev": summary(metrics),
        }
        log(json.dumps(record))
        with open(out / "log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        if metrics["strict"]["f1"] > best:
            best = metrics["strict"]["f1"]
            save(model, tokenizer, out, {"config": asdict(cfg), "epoch": epoch, "dev": metrics})

    return best


def save(model, tokenizer, out, meta):
    torch.save(model.state_dict(), out / "model.pt")
    model.encoder.config.save_pretrained(out / "encoder")
    tokenizer.save_pretrained(out / "tokenizer")
    (out / "meta.json").write_text(json.dumps(meta, indent=2))


def load(path):
    """(model, tokenizer, meta) from a training output directory."""
    path = Path(path)
    config = AutoConfig.from_pretrained(path / "encoder")
    if hasattr(config, "reference_compile"):
        config.reference_compile = False
    model = MemoTagger(AutoModel.from_config(config))
    model.load_state_dict(torch.load(path / "model.pt", weights_only=True))
    model.eval()
    return model, AutoTokenizer.from_pretrained(path / "tokenizer"), json.loads((path / "meta.json").read_text())
