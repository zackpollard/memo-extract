# memo-extract

A tiny on-device model that reads a short memo ("Priya's mum is having surgery next week. She's worried.") and finds people, relations, interests, events, dates, facts and requested follow-ups. Plain code then turns those labels into details to save and reminders to confirm ("Check in with Priya about her mum", date to confirm).

```
memo text ──► tokenizer ──► encoder.onnx ──► BIO tags (2 layers) ──► Viterbi ──► spans
                                  │                                              │
                                  └──────────── hidden states ──► heads.onnx ◄───┘
                                                                     │
                       attributes (pronoun, event type, followup, …) + owner/anchor links
                                                                     │
                    dates.py (deterministic) + suggest.py (templates, policy) ──► review screen
```

The model never writes text or does date arithmetic, so it cannot invent a date: every suggestion points back to words in the memo.

**Start here:** [docs/how-it-works.md](docs/how-it-works.md) explains the whole thing in plain English. [docs/handoff.md](docs/handoff.md) gives the current state, results, decisions and open work. [AGENTS.md](AGENTS.md) holds the working rules for anyone, human or AI, continuing development.

Best small model: `bert-mini-v8k-silver-kd`, 8.0 MB at int8, 0.775 strict F1 on the test set. The 23.7 MB teacher scores 0.783, and two independent annotators agree at 0.918. See [runs/summary.md](runs/summary.md).

## Layout

| Path | What |
| --- | --- |
| `docs/labeling.md` | The labelling spec: the single source of truth for what the model predicts |
| `docs/dates.md` | The date resolver spec |
| `memo_extract/` | Records and validation, encoding, model, decoding, training, evaluation, date resolver, suggestion layer, ONNX export, model registry |
| `tools/` | CLIs: data tooling (`make_briefs`, `validate`, `texts`, `compare`, `merge`), `train`, `pseudo_label`, `prune_vocab`, `export`, `evaluate`, `sweep`, `serve` |
| `playground/` | The test page and its saved prompts (`prompts.json`) |
| `data/` | Briefs, raw per-brief agent output (`raw/`), merged splits (`train/dev/test.jsonl`), teacher-labelled `silver.jsonl` and the hand-labelled product examples (`eval/user_examples.jsonl`) |
| `workflows/` | The Claude workflow scripts that wrote and labelled the data and built the date resolver |
| `experiments/` | Run lists for `tools/sweep.py` (size sweep, distillation, learning curve) |
| `runs/` | One directory per training run: config, per-epoch log, test metrics, tokenizer; `summary.md` compares them all. Checkpoints (`model.pt`) are release assets |
| `models/onnx/` | ONNX exports with tokenizer and metrics. Git holds the int8 graphs of `bert-tiny-v8k-silver`, `bert-mini-v8k-silver-kd` and `minilm-l6`; every other graph is a release asset |

## Data

Synthetic memos come from Claude workflow agents: a writer produces memo text from a brief (style, topics, date styles, names), two annotators label it blind against `docs/labeling.md`, and an adjudicator settles every disagreement. `tools/merge.py --briefs data/briefs/*.json` keeps memos both annotators agreed on plus adjudicated ones.

## Train, export, evaluate

```sh
uv sync
.venv/bin/python tools/train.py --backbone models/backbones/bert_uncased_L-4_H-256_A-4 --train data/train.jsonl --dev data/dev.jsonl --out runs/bert-mini
.venv/bin/python tools/export.py runs/bert-mini                    # models/onnx/bert-mini/{encoder,heads}.{fp32,int8}.onnx
.venv/bin/python tools/evaluate.py models/onnx/bert-mini --kind onnx-int8 --data data/test.jsonl --write
.venv/bin/python tools/sweep.py experiments/size-sweep.json --jobs 2   # all of the above for a list of runs, plus runs/summary.md
```

Smaller variants: `tools/prune_vocab.py` cuts a BERT backbone's vocabulary to what memos need (the embedding table is most of a tiny model), and `--teacher runs/<bigger>` distils a larger run into a smaller one that shares its vocabulary.

## Playground

```sh
.venv/bin/python tools/serve.py          # http://127.0.0.1:8765, --host 0.0.0.0 to try it from a phone
```

Every run in `runs/` and export in `models/onnx/` is listed (rescan to pick up new ones). Pick several models to compare side by side; reminders that not every model produced are marked. Saved prompts live in `playground/prompts.json`; "Run all" shows every saved prompt against every selected model. Latency is measured on one thread as a rough proxy for one phone core.

## Tests

```sh
.venv/bin/python -m pytest -q
```

## Getting the models

Git holds the int8 graphs of the three headline models, so the playground and evaluation work straight after `uv sync`. Training checkpoints, fp32 graphs, the other exports and the pruned backbones are attached to the GitHub release `models-2026-10-20`:

```sh
gh release download models-2026-10-20 -D /tmp/memo-models
for f in /tmp/memo-models/*.tar.zst; do tar --zstd -xf "$f"; done   # from the repo root
```

The original backbones come from Hugging Face; [docs/handoff.md](docs/handoff.md) gives the download command.

## Licence

MIT, see [LICENSE](LICENSE). The trained weights are fine-tuned from Apache-2.0 and MIT encoders; see [NOTICE.md](NOTICE.md).

