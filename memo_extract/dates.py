"""Resolve the text of one DATE span to dates with ordered regex rules and plain date arithmetic (docs/dates.md).

Standard library only, so the rules port directly to Swift and Kotlin. `resolve` normalises the text, takes out
any clock time and part of day, then tries RULES in order: each rule gets the remaining phrase and a Context and
returns a Resolution, or None to let the next rule try.
"""

import calendar
import re
from dataclasses import dataclass, replace
from datetime import date, timedelta

DAY = timedelta(days=1)
WEEK = timedelta(days=7)
MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 24 * MINUTES_PER_HOUR
MONTHS_PER_YEAR = 12
HALF_DAY_HOURS = 12
MAX_MONTH_DAY = 31

WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
SATURDAY_OFFSET = WEEKDAYS["saturday"] * DAY
SUNDAY_OFFSET = WEEKDAYS["sunday"] * DAY
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

ABBREVIATIONS = {
    "tmrw": "tomorrow",
    "tmw": "tomorrow",
    "tomoz": "tomorrow",
    "2moro": "tomorrow",
    "2morrow": "tomorrow",
    "mon": "monday",
    "tue": "tuesday",
    "tues": "tuesday",
    "wed": "wednesday",
    "weds": "wednesday",
    "thu": "thursday",
    "thur": "thursday",
    "thurs": "thursday",
    "fri": "friday",
    "sat": "saturday",
    "sun": "sunday",
    "jan": "january",
    "feb": "february",
    "mar": "march",
    "apr": "april",
    "jun": "june",
    "jul": "july",
    "aug": "august",
    "sep": "september",
    "sept": "september",
    "oct": "october",
    "nov": "november",
    "dec": "december",
    "wk": "week",
    "wks": "weeks",
    "wknd": "weekend",
    "nxt": "next",
    "eve": "evening",
    "xmas": "christmas",
}
# "eve" after one of these names a holiday ("christmas eve", "new years eve"), not an evening
HOLIDAY_EVES = {"christmas", "year", "years"}

CARDINALS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
ORDINALS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "thirtieth": 30,
}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
NUMBER_WORDS = CARDINALS | TENS
UNIT_CARDINALS = {word: n for word, n in CARDINALS.items() if n < 10}
UNIT_ORDINALS = {word: n for word, n in ORDINALS.items() if n < 10}
# digits stand in for an ordinal word; the rules only check that some suffix is there
ORDINAL_MARK = "th"

LEADING_FILLERS = {"um", "umm", "uh", "uhh", "erm", "er", "like", "so", "and", "on", "at", "for", "around", "about", "over", "during"}

VAGUE_PHRASES = {
    "soon",
    "some point",
    "sometime",
    "some time",
    "later",
    "later on",
    "1 day",  # "one day" after number words become digits
    "someday",
    "some day",
    "when i can",
    "eventually",
    "in a bit",
    "in a while",
}
# vague words that may wrap a resolvable part: "sometime next week", "at some point in march", "next week sometime"
VAGUE_AFFIXES = ("at some point", "some point", "sometime", "some time", "soon", "later", "eventually")

DEICTIC_DAYS = {
    "today": 0,
    "tomorrow": 1,
    "the day after tomorrow": 2,
    "day after tomorrow": 2,
    "yesterday": -1,
    "the day before yesterday": -2,
    "day before yesterday": -2,
}

# days from the anchor; 0 is the anchor itself, negative counts from its first day, positive from its last
ANAPHORIC_PHRASES = {
    "that day": 0,
    "the day": 0,
    "the day of": 0,
    "the same day": 0,
    "same day": 0,
    "beforehand": -1,
    "before": -1,
    "before then": -1,
    "before it": -1,
    "before that": -1,
    "afterwards": 1,
    "afterward": 1,
    "after": 1,
    "after it": 1,
    "after that": 1,
    "after then": 1,
    "once its done": 1,
    "once it is done": 1,
    "once its over": 1,
    "the next day": 1,
    "next day": 1,
    "the following day": 1,
    "following day": 1,
}
# words that stand for the anchor after "N days before/after"
ANAPHORIC_REFERENCES = {"it", "that", "then"}

EXACT_COUNTS = {"a": 1, "an": 1}
APPROX_COUNTS = {"a couple of": 2, "couple of": 2, "a couple": 2, "couple": 2, "a few": 3, "few": 3, "several": 4}
UNIT_DAYS = {"day": 1, "week": 7, "fortnight": 14}
UNIT_MONTHS = {"month": 1, "year": 12}
# half-width of the range around the nominal day for approximate counts ("a few weeks")
APPROX_SLACK_DAYS = {"day": 1, "week": 3, "fortnight": 3, "month": 7, "year": 30}

WHOLE_MONTH = (1, MAX_MONTH_DAY)  # the last day clamps to the month's length
MONTH_PARTS = {
    "early": (1, 10),
    "beginning of": (1, 10),
    "start of": (1, 10),
    "mid": (11, 20),
    "middle of": (11, 20),
    "late": (21, MAX_MONTH_DAY),
    "end of": (21, MAX_MONTH_DAY),
}
# days after Monday
WEEK_PARTS = {
    "early": (0, 1),
    "beginning of": (0, 1),
    "start of": (0, 1),
    "mid": (2, 3),
    "middle of": (2, 3),
    "late": (4, 6),
    "end of": (4, 6),
}
SEASONS = {"spring": (3, 5), "summer": (6, 8), "autumn": (9, 11), "fall": (9, 11), "winter": (12, 2)}  # northern hemisphere
RELATIVE_STEPS = {None: 0, "this": 0, "coming": 0, "this coming": 0, "next": 1, "last": -1}
# years either side of today searched for the season or month a phrase names ("last winter" in February is two back)
SEARCH_YEARS_AROUND = 2

FIXED_HOLIDAYS = {
    "christmas": (12, 25),
    "christmas day": (12, 25),
    "christmas eve": (12, 24),
    "boxing day": (12, 26),
    "new years eve": (12, 31),
    "new years day": (1, 1),
    "new year": (1, 1),
    "new years": (1, 1),
    "valentines": (2, 14),
    "valentines day": (2, 14),
    "halloween": (10, 31),
    "bonfire night": (11, 5),
}
EASTER_OFFSETS = {"easter": 0, "easter sunday": 0, "easter day": 0, "good friday": -2, "easter monday": 1}
AFTER_CHRISTMAS = ((12, 26), (12, 31))
AFTER_CHRISTMAS_PHRASES = {"after christmas", "after christmas day"}

PARTS_OF_DAY = ("morning", "afternoon", "evening", "night")
PM_PARTS = {"afternoon", "evening", "night"}
NAMED_TIMES = {
    "noon": (12, 0, None),
    "midday": (12, 0, None),
    "midnight": (0, 0, None),
    "lunchtime": (12, 30, "afternoon"),
    "lunch time": (12, 30, "afternoon"),
    "lunch": (12, 30, "afternoon"),
}
CLOCK_FRACTIONS = {"half": 30, "quarter": 15}
BARE_PM_HOURS = range(1, 7)  # a bare 1-6 is pm; 7-12 stand as said (7-11 am, 12 noon)
# what is left once a clock time is taken out of "3pm", "before 3pm", "by 3pm", "after 3pm"
TIME_RELATIONS = {"": None, "before": "before", "by": "before", "after": "after"}

YEAR = r"(?:19|20|21)\d\d"  # four-digit years accepted; keeps arithmetic far from date.max
TWO_DIGIT_YEAR_BASE = 2000
CALENDAR_SEARCH_YEARS = 8  # a 29 February recurs within eight years
MAX_PHRASE_CHARS = 120  # longer text is not one date expression


def alternation(words):
    """Regex alternation of literal words, longest first so "christmas eve" wins over "christmas"."""
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


WEEKDAY = alternation(WEEKDAYS)
MONTH = alternation(MONTHS)
PART_OF_DAY = alternation(PARTS_OF_DAY)
COUNT = alternation([*APPROX_COUNTS, *EXACT_COUNTS]) + r"|\d{1,3}"
UNIT = alternation([*UNIT_DAYS, *UNIT_MONTHS])
ORDINAL_SUFFIX = r"(?:st|nd|rd|th)"


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


UNPARSED = Resolution("unparsed")
VAGUE = Resolution("vague")


@dataclass(frozen=True)
class Context:
    today: date
    anchor: Resolution | None
    day_first: bool


def resolve(text: str, today: date, anchor: Resolution | None = None, day_first: bool = True) -> Resolution:
    phrase = normalize(text)
    if len(phrase) > MAX_PHRASE_CHARS:
        return UNPARSED

    phrase, clock = take_clock(phrase)
    phrase, part = take_part_of_day(phrase)
    phrase = strip_fillers(phrase)
    ctx = Context(today, usable_anchor(anchor), day_first)
    part = part or (clock and clock.part_of_day)
    if clock is None and part is None:
        return resolve_phrase(phrase, ctx)

    time, time_ambiguous = settle_clock(clock, part)
    found = time_only(phrase, ctx) or resolve_phrase(phrase, ctx)
    if found.kind == "unparsed" and not found.anaphoric:
        return found

    return replace(found, time=time, part_of_day=part, ambiguous=found.ambiguous or time_ambiguous)


def usable_anchor(anchor):
    """An anchor without dates (vague, unparsed) is no anchor; a missing end means a single day."""
    if anchor is None or anchor.start is None:
        return None

    return anchor if anchor.end else replace(anchor, end=anchor.start)


def time_only(phrase, ctx):
    """A clock time or part of day with no date falls on the anchor's first day, or on today."""
    if phrase not in TIME_RELATIONS:
        return None

    relation, anchor = TIME_RELATIONS[phrase], ctx.anchor
    if anchor is None:
        return exact(ctx.today, relation=relation)

    return exact(anchor.start, relation=relation, anaphoric=True, ambiguous=anchor.ambiguous or anchor.start != anchor.end)


# --- normalisation ---


def normalize(text):
    """Lowercase words and digits: apostrophes dropped, other punctuation kept only inside numbers, words expanded."""
    s = re.sub(r"['‘’]", "", text.lower()).replace("@", " at ")
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", "", s)  # "p.m." -> "pm", "sept." -> "sept", "14.05" stays
    s = re.sub(r"(?<!\d)[:/-]|[:/-](?!\d)", " ", s)  # "mid-march" -> "mid march", "14/05" and "15:00" stay
    s = re.sub(r"[^a-z0-9.:/\- ]", " ", s)
    return numbers_to_digits(" ".join(expand_abbreviations(s.split())))


def expand_abbreviations(words):
    expanded = []
    for word in words:
        if word == "eve" and expanded and expanded[-1] in HOLIDAY_EVES:
            expanded.append(word)
            continue

        expanded.append(ABBREVIATIONS.get(word, word))

    return expanded


# compounds first, so "twenty one" becomes 21 rather than "20 1"
NUMBER_REWRITES = (
    (re.compile(rf"\b({alternation(TENS)}) ({alternation(UNIT_CARDINALS)})\b"), lambda m: str(TENS[m[1]] + UNIT_CARDINALS[m[2]])),
    (
        re.compile(rf"\b({alternation(TENS)}) ({alternation(UNIT_ORDINALS)})\b"),
        lambda m: f"{TENS[m[1]] + UNIT_ORDINALS[m[2]]}{ORDINAL_MARK}",
    ),
    (re.compile(rf"\b({alternation(NUMBER_WORDS)})\b"), lambda m: str(NUMBER_WORDS[m[1]])),
    (re.compile(rf"\b({alternation(ORDINALS)})\b"), lambda m: f"{ORDINALS[m[1]]}{ORDINAL_MARK}"),
)


def numbers_to_digits(s):
    """ "twenty one" -> "21", "the fourteenth" -> "the 14th"."""
    for pattern, digits in NUMBER_REWRITES:
        s = pattern.sub(digits, s)

    return s


def strip_fillers(phrase):
    words = phrase.split()
    while words and words[0] in LEADING_FILLERS:
        words = words[1:]

    return " ".join(words)


def cut(phrase, match, insert=""):
    """`phrase` with `match` replaced by `insert`, spaces tidied."""
    return " ".join(f"{phrase[: match.start()]} {insert} {phrase[match.end() :]}".split())


# --- clock times ---


@dataclass(frozen=True)
class Clock:
    hour: int  # as said: 3 in "3pm", 5 in "quarter to 5"
    minutes: int = 0  # may be negative: "quarter to 5" is 5:00 less 15
    meridiem: str | None = None  # "am" | "pm" | "24h", or None for a bare hour
    part_of_day: str | None = None  # implied by the word, as in "lunchtime"


def hour_meridiem(hour_text):
    """ "24h" for an hour that can only be read that way ("15", "0", "09"), else None (bare)."""
    hour = int(hour_text)
    return "24h" if hour == 0 or hour > HALF_DAY_HOURS or hour_text.startswith("0") else None


def named_clock(m):
    hour, minutes, part = NAMED_TIMES[m[1]]
    return Clock(hour, minutes, "24h", part)


def fraction_clock(m):
    minutes = CLOCK_FRACTIONS[m[1]] if m[1] in CLOCK_FRACTIONS else int(m[1])
    return Clock(int(m[3]), minutes if m[2] == "past" else -minutes, m[4])


def half_hour_clock(m):
    """British "half 9" is 9:30."""
    return Clock(int(m[1]), 30)


def meridiem_clock(m):
    return Clock(int(m[1]), int(m[2] or 0), m[3])


def colon_clock(m):
    return Clock(int(m[1]), int(m[2]), hour_meridiem(m[1]))


def spoken_clock(m):
    """ "three thirty" arrives as "3 30"."""
    return Clock(int(m[1]), int(m[2]))


def hour_clock(m):
    return Clock(int(m[1]), 0, hour_meridiem(m[1]))


H12 = r"(1[0-2]|0?[1-9])"
H24 = r"(2[0-3]|[01]?\d)"
MM = r"([0-5]\d)"
AT = r"(?:at )?"
CLOCKS = (
    (re.compile(rf"\b{AT}({alternation(NAMED_TIMES)})\b"), named_clock),
    (
        re.compile(rf"\b{AT}({alternation(CLOCK_FRACTIONS)}|[1-5]?\d)(?: minutes)? (past|to) {H12}(?: ?(am|pm))?(?: oclock)?\b"),
        fraction_clock,
    ),
    (re.compile(rf"\b{AT}half {H12}\b"), half_hour_clock),
    (re.compile(rf"\b{AT}{H12}(?:[:.]{MM})? ?(am|pm)\b"), meridiem_clock),
    (re.compile(rf"\b{AT}{H24}:{MM}\b"), colon_clock),
    (re.compile(rf"\bat {H24}\.{MM}\b"), colon_clock),
    (re.compile(rf"\b{AT}{H12} {MM}\b"), spoken_clock),
    (re.compile(rf"\b{AT}{H24} ?oclock\b"), hour_clock),
    (re.compile(rf"\bat {H24}\b"), hour_clock),
    (re.compile(rf"\b{H12}(?= in the (?:morning|afternoon|evening)| at night| tonight| this (?:morning|afternoon|evening))"), hour_clock),
)


def take_clock(phrase):
    """(phrase without its clock time, Clock | None); only the first time in the phrase counts."""
    for pattern, build in CLOCKS:
        m = pattern.search(phrase)
        if m:
            return cut(phrase, m), build(m)

    return phrase, None


def settle_clock(clock, part):
    """("HH:MM" | None, ambiguous) once am/pm or the part of day has decided the hour."""
    if clock is None:
        return None, False

    hour, ambiguous = clock_hour(clock, part)
    total = (hour * MINUTES_PER_HOUR + clock.minutes) % MINUTES_PER_DAY
    return f"{total // MINUTES_PER_HOUR:02d}:{total % MINUTES_PER_HOUR:02d}", ambiguous


def clock_hour(clock, part):
    if clock.meridiem == "24h":
        return clock.hour, False
    am_hour, pm_hour = clock.hour % HALF_DAY_HOURS, clock.hour % HALF_DAY_HOURS + HALF_DAY_HOURS
    if clock.meridiem == "am":
        return am_hour, False
    if clock.meridiem == "pm":
        return pm_hour, False
    if part == "night" and clock.hour == HALF_DAY_HOURS:
        return 0, False
    if part in PM_PARTS:
        return pm_hour, False
    if part == "morning":
        return am_hour, False

    return (pm_hour if clock.hour in BARE_PM_HOURS else clock.hour), True


# --- parts of day ---

# each rewrite takes out the part of day (group "part") and leaves the day it names; the first that matches wins
PART_OF_DAY_REWRITES = (
    (re.compile(r"\bto(?P<part>night)\b"), "today"),
    (re.compile(r"\blast (?P<part>night|evening)\b"), "yesterday"),
    (re.compile(rf"\bthis (?P<part>{PART_OF_DAY})\b"), "today"),
    (re.compile(rf"\b(?P<which>that|the next|next|the following) (?P<part>{PART_OF_DAY})\b"), r"\g<which> day"),
    (re.compile(rf"\bthe (?P<part>{PART_OF_DAY}) (?P<relation>before|after|of)\b"), r"the day \g<relation>"),
    (re.compile(rf"(?:\b(?:in the|at|during the|the) )?(?<!bonfire )\b(?P<part>{PART_OF_DAY})\b"), ""),
)


def take_part_of_day(phrase):
    for pattern, replacement in PART_OF_DAY_REWRITES:
        m = pattern.search(phrase)
        if m:
            return cut(phrase, m, m.expand(replacement)), m["part"]

    return phrase, None


# --- rules: each takes (phrase, ctx) and returns a Resolution, or None when it does not apply ---


def deictic_day(phrase, ctx):
    if phrase not in DEICTIC_DAYS:
        return None

    return exact(ctx.today + DEICTIC_DAYS[phrase] * DAY)


def anaphoric_phrase(phrase, ctx):
    if phrase not in ANAPHORIC_PHRASES:
        return None

    offset = ANAPHORIC_PHRASES[phrase]
    relation = "before" if offset < 0 else "after" if offset > 0 else None
    return from_reference(ctx.anchor, relation, lambda base: (base + offset * DAY, base + offset * DAY), anaphoric=True)


def vague_phrase(phrase, ctx):
    return VAGUE if phrase in VAGUE_PHRASES else None


def after_christmas(phrase, ctx):
    if phrase not in AFTER_CHRISTMAS_PHRASES:
        return None

    (first_month, first_day), (last_month, last_day) = AFTER_CHRISTMAS
    year = ctx.today.year
    return span(date(year, first_month, first_day), date(year, last_month, last_day), relation="after")


OFFSET_FROM_REFERENCE = re.compile(
    rf"(?:(?P<count>{COUNT}) (?P<unit>{UNIT})s?|the (?P<span>day|week)) (?P<relation>before|after)(?: (?P<reference>.+))?"
)


def offset_from_reference(phrase, ctx):
    """ "the day before", "the week after", "3 days before", and the same against a named date: "the day before christmas"."""
    m = OFFSET_FROM_REFERENCE.fullmatch(phrase)
    if not m:
        return None

    reference, anaphoric = reference_of(m["reference"], ctx)
    if reference is None and not anaphoric:
        return None

    relation = m["relation"]
    sign = -1 if relation == "before" else 1
    if m["span"] == "week":
        return from_reference(reference, relation, lambda base: sorted((base + sign * DAY, base + sign * WEEK)), anaphoric)

    return from_reference(reference, relation, lambda base: offset_window(base, sign, m["count"] or "a", m["unit"] or "day"), anaphoric)


def reference_of(text, ctx):
    """(reference, anaphoric): the anchor when no date is named, else the named date (None when it does not resolve)."""
    if text is None or text in ANAPHORIC_REFERENCES:
        return ctx.anchor, True

    found = resolve_phrase(text, ctx)
    return (found if found.start is not None and not found.anaphoric else None), False


def from_reference(reference, relation, window, anaphoric):
    """Resolve against the reference's first day for "before", its last for "after", or all of it for neither.

    `window(base)` gives the (start, end) of the result counted from that day.
    """
    if reference is None:
        return Resolution("unparsed", relation=relation, anaphoric=True)
    if relation is None:
        return span(reference.start, reference.end, anaphoric=anaphoric, ambiguous=reference.ambiguous or reference.start != reference.end)

    start, end = window(reference.start if relation == "before" else reference.end)
    return span(start, end, relation=relation, anaphoric=anaphoric, ambiguous=reference.ambiguous)


RELATIVE_TO_DATE = re.compile(r"(?P<word>before|after|by) (?P<target>.+)")


def relative_to_date(phrase, ctx):
    """ "before friday" is today up to Thursday, "by friday" includes Friday, "after friday" is Saturday."""
    m = RELATIVE_TO_DATE.fullmatch(phrase)
    if not m:
        return None

    target = resolve_phrase(m["target"], ctx)
    if target.start is None or target.anaphoric:
        return None
    if m["word"] == "after":
        return exact(target.end + DAY, relation="after", ambiguous=target.ambiguous)

    end = target.end if m["word"] == "by" else target.start - DAY
    return span(min(ctx.today, end), end, relation="before", ambiguous=target.ambiguous)


WEEKDAY_PHRASE = re.compile(
    rf"(?:(?P<before>this coming|coming|this|next|last|a week on) )?(?P<day>{WEEKDAY})(?: (?P<after>week|this week|next week|after next))?"
)
WEEKDAY_FORMS = {
    (None, None): "coming",
    ("coming", None): "coming",
    ("this coming", None): "coming",
    ("this", None): "this",
    (None, "this week"): "this",
    ("next", None): "next",
    (None, "next week"): "next_week",
    ("a week on", None): "week_on",
    (None, "week"): "week_on",
    (None, "after next"): "week_on",
    ("last", None): "last",
}


def named_weekday(phrase, ctx):
    m = WEEKDAY_PHRASE.fullmatch(phrase)
    form = m and WEEKDAY_FORMS.get((m["before"], m["after"]))
    if not form:
        return None

    today, day = ctx.today, WEEKDAYS[m["day"]]
    in_this_week = week_start(today) + day * DAY
    coming = today + ((day - today.weekday() - 1) % 7 + 1) * DAY
    if form == "coming":
        return exact(coming)
    if form == "this":
        return exact(in_this_week if in_this_week >= today else in_this_week + WEEK)
    if form == "week_on":
        return exact(coming + WEEK)
    if form == "last":
        return exact(today - ((today.weekday() - day - 1) % 7 + 1) * DAY)

    return exact(in_this_week + WEEK, ambiguous=form == "next")


WEEKDAY_AND_DATE = re.compile(rf"(?P<day>{WEEKDAY}) (?P<date>.+)")


def weekday_and_date(phrase, ctx):
    """ "friday the 23rd": the date decides; a weekday that does not match it makes the result ambiguous."""
    m = WEEKDAY_AND_DATE.fullmatch(phrase)
    if not m:
        return None

    found = calendar_date(m["date"], ctx) or day_of_month(m["date"], ctx)
    if found is None or found.start is None:
        return None

    return replace(found, ambiguous=found.ambiguous or found.start.weekday() != WEEKDAYS[m["day"]])


DAY_MONTH = re.compile(rf"(?:the )?(?P<day>\d{{1,2}}){ORDINAL_SUFFIX}?(?: of)? (?P<month>{MONTH})(?: (?P<year>{YEAR}))?")
MONTH_DAY = re.compile(rf"(?P<month>{MONTH}) (?:the )?(?P<day>\d{{1,2}}){ORDINAL_SUFFIX}?(?: (?P<year>{YEAR}))?")
ISO_DATE = re.compile(rf"(?P<year>{YEAR})-(?P<month>\d{{1,2}})-(?P<day>\d{{1,2}})")
NUMERIC_DATE = re.compile(rf"(?P<first>\d{{1,2}})(?P<sep>[/.])(?P<second>\d{{1,2}})(?:(?P=sep)(?P<year>{YEAR}|\d\d))?")


def calendar_date(phrase, ctx):
    m = DAY_MONTH.fullmatch(phrase) or MONTH_DAY.fullmatch(phrase)
    if m:
        return calendar_day(ctx.today, MONTHS[m["month"]], int(m["day"]), full_year(m["year"]))

    m = ISO_DATE.fullmatch(phrase)
    if m:
        return calendar_day(ctx.today, int(m["month"]), int(m["day"]), full_year(m["year"]))

    m = NUMERIC_DATE.fullmatch(phrase)
    if m:
        return numeric_date(ctx, int(m["first"]), int(m["second"]), full_year(m["year"]))

    return None


def numeric_date(ctx, first, second, year):
    """Day and month in the preferred order (`day_first`), or the other order when the preferred one cannot fit."""
    orders = ((first, second), (second, first)) if ctx.day_first else ((second, first), (first, second))
    for day, month in orders:
        if 1 <= month <= MONTHS_PER_YEAR and 1 <= day <= MAX_MONTH_DAY:
            return calendar_day(ctx.today, month, day, year)

    return UNPARSED


def calendar_day(today, month, day, year=None):
    """The date in the given year, or without one its first occurrence on or after today; unparsed if invalid."""
    if year is not None:
        found = valid_date(year, month, day)
        return exact(found) if found else UNPARSED

    for candidate in range(today.year, today.year + CALENDAR_SEARCH_YEARS + 1):
        found = valid_date(candidate, month, day)
        if found and found >= today:
            return exact(found)

    return UNPARSED


DAY_OF_MONTH = re.compile(rf"the (\d{{1,2}}){ORDINAL_SUFFIX}?|(\d{{1,2}}){ORDINAL_SUFFIX}")


def day_of_month(phrase, ctx):
    """ "the 3rd": this month's if today or later, otherwise the next month that has that day."""
    m = DAY_OF_MONTH.fullmatch(phrase)
    if not m:
        return None

    day = int(m[1] or m[2])
    this_month = ctx.today.replace(day=1)
    for months_ahead in range(MONTHS_PER_YEAR):
        month_start = add_months(this_month, months_ahead)
        found = valid_date(month_start.year, month_start.month, day)
        if found and found >= ctx.today:
            return exact(found)

    return UNPARSED


HOLIDAY = re.compile(rf"(?:the )?(?P<name>{alternation([*FIXED_HOLIDAYS, *EASTER_OFFSETS])})(?: (?P<year>{YEAR}))?")


def holiday(phrase, ctx):
    m = HOLIDAY.fullmatch(phrase)
    if not m:
        return None
    if m["year"]:
        return exact(holiday_date(m["name"], int(m["year"])))

    this_year = holiday_date(m["name"], ctx.today.year)
    return exact(this_year if this_year >= ctx.today else holiday_date(m["name"], ctx.today.year + 1))


def holiday_date(name, year):
    if name in EASTER_OFFSETS:
        return easter_sunday(year) + EASTER_OFFSETS[name] * DAY

    return date(year, *FIXED_HOLIDAYS[name])


MONTH_PHRASE = re.compile(
    rf"(?:in )?(?:the )?(?:(?P<part>{alternation(MONTH_PARTS)}) )?(?:the )?(?:(?P<which>this|next|last) )?(?P<month>{MONTH}|month)(?: (?P<year>{YEAR}))?"
)


def month_range(phrase, ctx):
    """ "march", "early march", "next month", "end of the month": a named month is its next occurrence not yet over."""
    m = MONTH_PHRASE.fullmatch(phrase)
    if not m:
        return None

    part = MONTH_PARTS.get(m["part"], WHOLE_MONTH)
    if m["month"] == "month":
        if m["year"]:
            return None

        return span(*month_window(add_months(ctx.today.replace(day=1), RELATIVE_STEPS[m["which"]]), part))

    number = MONTHS[m["month"]]
    if m["year"]:
        return span(*month_window(date(int(m["year"]), number, 1), part))

    windows = [month_window(date(year, number, 1), part) for year in nearby_years(ctx.today)]
    return span(*pick_window(windows, m["which"], ctx.today))


def month_window(month_start, part):
    first_day, last_day = part
    return month_start.replace(day=first_day), month_start.replace(day=min(last_day, days_in_month(month_start.year, month_start.month)))


SEASON_PHRASE = re.compile(rf"(?:in )?(?:the )?(?:(?P<which>this|next|last) )?(?P<season>{alternation(SEASONS)})(?: (?P<year>{YEAR}))?")


def season_range(phrase, ctx):
    m = SEASON_PHRASE.fullmatch(phrase)
    if not m:
        return None
    if m["year"]:
        return span(*season_window(m["season"], int(m["year"])))

    windows = [season_window(m["season"], year) for year in nearby_years(ctx.today)]
    return span(*pick_window(windows, m["which"], ctx.today))


def season_window(name, year):
    """A season starting in `year`; winter runs into the next year."""
    first_month, last_month = SEASONS[name]
    end_year = year + 1 if last_month < first_month else year
    return date(year, first_month, 1), date(end_year, last_month, days_in_month(end_year, last_month))


def pick_window(windows, which, today):
    """From chronological (start, end) windows: "last" is the latest already over, "next" the first not yet begun,
    and bare or "this" the first not yet over (so the current one counts)."""
    if which == "last":
        return [w for w in windows if w[1] < today][-1]
    if which == "next":
        return next(w for w in windows if w[0] > today)

    return next(w for w in windows if w[1] >= today)


LATER_THIS_WEEK = {"later this week", "later in the week"}
WEEK_AFTER_NEXT = {"the week after next", "week after next"}
WEEK_PHRASE = re.compile(rf"(?:the )?(?:(?P<part>{alternation(WEEK_PARTS)}) )?(?:the )?(?:(?P<which>this|next|last) )?week")


def week_range(phrase, ctx):
    """Weeks run Monday to Sunday; "this week" starts today."""
    today = ctx.today
    monday = week_start(today)
    sunday = monday + SUNDAY_OFFSET
    if phrase in LATER_THIS_WEEK:
        return span(min(today + DAY, sunday), sunday)
    if phrase in WEEK_AFTER_NEXT:
        return span(monday + 2 * WEEK, sunday + 2 * WEEK)

    m = WEEK_PHRASE.fullmatch(phrase)
    if not m:
        return None

    start = monday + RELATIVE_STEPS[m["which"]] * WEEK
    if m["part"]:
        first, last = WEEK_PARTS[m["part"]]
        return span(start + first * DAY, start + last * DAY)
    if m["which"] in ("next", "last"):
        return span(start, start + SUNDAY_OFFSET)

    return span(today, sunday)


WEEKEND_PHRASE = re.compile(r"(?:the )?(?:(?P<which>this coming|coming|this|next|last) )?weekend")


def weekend_range(phrase, ctx):
    """The Saturday-Sunday of the current week ("this weekend" on a Sunday is still this one)."""
    m = WEEKEND_PHRASE.fullmatch(phrase)
    if not m:
        return None

    saturday = week_start(ctx.today) + SATURDAY_OFFSET + RELATIVE_STEPS[m["which"]] * WEEK
    return span(saturday, saturday + DAY, ambiguous=m["which"] == "next")


YEAR_PHRASE = re.compile(r"(?:in )?(?P<which>this|next|last) year")


def year_range(phrase, ctx):
    m = YEAR_PHRASE.fullmatch(phrase)
    if not m:
        return None

    number = ctx.today.year + RELATIVE_STEPS[m["which"]]
    return span(date(number, 1, 1), date(number, MONTHS_PER_YEAR, MAX_MONTH_DAY))


OFFSET_FROM_TODAY = re.compile(rf"(?:in )?(?P<count>{COUNT}) (?P<unit>{UNIT})s?(?: time| from now| from today)?")


def offset_from_today(phrase, ctx):
    m = OFFSET_FROM_TODAY.fullmatch(phrase)
    if not m:
        return None

    return span(*offset_window(ctx.today, 1, m["count"], m["unit"]))


def vague_affix(phrase, ctx):
    """A vague word around a resolvable part resolves that part ("sometime next week"); otherwise it stays vague."""
    for word in VAGUE_AFFIXES:
        rest = without_affix(phrase, word)
        if rest is None:
            continue

        found = resolve_phrase(strip_fillers(rest), ctx)
        return VAGUE if found.kind == "unparsed" and not found.anaphoric else found

    return None


def without_affix(phrase, word):
    if phrase.startswith(f"{word} "):
        return phrase[len(word) + 1 :]
    if phrase.endswith(f" {word}"):
        return phrase[: -len(word) - 1]

    return None


RULES = (
    deictic_day,
    anaphoric_phrase,
    vague_phrase,
    after_christmas,
    offset_from_reference,
    relative_to_date,
    named_weekday,
    weekday_and_date,
    calendar_date,
    day_of_month,
    holiday,
    month_range,
    season_range,
    week_range,
    weekend_range,
    year_range,
    offset_from_today,
    vague_affix,
)


def resolve_phrase(phrase, ctx):
    if not phrase:
        return UNPARSED

    for rule in RULES:
        found = rule(phrase, ctx)
        if found is not None:
            return found

    return UNPARSED


# --- results and date arithmetic ---


def exact(day, **fields):
    return Resolution("exact", day, day, **fields)


def span(start, end, **fields):
    """A range, or exact when it covers one day."""
    if start == end:
        return exact(start, **fields)

    return Resolution("range", start, end, **fields)


def offset_window(base, sign, count, unit):
    """(start, end) `count` units from `base`: one day for a definite count, widened by the unit's slack for an approximate one."""
    n, approximate = parse_count(count)
    nominal = shift(base, sign * n, unit)
    slack = (APPROX_SLACK_DAYS[unit] if approximate else 0) * DAY
    return nominal - slack, nominal + slack


def parse_count(text):
    """(n, approximate) for "3", "a", "a few", ..."""
    if text in APPROX_COUNTS:
        return APPROX_COUNTS[text], True

    return EXACT_COUNTS.get(text) or int(text), False


def shift(day, count, unit):
    if unit in UNIT_DAYS:
        return day + count * UNIT_DAYS[unit] * DAY

    return add_months(day, count * UNIT_MONTHS[unit])


def add_months(day, months):
    """Same day of the month `months` later, clamped to the month's last day."""
    year, month_index = divmod(day.year * MONTHS_PER_YEAR + day.month - 1 + months, MONTHS_PER_YEAR)
    return date(year, month_index + 1, min(day.day, days_in_month(year, month_index + 1)))


def week_start(day):
    return day - day.weekday() * DAY


def days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def valid_date(year, month, day):
    if not 1 <= month <= MONTHS_PER_YEAR or not 1 <= day <= days_in_month(year, month):
        return None

    return date(year, month, day)


def full_year(text):
    if text is None:
        return None

    return int(text) + TWO_DIGIT_YEAR_BASE if len(text) == 2 else int(text)


def nearby_years(today):
    return range(today.year - SEARCH_YEARS_AROUND, today.year + SEARCH_YEARS_AROUND + 1)


def easter_sunday(year):
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    weekday_shift = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * weekday_shift) // 451
    month_and_day = h + weekday_shift - 7 * m + 114
    return date(year, month_and_day // 31, month_and_day % 31 + 1)
