export const meta = {
  name: 'memo-data-v2',
  description: 'Write memos, label them twice blind against spec v2, adjudicate disagreements',
  phases: [
    { title: 'Write', detail: 'one writer per brief produces memo text only' },
    { title: 'Label', detail: 'two independent blind annotators per brief' },
    { title: 'Adjudicate', detail: 'resolve every disagreement against the spec' },
  ],
}

const ROOT = '/home/zack/Source/memo-extract'
const RAW = `${ROOT}/data/raw`
const SPEC = `${ROOT}/docs/labeling.md`
const VALIDATE = `python3 ${ROOT}/tools/validate.py`

const WRITE_RESULT = {
  type: 'object',
  properties: { count: { type: 'integer' }, note: { type: 'string' } },
  required: ['count', 'note'],
}
const LABEL_RESULT = {
  type: 'object',
  properties: {
    count: { type: 'integer' },
    ambiguities: { type: 'string', description: 'spec rules you found ambiguous, with memo ids; empty if none' },
  },
  required: ['count', 'ambiguities'],
}
const ADJ_RESULT = {
  type: 'object',
  properties: {
    agreed: { type: 'integer' },
    disagreed: { type: 'integer' },
    dropped: { type: 'integer' },
    a_right: { type: 'integer' },
    b_right: { type: 'integer' },
    neither: { type: 'integer' },
    common_errors: { type: 'string' },
    spec_fixes: { type: 'string', description: 'concrete spec rewordings that would have prevented the disagreements; empty if none' },
  },
  required: ['agreed', 'disagreed', 'dropped', 'a_right', 'b_right', 'neither', 'common_errors', 'spec_fixes'],
}

const writePrompt = (item) => `You write realistic memo texts for training a tiny on-device model that reads short personal notes (typed or dictated right after talking to someone) and extracts people, relations, interests, events, dates, facts and requested follow-ups. You write text only; other agents label it.

1. Skim the labelling spec ${SPEC}, especially "Special cases" and "Do not label", so your memos exercise what the model must handle.
2. Read your brief: the object with "id": "${item.id}" in ${ROOT}/${item.file}. It gives n, the writing style, three topics, two date styles to emphasise, the first names you may use, and a few surnames.
3. Write n distinct memos in that style:
   - They read like real notes-app or voice-memo entries written straight after a conversation, call or message. Vary openings, structure, tone and length; never fall into a template.
   - Length: most 8-45 words, about 1 in 6 between 45 and 110 words, none over 120 words.
   - Mix: about 30% contain an explicit request ("remind me to", "I should", "need to", "don't forget to", "must"); about 45% only mention events and facts; about 15% are facts or interests only; about 10% have no other person (errands, the user's own plans) or nothing worth labelling.
   - People: first names only from the brief's list (occasionally add a surname, a title like Dr/Mrs/Uncle, or a nickname). Use 2-4 people in some memos, repeat names, refer back with pronouns, and include unnamed relatives (her mum, his boss, their kids) and named ones (her brother Sam).
   - Across the set, include each of these in a few memos: a name inside a request ("remind me to ask Kofi how it went"), a nickname or short form after a full name, a pet, a couple or family sharing an event, a cancelled or called-off event, the user's own plans stated as fact, a follow-up about an event that already happened, someone nervous or struggling, a relative's event, a gift hint, several time expressions in one memo.
   - Time expressions: lean on the brief's date styles but vary widely; about 20% of memos have none.
   - Spread the three topics across the set, plus some off-topic memos.
   - Only the memo text: no labels, notes or commentary inside it.
4. Write ${RAW}/${item.id}.txt.jsonl with one {"id": "${item.id}-001", "text": "..."} per line, ids numbered in order.
5. Run \`${VALIDATE} --texts-only ${RAW}/${item.id}.txt.jsonl\` and fix every error until it prints OK.

Return the count and a one-line note.`

const labelPrompt = (item, mine, theirs) => `You are annotator "${mine}" for a memo-extraction dataset. Another annotator labels the same memos independently, so never open ${RAW}/${item.id}.${theirs}.jsonl or any other annotation file under ${RAW}.

1. Read the labelling spec ${SPEC} in full. It is the source of truth; when two readings are defensible, follow the rule the spec points to.
2. Read the memos in ${RAW}/${item.id}.txt.jsonl.
3. Label every memo, keeping each id and text byte-for-byte identical. Write ${RAW}/${item.id}.${mine}.jsonl, one {"id", "text", "spans"} per line, in the same order.
4. Run \`${VALIDATE} ${RAW}/${item.id}.${mine}.jsonl\` and fix every error until it prints OK.
5. Re-read every record against the spec and fix what is wrong, then re-validate. Check especially: FACT scope (durable details and every stated feeling; intensifiers dropped, softeners kept; nothing situational or resolved), EVENT boundaries (noun phrase, identifying complement kept) and event_type, the followup table (first matching row wins; nervous/struggling means the owner), deaths owned by the bereaved, shared events, ACTION only for explicit requests or to-dos (not the user's stated plans), action_type by purpose then verb, timing (past events are after), DATE boundaries (drop only on/at/@/for), anchors (dates to the event or action they time; actions to the event their time is relative to), pointers to first mentions, same owner and pronoun on every mention, same_as for nicknames, pets as FACT.

Return the number of memos labelled and any spec ambiguities you hit.`

const adjPrompt = (item) => `You are the adjudicator for a memo-extraction dataset. Two annotators labelled the same memos independently: ${RAW}/${item.id}.a.jsonl and ${RAW}/${item.id}.b.jsonl.

1. Read the labelling spec ${SPEC} in full. It is the source of truth; when it is silent, choose what best serves the product (suggesting details to save and follow-up reminders to confirm) and say so in spec_fixes.
2. Run \`python3 ${ROOT}/tools/compare.py ${RAW}/${item.id}.a.jsonl ${RAW}/${item.id}.b.jsonl\`. The first line is a summary; each further line is one disagreement with both versions ("first" is a, "second" is b) and the kinds of difference.
3. For every disagreement decide the correct labelling: take one version, merge them, or fix both. Read the full records from the two files when needed. Drop a memo only if it is unrealistic, incoherent or impossible to label consistently.
4. Write ${RAW}/${item.id}.adj.jsonl with exactly one line per disagreed id: the full correct record ({"id", "text", "spans"}, text unchanged) or {"id": ..., "drop": true, "reason": "..."}.
5. Run \`${VALIDATE} --allow-drop ${RAW}/${item.id}.adj.jsonl\` and fix every error until it prints OK. Check that every disagreed id from step 2 has a line.

Return the counts, which side was right how often, the recurring errors, and concrete spec fixes.`

const results = await pipeline(
  args.items,
  (item) => agent(writePrompt(item), { label: `write:${item.id}`, phase: 'Write', schema: WRITE_RESULT, effort: 'medium' }),
  (written, item) => {
    if (!written) throw new Error(`writer failed for ${item.id}`)
    return parallel([
      () => agent(labelPrompt(item, 'a', 'b'), { label: `label-a:${item.id}`, phase: 'Label', schema: LABEL_RESULT, effort: 'high' }),
      () => agent(labelPrompt(item, 'b', 'a'), { label: `label-b:${item.id}`, phase: 'Label', schema: LABEL_RESULT, effort: 'high' }),
    ]).then(([a, b]) => ({ written, a, b }))
  },
  (prev, item) => {
    if (!prev.a || !prev.b) throw new Error(`labelling failed for ${item.id}`)
    return agent(adjPrompt(item), { label: `adj:${item.id}`, phase: 'Adjudicate', schema: ADJ_RESULT, effort: 'high' }).then((adj) => ({ id: item.id, prev, adj }))
  },
)

const done = results.filter(Boolean)
log(`${done.length}/${args.items.length} briefs completed`)
return done.map((r) => ({
  id: r.id,
  count: r.prev.written.count,
  agreed: r.adj?.agreed,
  disagreed: r.adj?.disagreed,
  dropped: r.adj?.dropped,
  a_right: r.adj?.a_right,
  b_right: r.adj?.b_right,
  spec_fixes: (r.adj?.spec_fixes || '').slice(0, 600),
  ambiguities: [(r.prev.a?.ambiguities || '').slice(0, 300), (r.prev.b?.ambiguities || '').slice(0, 300)],
}))
