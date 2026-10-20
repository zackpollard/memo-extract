# Third-party notices

The code, documentation and datasets in this repository are released under the MIT licence (see `LICENSE`).

The trained model weights (`models/onnx/*`, and the checkpoints and exports attached to the GitHub release) are fine-tuned from the pretrained encoders below. Fine-tuning changed every weight and added new output heads; the vocabulary of the `*-v8k` models was also pruned with `tools/prune_vocab.py`. Each derived model stays subject to its upstream licence. Both licences are permissive, but Apache-2.0 asks that redistributions keep a copy of the licence and note the changes.

| Backbone | Used by | Licence |
| --- | --- | --- |
| [google/bert_uncased_L-2_H-128_A-2](https://huggingface.co/google/bert_uncased_L-2_H-128_A-2) | `bert-tiny`, `bert-tiny-v8k*` | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| [google/bert_uncased_L-4_H-256_A-4](https://huggingface.co/google/bert_uncased_L-4_H-256_A-4) | `bert-mini`, `bert-mini-v8k*`, `lc-mini-v8k-*` | Apache-2.0 |
| [google/bert_uncased_L-4_H-512_A-8](https://huggingface.co/google/bert_uncased_L-4_H-512_A-8) | `bert-small`, `teachers/bert-small` | Apache-2.0 |
| [google-bert/bert-base-uncased](https://huggingface.co/google-bert/bert-base-uncased) | `teachers/bert-base` | Apache-2.0 |
| [nreimers/MiniLM-L6-H384-uncased](https://huggingface.co/nreimers/MiniLM-L6-H384-uncased) | `minilm-l6`, `teachers/minilm-l6` | MIT |
| [jhu-clsp/ettin-encoder-17m](https://huggingface.co/jhu-clsp/ettin-encoder-17m) | `ettin-17m` | MIT |
| [jhu-clsp/ettin-encoder-32m](https://huggingface.co/jhu-clsp/ettin-encoder-32m) | `ettin-32m` | MIT |

The memos in `data/` are synthetic. Claude agents wrote them and labelled the gold splits (see `workflows/`). The trained `minilm-l6` teacher labelled `data/silver.jsonl` with `tools/pseudo_label.py`. The names in them and in `memo_extract/names.py` are invented or common given names; they do not describe real people.
