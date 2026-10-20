export const meta = {
  name: 'memo-label-extra-30k',
  description: 'Label the 30k extra memos with one careful annotator each (spec v2) for a larger training set',
  phases: [{ title: 'Label', detail: 'one annotator per brief of 60 memos' }],
}

const ROOT = '/home/zack/Source/memo-extract'
const RAW = `${ROOT}/data/raw`
const SPEC = `${ROOT}/docs/labeling.md`
const VALIDATE = `python3 ${ROOT}/tools/validate.py`
const SCRATCH = '/tmp/claude-1000/-home-zack/a627e32c-045a-4a58-9aa2-72c2c2028bb3/scratchpad/annotators'
const RESULT = {
  type: 'object',
  properties: { count: { type: 'integer' }, ambiguities: { type: 'string' } },
  required: ['count', 'ambiguities'],
}

const ids = Array.from({ length: args.count }, (_, i) => `${args.prefix}${String(i).padStart(3, '0')}`)

const labelPrompt = (id) => `You are the annotator for one batch of a memo-extraction dataset.

1. Read the labelling spec ${SPEC} in full. It is the source of truth; when two readings are defensible, follow the rule the spec points to.
2. Read the memos in ${RAW}/${id}.txt.jsonl.
3. Label every memo, keeping each id and text byte-for-byte identical. Write ${RAW}/${id}.c.jsonl, one {"id", "text", "spans"} per line, in the same order. If you write any helper script or scratch file, put it only under ${SCRATCH}/${id}/ (create it); never write elsewhere in the scratchpad, because other annotators share it.
4. Run \`${VALIDATE} ${RAW}/${id}.c.jsonl\` and fix every error until it prints OK.
5. Re-read every record against the spec and fix what is wrong, then re-validate. Check especially: FACT scope (durable details and every stated feeling; intensifiers dropped, softeners kept; nothing situational or resolved), EVENT boundaries and event_type, the followup table (first matching row wins; nervous/struggling means the owner), deaths owned by the bereaved, shared events, ACTION only for explicit requests or to-dos, action_type by purpose then verb, timing (past events are after), DATE boundaries (drop only on/at/@/for) and the DATE anchor tie-breaks, pointers to first mentions, same owner and pronoun on every mention, same_as for nicknames, pets as FACT.

Return the number of memos labelled and any spec ambiguities you hit (one short line each).`

const results = await parallel(ids.map((id) => () => agent(labelPrompt(id), { label: `label:${id}`, phase: 'Label', schema: RESULT, effort: 'high' })))
const done = results.filter(Boolean)
log(`${done.length}/${ids.length} batches labelled, ${done.reduce((n, r) => n + r.count, 0)} memos`)
return { finished: done.length, memos: done.reduce((n, r) => n + r.count, 0) }
