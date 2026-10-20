#!/usr/bin/env python3
"""Shrink a BERT WordPiece backbone's vocabulary (and embedding table) to what memos need.

tools/prune_vocab.py models/backbones/bert_uncased_L-2_H-128_A-2 --keep-top 8000 --texts data/train.jsonl data/dev.jsonl

Keeps the special tokens, every single-character piece (so any word still tokenizes), the `--keep-top` most
frequent wordpieces (BERT's vocab is frequency-ordered after its character block), and every token used by the
given texts and the name lists. Greedy longest-match over a subset vocabulary picks the same pieces for any
text whose pieces were all kept, so tokenization of the training data is unchanged.
"""

import argparse
from pathlib import Path

import _path  # noqa: F401
import torch
from transformers import AutoModel, AutoTokenizer, BertTokenizerFast

from memo_extract.data import read_jsonl
from memo_extract.names import NAMES, SURNAMES

SPECIAL = ("[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]")


def is_single_char(token):
    return len(token) == 1 or (token.startswith("##") and len(token) == 3)


def keep_ids(vocab, tokenizer, texts, keep_top):
    keep = {vocab.index(t) for t in SPECIAL}
    keep |= {i for i, t in enumerate(vocab) if is_single_char(t)}
    regular = [i for i, t in enumerate(vocab) if not t.startswith("[") and not is_single_char(t)]
    keep |= set(regular[:keep_top])
    for text in texts:
        keep |= set(tokenizer(text, add_special_tokens=False)["input_ids"])
    return sorted(keep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("backbone")
    ap.add_argument("--keep-top", type=int, default=8000)
    ap.add_argument("--texts", nargs="*", default=[])
    ap.add_argument("--out")
    args = ap.parse_args()

    source = Path(args.backbone)
    out = Path(args.out or f"{source}-v{args.keep_top}")
    tokenizer = AutoTokenizer.from_pretrained(source)
    vocab = (source / "vocab.txt").read_text(encoding="utf-8").splitlines()
    texts = [r["text"] for r in read_jsonl(args.texts)]
    texts += [" ".join(NAMES), " ".join(SURNAMES)]
    ids = keep_ids(vocab, tokenizer, texts, args.keep_top)

    model = AutoModel.from_pretrained(source)
    old = model.get_input_embeddings().weight.data
    new = torch.nn.Embedding(len(ids), old.shape[1], padding_idx=ids.index(vocab.index("[PAD]")))
    new.weight.data = old[torch.tensor(ids)].clone()
    model.set_input_embeddings(new)
    model.config.vocab_size = len(ids)
    model.config.pad_token_id = ids.index(vocab.index("[PAD]"))

    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    kept = [vocab[i] for i in ids]
    (out / "vocab.txt").write_text("\n".join(kept) + "\n", encoding="utf-8")
    BertTokenizerFast(vocab={token: i for i, token in enumerate(kept)}, do_lower_case=tokenizer.do_lower_case).save_pretrained(out)

    pruned = AutoTokenizer.from_pretrained(out)
    mismatched = sum(
        tokenizer.convert_ids_to_tokens(tokenizer(t)["input_ids"]) != pruned.convert_ids_to_tokens(pruned(t)["input_ids"]) for t in texts
    )
    params = sum(p.numel() for p in model.parameters())
    print(f"{out}: vocab {len(vocab)} -> {len(ids)}, params {params / 1e6:.2f}M, texts tokenized differently: {mismatched}/{len(texts)}")


if __name__ == "__main__":
    main()
