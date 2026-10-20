# Date resolver spec

`memo_extract/dates.py` turns the text of one `DATE` span into dates, deterministically, with no ML and no dependencies beyond the Python standard library. It must stay simple enough to port to Swift and Kotlin, so it uses ordered regex rules and plain date arithmetic, not a general parser.

## Interface

```python
from datetime import date
from memo_extract.dates import Resolution, resolve

resolve(text: str, today: date, anchor: Resolution | None = None, day_first: bool = True) -> Resolution
```

`text` is the span text exactly as labelled (any case, dictated or typed, may contain fillers like "um" or punctuation). `today` is the memo's date. `anchor` is the already-resolved date of the event this expression is relative to, if any. `day_first` decides `5/6` style numeric dates.

```python
@dataclass(frozen=True)
class Resolution:
    kind: str  # "exact" | "range" | "vague" | "unparsed"
    start: date | None = None  # first possible day
    end: date | None = None  # last possible day, inclusive; equals start for "exact"
    time: str | None = None  # "HH:MM" 24h when a clock time is given
    part_of_day: str | None = None  # "morning" | "afternoon" | "evening" | "night"
    relation: str | None = None  # "before" | "after" when the expression means before/after its reference
    anaphoric: bool = False  # True when the expression is relative to an event, not to today
    ambiguous: bool = False  # True when a reasonable reader could pick another date
```

- `exact`: one day (`start == end`).
- `range`: a span of days (`next week`, `in March`, `early June`, `this weekend`).
- `vague`: a time expression with no usable date (`soon`, `at some point`, `sometime`, `later`). `start`/`end` are None unless the expression also bounds it.
- `unparsed`: nothing recognised. Never raise.
- A pure time or part of day with no date (`at 3pm`, `in the morning`) is `exact` on `anchor`'s start if an anchor is given and `anaphoric=True`, otherwise `exact` on `today`.
- Anaphoric expressions with no `anchor` return `kind="unparsed"`, `anaphoric=True` (and `relation` / `time` / `part_of_day` filled where known), so the caller knows it needs the event's date.
- Anaphoric expressions resolve against `anchor.start` for "before" relations and `anchor.end` for "after" relations ("check in afterwards" on an event `range` 26 Oct–1 Nov → 2 Nov). If the anchor is a `range`, the result is `range` and `ambiguous=True` unless the offset collapses it.

## What must be understood

Everything is case-insensitive and should tolerate leading fillers and prepositions ("um", "uh", "like", "so", "on", "at", "for", "around", "about"; a leading "by" is a deadline, see **Before/after a date**), trailing punctuation, and common abbreviations (`tmrw`, `tmw`, `tomoz`, `2moro`, `tues`, `weds`, `thurs`, `sat`, `sept`, `wk`, `nxt`, `wknd`, `eve`, `mon`, `fri`).

Weeks start on Monday.

**Deictic days**: `today`, `tonight` (today, night), `this morning/afternoon/evening`, `tomorrow` (+ morning/afternoon/evening/night), `the day after tomorrow`, `yesterday`, `last night`.

**Weekdays** (`Friday`, `fri`, `on Friday`):
- bare weekday: the next occurrence strictly after today.
- `this Friday`: the occurrence in the current Monday–Sunday week if it is today or later, otherwise next week's; `ambiguous=False`.
- `next Friday`: the occurrence in next Monday–Sunday week, `ambiguous=True`.
- `Friday week` / `a week on Friday`: the bare weekday + 7 days.
- `last Friday`: the most recent occurrence strictly before today.
- weekday + part of day or time: `Friday morning`, `Friday at 3pm`, `fri 3pm`.

**Calendar dates**:
- `14 May`, `14th May`, `14th of May`, `May 14`, `May 14th`, `the fourteenth of may`, `may fourteenth`, `14 May 2027`, `May 14, 2027`, `2 November 2026`.
- numeric `14/05`, `14/5`, `14.05`, `14/05/2027`, `14/05/27`, `5/14`: read in the configured order (day/month when `day_first` is True, month/day when False), and swap only when that order puts a number above 12 in the month slot (`14/05` and `5/14` are both 14 May). If neither order is a real date (`31/06`, `13/13`) it is `unparsed`. A numeric date is not `ambiguous`: `day_first` settles `5/6`. Two-digit years are 20YY.
- `the 3rd`, `the 14th`, `the fourteenth`: that day of the current month if it is today or later, otherwise next month.
- Without a year, a calendar date is the next occurrence on or after today (a reminder app is future-biased). With a year, use it as given.
- Invalid dates (`31 June`) are `unparsed`.

**Months and seasons**: `March`, `in March` (range over the whole month, next occurrence: the current month counts), `early March` (1–10), `mid March`/`mid-March` (11–20), `late March`/`end of March` (21–last day), `March 2027`, `next month`, `this month`, `end of the month` / `end of next month` (21–last), `beginning of next month` (1–10), `spring` (Mar–May), `summer` (Jun–Aug), `autumn`/`fall` (Sep–Nov), `winter` (Dec–Feb), with `this`/`next`/`over the`/`in the` variants. Northern hemisphere.

**Weeks and weekends**: `this week` (today–Sunday), `next week` (next Monday–Sunday), `the week after next`, `later this week` (tomorrow–Sunday), `this weekend` (the coming Saturday–Sunday; if today is Saturday or Sunday, this weekend), `next weekend` (the weekend after the coming one, `ambiguous=True`), `end of the week` (Friday–Sunday of this week), `sometime next week` (same range as `next week`).

**Offsets from today**: `in 3 days`, `in three days`, `in a week`, `in 2 weeks`, `in a fortnight`, `in a month` (same day next month, clamped to month end), `in six months` → `exact`. Approximate counts (`a couple of`, `couple`, `a few`, `few`, `several`) → `range`: days ±1, weeks ±3 days, months ±7 days around the nominal value (couple = 2, few = 3, several = 4).

**Holidays**: `Christmas`/`Xmas`/`Christmas Day` (25 Dec), `Christmas Eve` (24 Dec), `Boxing Day` (26 Dec), `New Year's Eve` (31 Dec), `New Year's Day`/`New Year` (1 Jan), `Valentine's`/`Valentine's Day` (14 Feb), `Halloween` (31 Oct), `Easter`/`Easter Sunday` (computed, Gregorian), `bonfire night` (5 Nov). Next occurrence on or after today. `after Christmas` → `relation="after"`, `range` 26–31 Dec. `before Christmas` → `relation="before"`, `range` from today to 24 Dec.

**Times**: `3pm`, `3 pm`, `3:30pm`, `15:00`, `at 3`, `at half 9`, `half past nine`, `quarter past 2`, `quarter to 5`, `noon`, `midday`, `midnight`, `9 in the morning`, `three thirty`. Bare hours with no am/pm: 7–11 are am, 12 is noon, 1–6 are pm, and `ambiguous=True`. `lunchtime` → `time="12:30"`, `part_of_day="afternoon"`. Parts of day: `morning`, `afternoon`, `evening`, `night`, `tonight`. A time alone sets `time`/`part_of_day` and resolves its date as described above.

**Anaphoric (needs `anchor`)**: `that morning/afternoon/evening/night/day`, `on the day`, `the morning of`, `the night before` (−1 day, night), `the day before`, `the day after`, `the next day`, `the following day`, `the week before` (range of the 7 days before), `the week after` (range of the 7 days after), `a week before/after`, `N days before/after`, `two weeks after`, `afterwards`, `after`, `after it`, `after that`, `once it's done` (`relation="after"`, `exact` = anchor end + 1 day), `beforehand`, `before`, `before then` (`relation="before"`, `exact` = anchor start − 1 day).

**Vague**: `soon`, `at some point`, `sometime`, `later`, `one day`, `when I can`, `eventually`, `in a bit` → `vague`. A vague word plus a resolvable part (`sometime next week`, `at some point in March`) resolves the resolvable part as a `range` (not `vague`).

**Before/after a date**: `before Friday` → `relation="before"`, `range` from today to the day before Friday. `after Friday` / `after the 14th` → `relation="after"`, `exact` the day after. `by Friday` → treat like `before Friday` but include Friday.

**Past expressions** (`yesterday`, `last week`, `last Friday`, `on Monday` when used in the past is not detectable, so ignore tense): `last week` is the previous Monday–Sunday range.

## Clarifications

Readings both test suites agree on where the rules above are silent or could be read two ways.

- **Next occurrence**: a part of a month (`early October`) or a season is the next one that has not ended yet; on 19 Oct `early October` is 2027 and `summer` is 2027. `next <month or season>` is the first one not yet started; `last <month or season>` is the latest one already over. Neither is `ambiguous`. `29 February` with no year is the next leap year's; with a non-leap year it is `unparsed`. `the 31st` skips to the next month that has one.
- **Weeks**: `this weekend` and `end of the week` are taken literally (Sat–Sun, Fri–Sun of this week) even when part has passed. A range that collapses to one day is `exact` (`later this week` on Saturday is Sunday; `this week` and `later this week` on Sunday are Sunday).
- **Relation**: `relation` is set on every before/after phrase, anaphoric ones included (`the day before`, `the night before`, `the next day`, `N days after`), and `by X` is `relation="before"`. `the day after tomorrow` has no relation. `before`/`after`/`by` with only a clock time (`after 3pm`) stays on today (or the anchor's day) with the relation set.
- **Anchors**: a before/after phrase on a `range` anchor counts from its first/last day and is `exact`, not `ambiguous`. A phrase with no direction (`that day`, `on the day`, `that morning`) returns the anchor's range with `ambiguous=True`. A time or part of day alone on a `range` anchor is `exact` on its first day with `ambiguous=True`. An `ambiguous` anchor makes the result `ambiguous`. An anchor with no `start` (`vague`, `unparsed`) counts as no anchor.
- **Vague**: a vague word plus a part that resolves to one day stays `exact` (`sometime tomorrow`). `one day` is vague; `in one day` is +1 day.
- **Times**: a part of day settles a bare hour (`7 in the evening` is 19:00, not ambiguous). Two-digit-hour times (`09:30`, `15:00`) are 24h and not ambiguous; `9:30`, `at 6:45` and `three thirty` follow the bare-hour rule. `half 9` is 09:30. `12am` and `12 at night` are 00:00. Holiday names set no `part_of_day` (`Christmas Eve` is not an evening).
- **Tolerated input**: fillers can chain and carry commas (`um, so on friday`), apostrophes may be missing or curly, and rule words only match as whole words (`fridge`, `sunny`, `wedding` are `unparsed`).

## Tests

`tests/test_dates.py` covers every rule above with a fixed `today` (use Monday 19 October 2026, and a second suite on Saturday 26 December 2026 to exercise year rollover and weekend logic), including anchors that are `exact` and `range`.
