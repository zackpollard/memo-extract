# AGENTS.md

Instructions for an AI agent (or a person) continuing work on memo-extract. Read this file first, then:

1. [docs/handoff.md](docs/handoff.md): current state, results, how everything was produced, decisions and dead ends, the open to-do list.
2. [docs/labeling.md](docs/labeling.md): the labelling spec. It is the single source of truth for what the model predicts. Data, model heads, decoding and evaluation all follow it.
3. [CONTEXT.md](CONTEXT.md): the project vocabulary. Use these terms in code, docs and commit messages.
4. [docs/dates.md](docs/dates.md): the date resolver spec.
5. [docs/how-it-works.md](docs/how-it-works.md): a plain-English walkthrough, if you want the big picture first.

## What this is

A tiny on-device model (BERT-style encoder, 3 to 24 MB at int8) that tags people, relations, interests, events, dates, facts and actions in short personal memos, plus deterministic Python that turns the tags into details to save and reminders to confirm. The model never generates text or does date arithmetic.

## Setup

```sh
uv sync                                   # Python 3.13, CPU-only torch from the pytorch-cpu index
gh release download models-2026-10-20 -D /tmp/memo-models   # checkpoints, every ONNX export, pruned backbones (1.8 GB)
for f in /tmp/memo-models/*.tar.zst; do tar --zstd -xf "$f"; done   # run from the repo root: restores runs/ and models/ in place
```

Git already holds the int8 ONNX graphs for the three headline models (`bert-tiny-v8k-silver`, `bert-mini-v8k-silver-kd`, `minilm-l6`), so the playground and evaluation work without the release. The full list of release assets and how to download the original Hugging Face backbones are in docs/handoff.md.

## Checklist before reporting work as done

```sh
.venv/bin/python -m pytest -q             # ~1,260 tests, under 10 s
uvx ruff@0.17.0 check .
uvx ruff@0.17.0 format --check .
```

All three must be clean. Run pytest as `python -m pytest` from the repo root: the package is not installed, and bare `pytest` fails to import it. The tools put the repo root on `sys.path` through `tools/_path.py`. Ruff is not a project dependency; `uvx` fetches the pinned version. Regenerate derived artifacts in the same change: retrain, re-export or re-evaluate (`tools/evaluate.py --write`, `tools/sweep.py` rewrites `runs/summary.md`) whenever a change alters model inputs, outputs or scoring.

## Conventions

- **Spec first.** A labelling change starts in docs/labeling.md, then goes to `memo_extract/constants.py` (label sets), `records.py` (validation), the model heads, decode and evaluate, plus the data. Bump the spec version when a change invalidates existing labels.
- **Every magic number has a name in `memo_extract/constants.py`.** Enumerations are string-valued and live there too.
- **Tests ship with every change.** Every bug fix gets a test that fails before the fix. Spec-driven code (dates, suggestions) has table tests in `tests/`.
- **The model only labels.** Dates, wording and confirmation policy live in plain code (`dates.py`, `suggest.py`, `templates.py`) so they can be ported to the app and unit-tested. Do not move them into the model.
- **Adding a dependency is a decision for the maintainer.** Prefer the standard library and what `pyproject.toml` already has.
- **Commits**: conventional commits, lowercase, no trailing period (`fix(suggest): gift reminder date`). One idea per commit.
- **Measurement**: compare models on `data/test.jsonl` only at the end. Pick hyperparameters on `data/dev.jsonl`. Report int8 numbers, because int8 is what ships.

## Machine and tooling gotchas

- **CPU training**: the original machine had no GPU (Core Ultra 9 285HX, 24 threads, 96 GB RAM). PyTorch was fastest at 8 to 16 threads and slower at 24. `train.py`, `evaluate.py` and `pseudo_label.py` default to 16 threads. `sweep.py` passes 8, so `--jobs 2` runs two jobs side by side, which beats one job at 24.
- **Latency numbers** are measured on one thread (`--threads 1`) as a proxy for one phone core. They are not phone measurements.
- **Claude workflow agents** generated all data (`workflows/*.js`). Each parallel agent must get its own private scratch directory and file names: annotators sharing a scratch directory overwrote each other's helper scripts once (see handoff). Agents run at most 16 at a time per workflow, and long labelling runs can stop at account usage limits; the scripts are resumable.
- **Shell**: the original sessions ran zsh. Quote variables, and do not use `path` as a variable name, because zsh ties it to `PATH`.
