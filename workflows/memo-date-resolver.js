export const meta = {
  name: 'memo-date-resolver',
  description: 'Implement the deterministic date resolver, write independent spec tests, then reconcile until green',
  phases: [
    { title: 'Build', detail: 'implementer and independent spec tester work in parallel' },
    { title: 'Reconcile', detail: 'run both suites, fix whichever side contradicts the spec' },
  ],
}

const ROOT = '/home/zack/Source/memo-extract'
const SPEC = `${ROOT}/docs/dates.md`
const PYTEST = `cd ${ROOT} && .venv/bin/python -m pytest -q`

const RESULT = {
  type: 'object',
  properties: {
    files: { type: 'array', items: { type: 'string' } },
    tests: { type: 'integer', description: 'number of test cases written or passing' },
    failing: { type: 'integer' },
    notes: { type: 'string', description: 'spec gaps, judgement calls, and anything left unresolved' },
  },
  required: ['files', 'tests', 'failing', 'notes'],
}

const implement = `Implement the date resolver specified in ${SPEC} (read it in full first).

- Write ${ROOT}/memo_extract/dates.py: standard library only, no third-party imports. Ordered regex rules plus date arithmetic, structured so each rule is a small function and the module stays easy to port to Swift/Kotlin. Put named constants (default offsets, month/weekday/number-word tables, holiday dates) at the top of the module.
- Match the surrounding code in ${ROOT}/memo_extract (read constants.py and records.py for style): guard clauses with early returns, short docstrings only where the why is non-obvious, no try/except for control flow.
- Write ${ROOT}/tests/test_dates.py: table-driven pytest cases covering every rule in the spec, with today = Monday 19 October 2026 and a second table with today = Saturday 26 December 2026, plus anchored cases with exact and range anchors.
- Run \`${PYTEST} tests/test_dates.py\` and iterate until it passes. Do not create or edit any other test file (another agent is writing tests/test_dates_spec.py in parallel).

Return the files you wrote, how many test cases pass, how many fail, and any spec gaps or judgement calls.`

const specTests = `You are writing an independent, adversarial acceptance suite for a date resolver from its spec alone. Another agent is implementing ${ROOT}/memo_extract/dates.py in parallel; do NOT read that file or ${ROOT}/tests/test_dates.py.

- Read ${SPEC} in full. Write ${ROOT}/tests/test_dates_spec.py: table-driven pytest cases that pin down what the spec says, especially the edges an implementer is likely to get wrong: weekday semantics (bare / this / next / last / "Friday week") on every weekday relative to today, year rollover for calendar dates and holidays, day_first numeric dates both ways and impossible combinations, month-end clamping for "in a month", approximate-count ranges, weekend logic when today is Saturday or Sunday, anaphoric expressions with and without an anchor and with exact vs range anchors, times with and without am/pm (including the ambiguous flag), dictated forms ("the fourteenth of may", "half past nine", number words), abbreviations ("tmrw", "thurs", "nxt wk"), leading fillers and prepositions, vague expressions, and inputs that must come back "unparsed" rather than raising.
- Use today = Monday 19 October 2026 for most cases and also Saturday 26 December 2026 and Sunday 1 March 2026. Import with \`from memo_extract.dates import Resolution, resolve\`. Compare whole Resolution objects where the spec fully determines them; otherwise assert only the fields the spec determines.
- Every expected value must follow from the spec text; put a short comment on any case where you had to interpret the spec.
- You cannot run the suite against a real implementation yet; just make sure the file imports cleanly when dates.py exists (\`${PYTEST} --collect-only tests/test_dates_spec.py\` may fail with ImportError until then, which is fine).

Return the file you wrote, the number of cases, 0 for failing, and the spec interpretations you made.`

const reconcile = (impl, spec) => `Two agents worked from the date-resolver spec ${SPEC} independently: one implemented ${ROOT}/memo_extract/dates.py with tests/test_dates.py, the other wrote an acceptance suite tests/test_dates_spec.py without seeing the implementation.

Implementer notes: ${impl?.notes ?? '(none)'}
Spec-tester notes: ${spec?.notes ?? '(none)'}

1. Read ${SPEC} in full.
2. Run \`${PYTEST} tests/test_dates.py tests/test_dates_spec.py\`.
3. For each failure decide which side contradicts the spec. Fix the implementation when it does; fix the test only when the test's expectation does not follow from the spec, and leave a one-line comment saying why. When the spec is genuinely silent, pick the behaviour that is most useful for suggesting reminders, make both suites agree, and add the clarification to ${SPEC}.
4. Repeat until both suites pass. Keep dates.py standard-library only and readable; if a fix makes a rule convoluted, restructure the rule instead.

Return the files you changed, the final number of passing tests, failures left (should be 0), and a summary of each judgement call and spec clarification.`

phase('Build')
const [impl, spec] = await parallel([
  () => agent(implement, { label: 'implement dates.py', phase: 'Build', schema: RESULT }),
  () => agent(specTests, { label: 'spec tests', phase: 'Build', schema: RESULT }),
])

phase('Reconcile')
const result = await agent(reconcile(impl, spec), { label: 'reconcile', phase: 'Reconcile', schema: RESULT, effort: 'high' })
return { impl, spec, result }
