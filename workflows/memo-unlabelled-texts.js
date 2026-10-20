export const meta = {
  name: 'memo-unlabelled-texts',
  description: 'Write ~30k extra unlabelled memo texts for teacher-to-student distillation',
  phases: [{ title: 'Write', detail: 'one writer per brief, text only' }],
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

const ids = Array.from({ length: args.count }, (_, i) => `${args.prefix}${String(i).padStart(3, '0')}`)

const writePrompt = (id) => `You write realistic memo texts for training a tiny on-device model that reads short personal notes (typed or dictated right after talking to someone) and extracts people, relations, interests, events, dates, facts and requested follow-ups. You write text only; nobody labels these by hand, a trained model will.

1. Skim the labelling spec ${SPEC}, especially "Special cases" and "Do not label", so your memos exercise what the model must handle.
2. Read your brief: the object with "id": "${id}" in ${ROOT}/${args.file}. It gives n, the writing style, three topics, two date styles to emphasise, the first names you may use, and a few surnames.
3. Write n distinct memos in that style:
   - They read like real notes-app or voice-memo entries written straight after a conversation, call or message. Vary openings, structure, tone and length; never fall into a template, and avoid stock openers like "Remind me to" or "Spoke to" for more than a few memos.
   - Length: most 8-45 words, about 1 in 6 between 45 and 110 words, none over 120 words.
   - Mix: about 30% contain an explicit request ("remind me to", "I should", "need to", "don't forget to", "must"); about 45% only mention events and facts; about 15% are facts or interests only; about 10% have no other person (errands, the user's own plans) or nothing worth labelling.
   - People: first names only from the brief's list (occasionally add a surname, a title like Dr/Mrs/Uncle, or a nickname). Use 2-4 people in some memos, repeat names, refer back with pronouns, and include unnamed relatives (her mum, his boss, their kids) and named ones (her brother Sam).
   - Across the set, include each of these in a few memos: a name inside a request, a nickname after a full name, a pet, a couple sharing an event, a cancelled event, the user's own plans stated as fact, a follow-up about something that already happened, someone nervous or struggling, a relative's event, a gift hint, several time expressions in one memo.
   - Time expressions: lean on the brief's date styles but vary widely; about 20% of memos have none.
   - Only the memo text: no labels, notes or commentary inside it.
4. Write ${RAW}/${id}.txt.jsonl with one {"id": "${id}-001", "text": "..."} per line, ids numbered in order.
5. Run \`${VALIDATE} --texts-only ${RAW}/${id}.txt.jsonl\` and fix every error until it prints OK.

Return the count and a one-line note.`

const results = await parallel(ids.map((id) => () => agent(writePrompt(id), { label: `write:${id}`, phase: 'Write', schema: WRITE_RESULT, effort: 'medium' })))
const done = results.filter(Boolean)
log(`${done.length}/${ids.length} writers finished, ${done.reduce((n, r) => n + r.count, 0)} memos`)
return { finished: done.length, memos: done.reduce((n, r) => n + r.count, 0) }
