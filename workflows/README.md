# Claude workflow scripts

These are the Claude Code [Workflow](https://docs.claude.com/en/docs/claude-code) scripts that produced the data and the date resolver. Each one fans out Claude subagents and returns a small summary. They are kept so the data can be regenerated or extended with the same prompts.

To rerun one, open Claude Code in the repo and ask it to run the script through the Workflow tool with the arguments shown below. Two things need adjusting first:

- `ROOT` (and `SCRATCH` in `memo-label-extra-30k.js`) are absolute paths from the original machine. Change them to your checkout.
- The agents call `python3 tools/validate.py`, which imports only the standard library, so the system Python is enough.

| Script | What it did | Arguments | Writes |
| --- | --- | --- | --- |
| `memo-data-pilot.js` | Spec v1 pilot. Per brief: a generator writes and labels memos (`gen`), a blind annotator relabels them (`lab`), an adjudicator settles disagreements (`adj`) | `{briefsFile, ids}` | `data/raw/p*.{gen,lab,adj}.jsonl` |
| `memo-data-v2.js` | The main gold data, spec v2. Per brief: a writer writes text only, annotators `a` and `b` label blind in parallel, an adjudicator resolves every disagreement | `{items: [{id, file}]}`, one per brief from `data/briefs/{train,dev,test}.json` | `data/raw/<brief>.{txt,a,b,adj}.jsonl` |
| `memo-unlabelled-texts.js` | 30,000 extra memo texts (500 briefs × 60) with no labels, for the teacher to label (silver data) | `{prefix: "u", count: 500, file: "data/briefs/unlabelled.json"}` | `data/raw/u*.txt.jsonl` |
| `memo-label-extra-30k.js` | One careful annotator per unlabelled brief, to turn the 30k into a single-annotator training set. **Stopped at the account usage limit before any batch finished; no `u*.c.jsonl` exists yet** | `{prefix: "u", count: 500}` | `data/raw/u*.c.jsonl` |
| `memo-date-resolver.js` | Built `memo_extract/dates.py` from `docs/dates.md`: an implementer and an independent spec-test writer work in parallel, then a reconciler fixes whichever side contradicts the spec | none | `memo_extract/dates.py`, `tests/test_dates*.py` |

After a data run, `tools/merge.py` combines the per-brief files into `data/{train,dev,test}.jsonl`; see `docs/handoff.md` for the exact commands.

## Lessons

- **Give every parallel agent a private scratch directory.** In the v2 run, annotators `a` and `b` shared the session scratchpad and some wrote helper scripts with the same names, overwriting each other's work in 35 briefs. Agreement in those briefs (0.632) was no worse than elsewhere (0.618), so the data was kept, but `memo-label-extra-30k.js` now tells each agent to use `SCRATCH/<id>/` only.
- **Agents run at most 16 at a time per workflow.** Running the same script twice on different halves of the briefs doubled throughput. Give the two runs distinct names so they are easy to tell apart.
- **Long runs can stop at account usage limits.** A workflow is resumable (`resumeFromRunId`): finished agents return cached results. Agents that had not finished start again.
- **Validate inside the agent.** Every prompt ends with "run `tools/validate.py` and fix every error until it prints OK", which caught most format mistakes before they reached the merge step.
