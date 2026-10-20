export const meta = {
  name: 'memo-data-pilot',
  description: 'Generate, independently relabel and adjudicate synthetic labelled memos for the tiny memo-extraction model',
  phases: [
    { title: 'Generate', detail: 'one agent per brief writes and labels memos' },
    { title: 'Relabel', detail: 'an independent annotator labels the same texts blind' },
    { title: 'Adjudicate', detail: 'resolve every disagreement against the spec' },
  ],
}

const ROOT = '/home/zack/Source/memo-extract'
const RAW = `${ROOT}/data/raw`
const SPEC = `${ROOT}/docs/labeling.md`
const BRIEFS = `${ROOT}/${args.briefsFile}`
const VALIDATE = `python3 ${ROOT}/tools/validate.py`

const ANNOTATION_RESULT = {
  type: 'object',
  properties: {
    count: { type: 'integer' },
    ambiguities: { type: 'string', description: 'spec rules you found ambiguous while labelling, with the memo ids that hit them; empty if none' },
  },
  required: ['count', 'ambiguities'],
}

const ADJUDICATION_RESULT = {
  type: 'object',
  properties: {
    agreed: { type: 'integer' },
    disagreed: { type: 'integer' },
    dropped: { type: 'integer' },
    first_was_right: { type: 'integer', description: 'disagreements where the first (generator) labelling was fully correct' },
    second_was_right: { type: 'integer', description: 'disagreements where the second (blind) labelling was fully correct' },
    neither: { type: 'integer', description: 'disagreements where you had to fix or merge' },
    common_errors: { type: 'string', description: 'the recurring mistakes, most frequent first, with example ids' },
    spec_fixes: { type: 'string', description: 'concrete rewordings or added rules for docs/labeling.md that would have prevented the disagreements; empty if none' },
  },
  required: ['agreed', 'disagreed', 'dropped', 'first_was_right', 'second_was_right', 'neither', 'common_errors', 'spec_fixes'],
}

const genPrompt = (id) => `You are generating training data for a tiny on-device model that reads short personal memos (typed or dictated after talking to someone) and extracts people, relations, interests, events, dates, facts and requested follow-ups.

1. Read the labelling spec ${SPEC} in full. It is the source of truth for span types, boundaries, attributes and pointers.
2. Read your brief: the object with "id": "${id}" in ${BRIEFS}. It gives how many memos to write (n), the writing style, three topics to focus on, two date styles to emphasise, the first names you may use, and a few surnames.
3. Write n distinct, realistic memos in that style. Requirements:
   - They should read like real notes-app or voice-memo entries written right after a conversation, call or message. Vary openings, structure and length; never fall into a template. Do not reuse or paraphrase the spec's worked examples.
   - Length: most 8-45 words, about 1 in 6 between 45 and 110 words, none over 120 words.
   - Mix across the set: about 30% contain an explicit request ("remind me to", "I should", "need to", "don't forget to", "must"); about 45% only mention events and facts with no request; about 15% are facts or interests only with no event; about 10% have no other person at all (errands, the user's own plans) or nothing worth labelling.
   - People: first names only from the brief's list (add a brief surname, title like Dr/Mrs/Uncle, or nickname occasionally). Use 2-4 people in some memos, repeat a person's name within a memo sometimes, refer back with pronouns, and include unnamed relatives (her mum, his boss, their kids) and named ones (her brother Sam).
   - Time expressions: lean on the brief's date styles but use a wide variety overall; roughly 20% of memos have none.
   - Spread the three topics across the set, with some memos off-topic for variety.
4. Label every memo exactly per the spec. Write all of them to ${RAW}/${id}.gen.jsonl, one JSON object per line, ids "${id}-001", "${id}-002", ... in order. Each line: {"id", "text", "spans"}. Copy span text character-for-character from the memo.
5. Run \`${VALIDATE} ${RAW}/${id}.gen.jsonl\` and fix every error it reports, rerunning until it prints OK.
6. Re-read your file against the spec once more, paying particular attention to: pointers going to the first mention, pronoun resolution for owner, EVENT followup defaults, ACTION timing, and DATE spans not including a leading on/at/by. Fix and re-validate.

Return the number of memos written and any spec ambiguities you hit.`

const labPrompt = (id) => `You are an independent second annotator for a memo-extraction dataset. Another annotator already labelled these memos; you must NOT look at their labels, so never open ${RAW}/${id}.gen.jsonl or any other *.jsonl under ${RAW} except the file you write.

1. Read the labelling spec ${SPEC} in full. It is the source of truth.
2. Run \`python3 ${ROOT}/tools/texts.py ${RAW}/${id}.gen.jsonl\` to print the memo ids and texts (labels are stripped).
3. Label every memo exactly per the spec, keeping each id and text byte-for-byte identical. Write them to ${RAW}/${id}.lab.jsonl, one JSON object per line ({"id", "text", "spans"}), in the same order.
4. Run \`${VALIDATE} ${RAW}/${id}.lab.jsonl\` and fix every error until it prints OK.
5. Re-read your labels against the spec once more (first-mention pointers, pronoun resolution, EVENT followup defaults, ACTION timing, DATE boundaries) and fix anything wrong, then re-validate.

Return the number of memos labelled and any spec ambiguities you hit.`

const adjPrompt = (id) => `You are the adjudicator for a memo-extraction dataset. Two annotators labelled the same memos independently: ${RAW}/${id}.gen.jsonl (first) and ${RAW}/${id}.lab.jsonl (second).

1. Read the labelling spec ${SPEC} in full. It is the source of truth; when the spec is silent, choose what best serves the product (suggesting saved details and follow-up reminders from the memo).
2. Run \`python3 ${ROOT}/tools/compare.py ${RAW}/${id}.gen.jsonl ${RAW}/${id}.lab.jsonl\`. The first line is a summary; each further line is one disagreement with both versions and the kinds of difference.
3. For every disagreement, decide the correct labelling: take one version, merge them, or fix both. Read the full records from the two files when you need them. Drop a memo only if it is unrealistic, incoherent, or impossible to label consistently.
4. Write ${RAW}/${id}.adj.jsonl with exactly one line per disagreed id: either the full correct record ({"id", "text", "spans"}, text unchanged) or {"id": ..., "drop": true, "reason": "..."}.
5. Run \`${VALIDATE} --allow-drop ${RAW}/${id}.adj.jsonl\` and fix every error until it prints OK. Check that every disagreed id from step 2 has a line.

Return the counts, which side was right how often, the recurring errors, and concrete spec fixes.`

const results = await pipeline(
  args.ids,
  (id) => agent(genPrompt(id), { label: `gen:${id}`, phase: 'Generate', schema: ANNOTATION_RESULT }),
  (gen, id) => {
    if (!gen) throw new Error(`generator failed for ${id}`)
    return agent(labPrompt(id), { label: `lab:${id}`, phase: 'Relabel', schema: ANNOTATION_RESULT }).then((lab) => ({ gen, lab }))
  },
  (prev, id) => {
    if (!prev.lab) throw new Error(`relabel failed for ${id}`)
    return agent(adjPrompt(id), { label: `adj:${id}`, phase: 'Adjudicate', schema: ADJUDICATION_RESULT, effort: 'high' }).then((adj) => ({ id, ...prev, adj }))
  },
)

const done = results.filter(Boolean)
log(`${done.length}/${args.ids.length} briefs completed`)
return done
