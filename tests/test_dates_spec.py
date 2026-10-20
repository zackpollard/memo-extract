"""Acceptance suite for memo_extract.dates, written from docs/dates.md alone.

Expected dates are literals, never computed, so an arithmetic bug shared with the resolver cannot hide.
A whole Resolution is compared where the spec fixes every field; an `only(...)` dict asserts just the fields it names.
Cases resting on a reading of the spec rather than its literal text carry a `# spec:` comment.
"""

import dataclasses
import re
from dataclasses import dataclass
from datetime import date

import pytest

from memo_extract.dates import Resolution, resolve

MON = date(2026, 10, 19)
SAT = date(2026, 12, 26)
SUN = date(2026, 3, 1)

KINDS = {"exact", "range", "vague", "unparsed"}
PARTS_OF_DAY = {None, "morning", "afternoon", "evening", "night"}
RELATIONS = {None, "before", "after"}
CLOCK = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def d(month: int, day: int, year: int = 2026) -> date:
    return date(year, month, day)


def exact(day: date, **fields) -> Resolution:
    return Resolution(kind="exact", start=day, end=day, **fields)


def span(start: date, end: date, **fields) -> Resolution:
    return Resolution(kind="range", start=start, end=end, **fields)


def only(**fields) -> dict:
    return fields


def only_exact(day: date, **fields) -> dict:
    return only(kind="exact", start=day, end=day, **fields)


def only_range(start: date, end: date, **fields) -> dict:
    return only(kind="range", start=start, end=end, **fields)


UNPARSED = Resolution(kind="unparsed")
VAGUE = Resolution(kind="vague")

FRIDAY_EVENT = exact(d(10, 23))
NEXT_WEEK_EVENT = span(d(10, 26), d(11, 1))


@dataclass(frozen=True)
class Case:
    text: str
    today: date
    expected: Resolution | dict
    anchor: Resolution | None = None
    day_first: bool = True


def label(c: Case) -> str:
    parts = [repr(c.text), f"{c.today:%a %d %b %Y}"]
    if c.anchor is not None:
        parts.append(f"anchor {c.anchor.kind} {c.anchor.start}..{c.anchor.end}")
    if not c.day_first:
        parts.append("month first")
    return " | ".join(parts)


def case(text: str, today: date, expected: Resolution | dict, **options):
    c = Case(text, today, expected, **options)
    return pytest.param(c, id=label(c))


def run(c: Case) -> Resolution:
    if c.anchor is None and c.day_first:
        return resolve(c.text, c.today)

    return resolve(c.text, c.today, anchor=c.anchor, day_first=c.day_first)


def assert_case(c: Case) -> None:
    result = run(c)
    if isinstance(c.expected, Resolution):
        assert result == c.expected
        return

    assert {name: getattr(result, name) for name in c.expected} == c.expected


DEICTIC = [
    case("today", MON, exact(d(10, 19))),
    case("tonight", MON, exact(d(10, 19), part_of_day="night")),
    case("this morning", MON, exact(d(10, 19), part_of_day="morning")),
    case("this afternoon", MON, exact(d(10, 19), part_of_day="afternoon")),
    case("this evening", MON, exact(d(10, 19), part_of_day="evening")),
    case("tomorrow", MON, exact(d(10, 20))),
    case("tomorrow morning", MON, exact(d(10, 20), part_of_day="morning")),
    case("tomorrow afternoon", MON, exact(d(10, 20), part_of_day="afternoon")),
    case("tomorrow evening", MON, exact(d(10, 20), part_of_day="evening")),
    case("tomorrow night", MON, exact(d(10, 20), part_of_day="night")),
    case("the day after tomorrow", MON, exact(d(10, 21))),
    case("yesterday", MON, exact(d(10, 18))),
    # spec: "last night" is yesterday with part_of_day night (listed under deictic days, no detail given)
    case("last night", MON, exact(d(10, 18), part_of_day="night")),
    case("tonight", SAT, exact(d(12, 26), part_of_day="night")),
    case("tomorrow", SAT, exact(d(12, 27))),
    case("the day after tomorrow", SAT, exact(d(12, 28))),
    case("yesterday", SAT, exact(d(12, 25))),
    case("tomorrow", SUN, exact(d(3, 2))),
    case("the day after tomorrow", SUN, exact(d(3, 3))),
    case("yesterday", SUN, exact(d(2, 28))),
    case("last night", SUN, exact(d(2, 28), part_of_day="night")),
    # spec: an extra today to cross the year boundary on a plain deictic
    case("tomorrow", d(12, 31), exact(d(1, 1, 2027))),
]


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# today -> form -> resolved day for Monday..Sunday
WEEKDAY_MATRIX = {
    MON: {
        "bare": (d(10, 26), d(10, 20), d(10, 21), d(10, 22), d(10, 23), d(10, 24), d(10, 25)),
        "this": (d(10, 19), d(10, 20), d(10, 21), d(10, 22), d(10, 23), d(10, 24), d(10, 25)),
        "next": (d(10, 26), d(10, 27), d(10, 28), d(10, 29), d(10, 30), d(10, 31), d(11, 1)),
        "week": (d(11, 2), d(10, 27), d(10, 28), d(10, 29), d(10, 30), d(10, 31), d(11, 1)),
        "last": (d(10, 12), d(10, 13), d(10, 14), d(10, 15), d(10, 16), d(10, 17), d(10, 18)),
    },
    SAT: {
        "bare": (d(12, 28), d(12, 29), d(12, 30), d(12, 31), d(1, 1, 2027), d(1, 2, 2027), d(12, 27)),
        "this": (d(12, 28), d(12, 29), d(12, 30), d(12, 31), d(1, 1, 2027), d(12, 26), d(12, 27)),
        "next": (d(12, 28), d(12, 29), d(12, 30), d(12, 31), d(1, 1, 2027), d(1, 2, 2027), d(1, 3, 2027)),
        "week": (d(1, 4, 2027), d(1, 5, 2027), d(1, 6, 2027), d(1, 7, 2027), d(1, 8, 2027), d(1, 9, 2027), d(1, 3, 2027)),
        "last": (d(12, 21), d(12, 22), d(12, 23), d(12, 24), d(12, 25), d(12, 19), d(12, 20)),
    },
    SUN: {
        "bare": (d(3, 2), d(3, 3), d(3, 4), d(3, 5), d(3, 6), d(3, 7), d(3, 8)),
        "this": (d(3, 2), d(3, 3), d(3, 4), d(3, 5), d(3, 6), d(3, 7), d(3, 1)),
        "next": (d(3, 2), d(3, 3), d(3, 4), d(3, 5), d(3, 6), d(3, 7), d(3, 8)),
        "week": (d(3, 9), d(3, 10), d(3, 11), d(3, 12), d(3, 13), d(3, 14), d(3, 15)),
        "last": (d(2, 23), d(2, 24), d(2, 25), d(2, 26), d(2, 27), d(2, 28), d(2, 22)),
    },
}

# The spec fixes `ambiguous` only for "this" (False) and "next" (True); the other forms assert just the day.
WEEKDAY_FORMS = (
    ("{}", "bare", only_exact),
    ("this {}", "this", exact),
    ("next {}", "next", lambda day: exact(day, ambiguous=True)),
    ("{} week", "week", only_exact),
    ("a week on {}", "week", only_exact),
    ("last {}", "last", only_exact),
)

WEEKDAY_SEMANTICS = [
    case(template.format(name), today, expect(days[form][index]))
    for today, days in WEEKDAY_MATRIX.items()
    for template, form, expect in WEEKDAY_FORMS
    for index, name in enumerate(WEEKDAYS)
]

WEEKDAY_WITH_TIME = [
    case("Friday morning", MON, exact(d(10, 23), part_of_day="morning")),
    case("Saturday night", MON, exact(d(10, 24), part_of_day="night")),
    case("Monday morning", MON, only_exact(d(10, 26), part_of_day="morning")),
    case("this Friday evening", MON, exact(d(10, 23), part_of_day="evening")),
    case("next Friday afternoon", MON, exact(d(10, 30), part_of_day="afternoon", ambiguous=True)),
    # spec: clock times assert `time` only; whether "3pm" also sets part_of_day is not stated
    case("Friday at 3pm", MON, only_exact(d(10, 23), time="15:00", ambiguous=False)),
    case("fri 3pm", MON, only_exact(d(10, 23), time="15:00", ambiguous=False)),
    case("thurs 10am", MON, only_exact(d(10, 22), time="10:00", ambiguous=False)),
    case("Friday at 3", MON, only_exact(d(10, 23), time="15:00", ambiguous=True)),
    case("this Friday at 3pm", MON, only_exact(d(10, 23), time="15:00", ambiguous=False)),
    case("next Friday at 3pm", MON, only_exact(d(10, 30), time="15:00", ambiguous=True)),
    case("Friday morning", SAT, exact(d(1, 1, 2027), part_of_day="morning")),
    case("Sunday evening", SUN, only_exact(d(3, 8), part_of_day="evening")),
]


CALENDAR_DATES = [
    case("14 May", MON, exact(d(5, 14, 2027))),
    case("14th May", MON, exact(d(5, 14, 2027))),
    case("14th of May", MON, exact(d(5, 14, 2027))),
    case("the 14th of May", MON, exact(d(5, 14, 2027))),
    case("May 14", MON, exact(d(5, 14, 2027))),
    case("May 14th", MON, exact(d(5, 14, 2027))),
    case("the fourteenth of may", MON, exact(d(5, 14, 2027))),
    case("may fourteenth", MON, exact(d(5, 14, 2027))),
    case("14 May 2027", MON, exact(d(5, 14, 2027))),
    case("May 14, 2027", MON, exact(d(5, 14, 2027))),
    case("2 November 2026", MON, exact(d(11, 2))),
    case("november 2nd", MON, exact(d(11, 2))),
    case("2 November", MON, exact(d(11, 2))),
    case("14 May 2026", MON, exact(d(5, 14))),
    case("19 October", MON, exact(d(10, 19))),
    case("18 October", MON, exact(d(10, 18, 2027))),
    case("20 October", MON, exact(d(10, 20))),
    case("1 January", MON, exact(d(1, 1, 2027))),
    case("the first of january", MON, exact(d(1, 1, 2027))),
    # spec: compound ordinal words generalise "the fourteenth of may" to every day of the month
    case("the twenty second of november", MON, exact(d(11, 22))),
    case("the thirty-first of december", MON, exact(d(12, 31))),
    case("14 sept", MON, exact(d(9, 14, 2027))),
    case("29 February 2028", MON, exact(d(2, 29, 2028))),
    # spec: the next occurrence of 29 February on or after 19 Oct 2026 is in 2028; it is not an invalid date
    case("29 February", MON, exact(d(2, 29, 2028))),
    case("25 December", SAT, exact(d(12, 25, 2027))),
    case("26 December", SAT, exact(d(12, 26))),
    case("27 December", SAT, exact(d(12, 27))),
    case("2 January", SAT, exact(d(1, 2, 2027))),
    case("January 1st", SAT, exact(d(1, 1, 2027))),
    case("26 December 2025", SAT, exact(d(12, 26, 2025))),
    case("1 March", SUN, exact(d(3, 1))),
    case("28 February", SUN, exact(d(2, 28, 2027))),
    case("31 June", MON, UNPARSED),
    case("30 February", MON, UNPARSED),
    case("31 sept", MON, UNPARSED),
    case("31 April 2027", MON, UNPARSED),
    case("29 February 2027", MON, UNPARSED),
]


# spec: read "day first unless ... the second does not fit as a month; the reverse when day_first is False" as
# "use the configured order, and swap only when that order puts a number above 12 in the month slot".
# The literal "unless the first number exceeds 12" would make the spec's own 14/05 example a month-14 date.
# `ambiguous` is not asserted: the spec does not say whether 5/6 style dates are ambiguous.
NUMERIC_DATES = [
    case("14/05", MON, only_exact(d(5, 14, 2027))),
    case("14/5", MON, only_exact(d(5, 14, 2027))),
    case("14.05", MON, only_exact(d(5, 14, 2027))),
    case("14/05/2027", MON, only_exact(d(5, 14, 2027))),
    # spec: a two-digit year means 20YY
    case("14/05/27", MON, only_exact(d(5, 14, 2027))),
    case("14/05/2026", MON, only_exact(d(5, 14))),
    case("5/14", MON, only_exact(d(5, 14, 2027))),
    case("5/6", MON, only_exact(d(6, 5, 2027))),
    case("1/11", MON, only_exact(d(11, 1))),
    case("10/12", MON, only_exact(d(12, 10))),
    case("19/10", MON, only_exact(d(10, 19))),
    case("10/19", MON, only_exact(d(10, 19))),
    case("12/25/26", MON, only_exact(d(12, 25))),
    case("29/02/2028", MON, only_exact(d(2, 29, 2028))),
    case("5/14", MON, only_exact(d(5, 14, 2027)), day_first=False),
    case("05/14/2027", MON, only_exact(d(5, 14, 2027)), day_first=False),
    case("5/6", MON, only_exact(d(5, 6, 2027)), day_first=False),
    case("1/11", MON, only_exact(d(1, 11, 2027)), day_first=False),
    case("10/12", MON, only_exact(d(10, 12, 2027)), day_first=False),
    case("14/05", MON, only_exact(d(5, 14, 2027)), day_first=False),
    case("14/5", MON, only_exact(d(5, 14, 2027)), day_first=False),
    case("10/19", MON, only_exact(d(10, 19)), day_first=False),
    case("12/25/26", MON, only_exact(d(12, 25)), day_first=False),
    case("14 May", MON, exact(d(5, 14, 2027)), day_first=False),
    case("25/12", SAT, only_exact(d(12, 25, 2027))),
    case("26/12", SAT, only_exact(d(12, 26))),
    case("31/12", SAT, only_exact(d(12, 31))),
    case("01/01", SAT, only_exact(d(1, 1, 2027))),
    case("12/25", SAT, only_exact(d(12, 25, 2027)), day_first=False),
    case("1/2", SAT, only_exact(d(1, 2, 2027)), day_first=False),
    case("1/3", SUN, only_exact(d(3, 1))),
    case("1/3", SUN, only_exact(d(1, 3, 2027)), day_first=False),
    case("28/2", SUN, only_exact(d(2, 28, 2027))),
    *(
        case(text, MON, UNPARSED, day_first=day_first)
        for text in ("31/06", "06/31", "13/13", "0/5", "00/00", "32/01", "30/02", "31/04/2027", "29/02/2027")
        for day_first in (True, False)
    ),
]


DAY_OF_MONTH = [
    case("the 3rd", MON, exact(d(11, 3))),
    case("on the 3rd", MON, exact(d(11, 3))),
    case("the 14th", MON, exact(d(11, 14))),
    case("the fourteenth", MON, exact(d(11, 14))),
    case("the first", MON, exact(d(11, 1))),
    case("the 19th", MON, exact(d(10, 19))),
    case("the 20th", MON, exact(d(10, 20))),
    case("the 31st", MON, exact(d(10, 31))),
    # spec: compound ordinal words generalise "the fourteenth"
    case("the twenty-first", MON, exact(d(10, 21))),
    case("the 3rd", SAT, exact(d(1, 3, 2027))),
    case("the 25th", SAT, exact(d(1, 25, 2027))),
    case("the 26th", SAT, exact(d(12, 26))),
    case("the 31st", SAT, exact(d(12, 31))),
    case("the 1st", SUN, exact(d(3, 1))),
    case("the 31st", SUN, exact(d(3, 31))),
    # spec: no month has a 32nd, so nothing valid is recognised
    case("the 32nd", MON, UNPARSED),
]


MONTHS = [
    case("March", MON, span(d(3, 1, 2027), d(3, 31, 2027))),
    case("in March", MON, span(d(3, 1, 2027), d(3, 31, 2027))),
    case("in November", MON, span(d(11, 1), d(11, 30))),
    # spec: "the current month counts" and the range covers the whole month, including days already past
    case("October", MON, span(d(10, 1), d(10, 31))),
    case("September", MON, span(d(9, 1, 2027), d(9, 30, 2027))),
    case("in sept", MON, span(d(9, 1, 2027), d(9, 30, 2027))),
    case("February", MON, span(d(2, 1, 2027), d(2, 28, 2027))),
    case("February 2028", MON, span(d(2, 1, 2028), d(2, 29, 2028))),
    case("March 2027", MON, span(d(3, 1, 2027), d(3, 31, 2027))),
    # spec: "with a year, use it as given" applies to a month with a year too
    case("March 2026", MON, span(d(3, 1), d(3, 31))),
    case("early March", MON, span(d(3, 1, 2027), d(3, 10, 2027))),
    case("early June", MON, span(d(6, 1, 2027), d(6, 10, 2027))),
    case("mid March", MON, span(d(3, 11, 2027), d(3, 20, 2027))),
    case("mid-March", MON, span(d(3, 11, 2027), d(3, 20, 2027))),
    case("late March", MON, span(d(3, 21, 2027), d(3, 31, 2027))),
    case("end of March", MON, span(d(3, 21, 2027), d(3, 31, 2027))),
    case("late February", MON, span(d(2, 21, 2027), d(2, 28, 2027))),
    case("end of June", MON, span(d(6, 21, 2027), d(6, 30, 2027))),
    case("late October", MON, span(d(10, 21), d(10, 31))),
    # spec: early/mid/late pick a slice of the month chosen by the month rule, where the current month counts
    case("mid October", MON, span(d(10, 11), d(10, 20))),
    case("next month", MON, span(d(11, 1), d(11, 30))),
    # spec: "this month" is the whole month like the other month expressions, not today..month end
    case("this month", MON, span(d(10, 1), d(10, 31))),
    case("end of the month", MON, span(d(10, 21), d(10, 31))),
    case("end of next month", MON, span(d(11, 21), d(11, 30))),
    case("beginning of next month", MON, span(d(11, 1), d(11, 10))),
    case("January", SAT, span(d(1, 1, 2027), d(1, 31, 2027))),
    case("early January", SAT, span(d(1, 1, 2027), d(1, 10, 2027))),
    case("December", SAT, span(d(12, 1), d(12, 31))),
    case("November", SAT, span(d(11, 1, 2027), d(11, 30, 2027))),
    case("next month", SAT, span(d(1, 1, 2027), d(1, 31, 2027))),
    case("this month", SAT, span(d(12, 1), d(12, 31))),
    case("end of the month", SAT, span(d(12, 21), d(12, 31))),
    case("end of next month", SAT, span(d(1, 21, 2027), d(1, 31, 2027))),
    case("beginning of next month", SAT, span(d(1, 1, 2027), d(1, 10, 2027))),
    case("March", SUN, span(d(3, 1), d(3, 31))),
    case("February", SUN, span(d(2, 1, 2027), d(2, 28, 2027))),
    case("late February", SUN, span(d(2, 21, 2027), d(2, 28, 2027))),
    case("next month", SUN, span(d(4, 1), d(4, 30))),
    case("end of the month", SUN, span(d(3, 21), d(3, 31))),
    case("end of next month", SUN, span(d(4, 21), d(4, 30))),
]


# spec: seasons follow the month rule: the next occurrence, where the season containing today counts.
SEASONS = [
    case("spring", MON, span(d(3, 1, 2027), d(5, 31, 2027))),
    case("in the spring", MON, span(d(3, 1, 2027), d(5, 31, 2027))),
    case("summer", MON, span(d(6, 1, 2027), d(8, 31, 2027))),
    case("over the summer", MON, span(d(6, 1, 2027), d(8, 31, 2027))),
    # spec: from autumn the next summer is the coming one; `ambiguous` is unspecified for "next <season>"
    case("next summer", MON, only_range(d(6, 1, 2027), d(8, 31, 2027))),
    case("autumn", MON, span(d(9, 1), d(11, 30))),
    case("fall", MON, span(d(9, 1), d(11, 30))),
    case("this autumn", MON, span(d(9, 1), d(11, 30))),
    case("winter", MON, span(d(12, 1), d(2, 28, 2027))),
    case("this winter", MON, span(d(12, 1), d(2, 28, 2027))),
    case("over the winter", MON, span(d(12, 1), d(2, 28, 2027))),
    case("in the winter", MON, span(d(12, 1), d(2, 28, 2027))),
    case("winter", SAT, span(d(12, 1), d(2, 28, 2027))),
    case("this winter", SAT, span(d(12, 1), d(2, 28, 2027))),
    case("spring", SAT, span(d(3, 1, 2027), d(5, 31, 2027))),
    case("summer", SAT, span(d(6, 1, 2027), d(8, 31, 2027))),
    case("spring", SUN, span(d(3, 1), d(5, 31))),
    case("this spring", SUN, span(d(3, 1), d(5, 31))),
    case("summer", SUN, span(d(6, 1), d(8, 31))),
    case("autumn", SUN, span(d(9, 1), d(11, 30))),
    case("winter", SUN, span(d(12, 1), d(2, 28, 2027))),
]


WEEKS_AND_WEEKENDS = [
    case("this week", MON, span(d(10, 19), d(10, 25))),
    case("next week", MON, span(d(10, 26), d(11, 1))),
    case("the week after next", MON, span(d(11, 2), d(11, 8))),
    case("later this week", MON, span(d(10, 20), d(10, 25))),
    case("this weekend", MON, span(d(10, 24), d(10, 25))),
    case("next weekend", MON, span(d(10, 31), d(11, 1), ambiguous=True)),
    case("end of the week", MON, span(d(10, 23), d(10, 25))),
    case("sometime next week", MON, span(d(10, 26), d(11, 1))),
    case("last week", MON, span(d(10, 12), d(10, 18))),
    case("this week", SAT, span(d(12, 26), d(12, 27))),
    case("next week", SAT, span(d(12, 28), d(1, 3, 2027))),
    case("the week after next", SAT, span(d(1, 4, 2027), d(1, 10, 2027))),
    # spec: tomorrow..Sunday is one day on a Saturday; whether that is kind "range" or "exact" is not stated
    case("later this week", SAT, only(start=d(12, 27), end=d(12, 27))),
    case("this weekend", SAT, span(d(12, 26), d(12, 27))),
    # spec: on a weekend day "the coming one" is the current weekend, so next weekend is the following one
    case("next weekend", SAT, span(d(1, 2, 2027), d(1, 3, 2027), ambiguous=True)),
    # spec: "Friday-Sunday of this week" is taken literally even when Friday is already past
    case("end of the week", SAT, span(d(12, 25), d(12, 27))),
    case("last week", SAT, span(d(12, 14), d(12, 20))),
    # spec: today..Sunday is one day on a Sunday; kind is not asserted
    case("this week", SUN, only(start=d(3, 1), end=d(3, 1))),
    case("next week", SUN, span(d(3, 2), d(3, 8))),
    case("the week after next", SUN, span(d(3, 9), d(3, 15))),
    case("this weekend", SUN, span(d(2, 28), d(3, 1))),
    # spec: same reading as the Saturday case
    case("next weekend", SUN, span(d(3, 7), d(3, 8), ambiguous=True)),
    case("end of the week", SUN, span(d(2, 27), d(3, 1))),
    case("last week", SUN, span(d(2, 16), d(2, 22))),
]


OFFSETS = [
    case("in 3 days", MON, exact(d(10, 22))),
    case("in three days", MON, exact(d(10, 22))),
    case("in 10 days", MON, exact(d(10, 29))),
    case("in ten days", MON, exact(d(10, 29))),
    case("in a week", MON, exact(d(10, 26))),
    case("in 2 weeks", MON, exact(d(11, 2))),
    case("in two weeks", MON, exact(d(11, 2))),
    case("in 3 weeks", MON, exact(d(11, 9))),
    case("in a fortnight", MON, exact(d(11, 2))),
    case("in a month", MON, exact(d(11, 19))),
    case("in 2 months", MON, exact(d(12, 19))),
    case("in six months", MON, exact(d(4, 19, 2027))),
    case("in 6 months", MON, exact(d(4, 19, 2027))),
    case("in 3 days", SAT, exact(d(12, 29))),
    case("in a week", SAT, exact(d(1, 2, 2027))),
    case("in a fortnight", SAT, exact(d(1, 9, 2027))),
    case("in a month", SAT, exact(d(1, 26, 2027))),
    case("in six months", SAT, exact(d(6, 26, 2027))),
    case("in a week", SUN, exact(d(3, 8))),
    case("in a fortnight", SUN, exact(d(3, 15))),
    case("in a month", SUN, exact(d(4, 1))),
]

# spec: none of the three standard todays falls on a 29th-31st, so clamping needs its own todays
MONTH_END_CLAMPING = [
    case("in a month", d(1, 31, 2027), exact(d(2, 28, 2027))),
    case("in a month", d(1, 31, 2028), exact(d(2, 29, 2028))),
    case("in a month", d(1, 30), exact(d(2, 28))),
    case("in a month", d(3, 31), exact(d(4, 30))),
    case("in a month", d(10, 31), exact(d(11, 30))),
    case("in a month", d(12, 31), exact(d(1, 31, 2027))),
    # spec: "in six months" uses the same same-day-clamped arithmetic as "in a month"
    case("in six months", d(8, 31), exact(d(2, 28, 2027))),
]

# Nominal value: couple = 2, few = 3, several = 4; days +-1, weeks +-3 days, months +-7 days.
# `ambiguous` is not asserted: the spec does not say whether approximate ranges are ambiguous.
APPROXIMATE_COUNTS = [
    case("in a couple of days", MON, only_range(d(10, 20), d(10, 22))),
    case("in a few days", MON, only_range(d(10, 21), d(10, 23))),
    case("in few days", MON, only_range(d(10, 21), d(10, 23))),
    case("in several days", MON, only_range(d(10, 22), d(10, 24))),
    case("in a couple of weeks", MON, only_range(d(10, 30), d(11, 5))),
    # spec: "couple" without "of" is the listed `couple` quantifier
    case("in a couple weeks", MON, only_range(d(10, 30), d(11, 5))),
    case("in couple of weeks", MON, only_range(d(10, 30), d(11, 5))),
    case("in a few weeks", MON, only_range(d(11, 6), d(11, 12))),
    case("in several weeks", MON, only_range(d(11, 13), d(11, 19))),
    case("in a couple of months", MON, only_range(d(12, 12), d(12, 26))),
    case("in a few months", MON, only_range(d(1, 12, 2027), d(1, 26, 2027))),
    case("in several months", MON, only_range(d(2, 12, 2027), d(2, 26, 2027))),
    case("in a couple of days", SAT, only_range(d(12, 27), d(12, 29))),
    case("in a few weeks", SAT, only_range(d(1, 13, 2027), d(1, 19, 2027))),
    case("in a couple of months", SAT, only_range(d(2, 19, 2027), d(3, 5, 2027))),
    case("in a few days", SUN, only_range(d(3, 3), d(3, 5))),
    case("in a couple of months", SUN, only_range(d(4, 24), d(5, 8))),
    # spec: the nominal month value is clamped like "in a month" (31 Dec + 2 months -> 28 Feb) before widening
    case("in a couple of months", d(12, 31), only_range(d(2, 21, 2027), d(3, 7, 2027))),
]


HOLIDAYS = [
    case("Christmas", MON, exact(d(12, 25))),
    case("Xmas", MON, exact(d(12, 25))),
    case("Christmas Day", MON, exact(d(12, 25))),
    # spec: "eve" is also the evening abbreviation; the holiday name wins and, like every holiday, sets no part of day
    case("Christmas Eve", MON, exact(d(12, 24))),
    case("Boxing Day", MON, exact(d(12, 26))),
    case("New Year's Eve", MON, exact(d(12, 31))),
    case("New Year's Day", MON, exact(d(1, 1, 2027))),
    case("New Year", MON, exact(d(1, 1, 2027))),
    case("Valentine's", MON, exact(d(2, 14, 2027))),
    case("Valentine's Day", MON, exact(d(2, 14, 2027))),
    case("Halloween", MON, exact(d(10, 31))),
    case("Easter", MON, exact(d(3, 28, 2027))),
    case("Easter Sunday", MON, exact(d(3, 28, 2027))),
    # spec: whether "bonfire night" sets part_of_day night is not stated
    case("bonfire night", MON, only_exact(d(11, 5))),
    case("after Christmas", MON, span(d(12, 26), d(12, 31), relation="after")),
    case("before Christmas", MON, span(d(10, 19), d(12, 24), relation="before")),
    case("before xmas", MON, span(d(10, 19), d(12, 24), relation="before")),
    case("Christmas", SAT, exact(d(12, 25, 2027))),
    case("Xmas", SAT, exact(d(12, 25, 2027))),
    case("Christmas Eve", SAT, exact(d(12, 24, 2027))),
    case("Boxing Day", SAT, exact(d(12, 26))),
    case("New Year's Eve", SAT, exact(d(12, 31))),
    case("New Year's Day", SAT, exact(d(1, 1, 2027))),
    case("New Year", SAT, exact(d(1, 1, 2027))),
    case("Valentine's Day", SAT, exact(d(2, 14, 2027))),
    case("Halloween", SAT, exact(d(10, 31, 2027))),
    case("Easter", SAT, exact(d(3, 28, 2027))),
    case("bonfire night", SAT, only_exact(d(11, 5, 2027))),
    # spec: Christmas is the next occurrence on or after today (25 Dec 2027), so "before" runs up to its eve
    case("before Christmas", SAT, span(d(12, 26), d(12, 24, 2027), relation="before")),
    case("Easter", SUN, exact(d(4, 5))),
    case("Easter Sunday", SUN, exact(d(4, 5))),
    case("Valentine's", SUN, exact(d(2, 14, 2027))),
    case("Halloween", SUN, exact(d(10, 31))),
    case("Christmas", SUN, exact(d(12, 25))),
    case("new year", SUN, exact(d(1, 1, 2027))),
]


# spec: clock times assert `time`, not part_of_day, which the spec does not tie to clock times.
TIMES = [
    case("3pm", MON, only_exact(d(10, 19), time="15:00", ambiguous=False, anaphoric=False)),
    case("3 pm", MON, only_exact(d(10, 19), time="15:00", ambiguous=False)),
    case("3PM", MON, only_exact(d(10, 19), time="15:00", ambiguous=False)),
    case("3:30pm", MON, only_exact(d(10, 19), time="15:30", ambiguous=False)),
    # spec: the bare-hour rule covers hours 1-12 only, so a 24h hour is not ambiguous
    case("15:00", MON, only_exact(d(10, 19), time="15:00", ambiguous=False)),
    case("at 3", MON, only_exact(d(10, 19), time="15:00", ambiguous=True)),
    case("at 1", MON, only_exact(d(10, 19), time="13:00", ambiguous=True)),
    case("at 6", MON, only_exact(d(10, 19), time="18:00", ambiguous=True)),
    case("at 7", MON, only_exact(d(10, 19), time="07:00", ambiguous=True)),
    case("at 11", MON, only_exact(d(10, 19), time="11:00", ambiguous=True)),
    case("at 12", MON, only_exact(d(10, 19), time="12:00", ambiguous=True)),
    # spec: the bare-hour rule applies to an hour with minutes but no am/pm
    case("at 6:45", MON, only_exact(d(10, 19), time="18:45", ambiguous=True)),
    # spec: British "half 9" is 09:30; no am/pm, so the bare-hour rule applies
    case("at half 9", MON, only_exact(d(10, 19), time="09:30", ambiguous=True)),
    case("half past nine", MON, only_exact(d(10, 19), time="09:30", ambiguous=True)),
    case("quarter past 2", MON, only_exact(d(10, 19), time="14:15", ambiguous=True)),
    case("quarter past two", MON, only_exact(d(10, 19), time="14:15", ambiguous=True)),
    case("quarter to 5", MON, only_exact(d(10, 19), time="16:45", ambiguous=True)),
    # spec: "three thirty" has no am/pm, so the bare-hour rule applies to its hour
    case("three thirty", MON, only_exact(d(10, 19), time="15:30", ambiguous=True)),
    case("ten thirty", MON, only_exact(d(10, 19), time="10:30", ambiguous=True)),
    case("at 9am", MON, only_exact(d(10, 19), time="09:00", ambiguous=False)),
    case("9 am", MON, only_exact(d(10, 19), time="09:00", ambiguous=False)),
    case("at 7pm", MON, only_exact(d(10, 19), time="19:00", ambiguous=False)),
    case("12pm", MON, only_exact(d(10, 19), time="12:00", ambiguous=False)),
    # spec: conventional 12am is midnight
    case("12am", MON, only(time="00:00", ambiguous=False)),
    case("noon", MON, only_exact(d(10, 19), time="12:00", ambiguous=False)),
    case("midday", MON, only_exact(d(10, 19), time="12:00", ambiguous=False)),
    # spec: whether midnight lands on today or tomorrow is not stated; only the clock is asserted
    case("midnight", MON, only(time="00:00")),
    # spec: "in the morning" supplies the am, so this is not a bare hour
    case("9 in the morning", MON, only_exact(d(10, 19), time="09:00", ambiguous=False)),
    case("lunchtime", MON, exact(d(10, 19), time="12:30", part_of_day="afternoon")),
    case("at lunchtime", MON, exact(d(10, 19), time="12:30", part_of_day="afternoon")),
    case("in the morning", MON, exact(d(10, 19), part_of_day="morning")),
    case("in the afternoon", MON, exact(d(10, 19), part_of_day="afternoon")),
    case("in the evening", MON, exact(d(10, 19), part_of_day="evening")),
    case("at night", MON, exact(d(10, 19), part_of_day="night")),
    case("morning", MON, exact(d(10, 19), part_of_day="morning")),
    case("evening", MON, exact(d(10, 19), part_of_day="evening")),
    case("at 3pm", SAT, only_exact(d(12, 26), time="15:00", ambiguous=False)),
    case("in the morning", SUN, exact(d(3, 1), part_of_day="morning")),
    # spec: a date plus a clock time composes like the weekday + time rule
    case("tomorrow at 3pm", MON, only_exact(d(10, 20), time="15:00", ambiguous=False)),
    case("tomorrow at half 9", MON, only_exact(d(10, 20), time="09:30", ambiguous=True)),
    case("tomorrow at noon", MON, only_exact(d(10, 20), time="12:00", ambiguous=False)),
    case("tomorrow lunchtime", MON, exact(d(10, 20), time="12:30", part_of_day="afternoon")),
    case("14 May at 10am", MON, only_exact(d(5, 14, 2027), time="10:00", ambiguous=False)),
    case("at 3pm", MON, only_exact(d(10, 23), time="15:00", anaphoric=True), anchor=FRIDAY_EVENT),
    case("at half 9", MON, only_exact(d(10, 23), time="09:30", ambiguous=True, anaphoric=True), anchor=FRIDAY_EVENT),
    case("in the morning", MON, exact(d(10, 23), part_of_day="morning", anaphoric=True), anchor=FRIDAY_EVENT),
    case("lunchtime", MON, exact(d(10, 23), time="12:30", part_of_day="afternoon", anaphoric=True), anchor=FRIDAY_EVENT),
    # spec: "exact on anchor's start" and "a range anchor gives a range" conflict here; only the shared facts are asserted
    case("in the morning", MON, only(start=d(10, 26), part_of_day="morning", anaphoric=True), anchor=NEXT_WEEK_EVENT),
    case("at 3pm", MON, only(start=d(10, 26), time="15:00", anaphoric=True), anchor=NEXT_WEEK_EVENT),
]


# spec: `relation` is set on every expression that means before/after its reference ("the day before",
# "the next day", "N days after"), not only on the afterwards/beforehand group, per the field's own definition.
ANAPHORIC_EXACT_ANCHOR = [
    case("that morning", MON, exact(d(10, 23), part_of_day="morning", anaphoric=True), anchor=FRIDAY_EVENT),
    case("that afternoon", MON, exact(d(10, 23), part_of_day="afternoon", anaphoric=True), anchor=FRIDAY_EVENT),
    case("that evening", MON, exact(d(10, 23), part_of_day="evening", anaphoric=True), anchor=FRIDAY_EVENT),
    case("that night", MON, exact(d(10, 23), part_of_day="night", anaphoric=True), anchor=FRIDAY_EVENT),
    case("that day", MON, exact(d(10, 23), anaphoric=True), anchor=FRIDAY_EVENT),
    case("on the day", MON, exact(d(10, 23), anaphoric=True), anchor=FRIDAY_EVENT),
    case("the morning of", MON, exact(d(10, 23), part_of_day="morning", anaphoric=True), anchor=FRIDAY_EVENT),
    case("the night before", MON, exact(d(10, 22), part_of_day="night", relation="before", anaphoric=True), anchor=FRIDAY_EVENT),
    case("the day before", MON, exact(d(10, 22), relation="before", anaphoric=True), anchor=FRIDAY_EVENT),
    case("the day after", MON, exact(d(10, 24), relation="after", anaphoric=True), anchor=FRIDAY_EVENT),
    case("the next day", MON, exact(d(10, 24), relation="after", anaphoric=True), anchor=FRIDAY_EVENT),
    case("the following day", MON, exact(d(10, 24), relation="after", anaphoric=True), anchor=FRIDAY_EVENT),
    case("the week before", MON, span(d(10, 16), d(10, 22), relation="before", anaphoric=True), anchor=FRIDAY_EVENT),
    case("the week after", MON, span(d(10, 24), d(10, 30), relation="after", anaphoric=True), anchor=FRIDAY_EVENT),
    # spec: "a week before/after" is an exact 7-day offset, unlike the ranged "the week before/after"
    case("a week before", MON, exact(d(10, 16), relation="before", anaphoric=True), anchor=FRIDAY_EVENT),
    case("a week after", MON, exact(d(10, 30), relation="after", anaphoric=True), anchor=FRIDAY_EVENT),
    case("3 days before", MON, exact(d(10, 20), relation="before", anaphoric=True), anchor=FRIDAY_EVENT),
    case("2 days after", MON, exact(d(10, 25), relation="after", anaphoric=True), anchor=FRIDAY_EVENT),
    case("three days after", MON, exact(d(10, 26), relation="after", anaphoric=True), anchor=FRIDAY_EVENT),
    # spec: "two weeks after" is an exact 14-day offset
    case("two weeks after", MON, exact(d(11, 6), relation="after", anaphoric=True), anchor=FRIDAY_EVENT),
    *(
        case(text, MON, exact(d(10, 24), relation="after", anaphoric=True), anchor=FRIDAY_EVENT)
        for text in ("afterwards", "after", "after it", "after that", "once it's done")
    ),
    *(
        case(text, MON, exact(d(10, 22), relation="before", anaphoric=True), anchor=FRIDAY_EVENT)
        for text in ("beforehand", "before", "before then")
    ),
    case("the next day", SAT, exact(d(1, 1, 2027), relation="after", anaphoric=True), anchor=exact(d(12, 31))),
    case("the week after", SAT, span(d(1, 1, 2027), d(1, 7, 2027), relation="after", anaphoric=True), anchor=exact(d(12, 31))),
]

# spec: before-relations use anchor.start and after-relations use anchor.end, which collapses a range anchor to one
# day, so those come back exact and unambiguous (the spec's own example: afterwards on 26 Oct-1 Nov -> 2 Nov).
# Expressions with no relation keep the whole range and are ambiguous.
ANAPHORIC_RANGE_ANCHOR = [
    case("afterwards", MON, exact(d(11, 2), relation="after", anaphoric=True), anchor=NEXT_WEEK_EVENT),
    case("after that", MON, exact(d(11, 2), relation="after", anaphoric=True), anchor=NEXT_WEEK_EVENT),
    case("beforehand", MON, exact(d(10, 25), relation="before", anaphoric=True), anchor=NEXT_WEEK_EVENT),
    case("the day before", MON, exact(d(10, 25), relation="before", anaphoric=True), anchor=NEXT_WEEK_EVENT),
    case("the night before", MON, exact(d(10, 25), part_of_day="night", relation="before", anaphoric=True), anchor=NEXT_WEEK_EVENT),
    case("the day after", MON, exact(d(11, 2), relation="after", anaphoric=True), anchor=NEXT_WEEK_EVENT),
    case("the next day", MON, exact(d(11, 2), relation="after", anaphoric=True), anchor=NEXT_WEEK_EVENT),
    case("2 days after", MON, exact(d(11, 3), relation="after", anaphoric=True), anchor=NEXT_WEEK_EVENT),
    # spec: whether a 7-day window measured from one end of the range is still "ambiguous" is not settled
    case("the week before", MON, only_range(d(10, 19), d(10, 25), relation="before", anaphoric=True), anchor=NEXT_WEEK_EVENT),
    case("the week after", MON, only_range(d(11, 2), d(11, 8), relation="after", anaphoric=True), anchor=NEXT_WEEK_EVENT),
    case("that day", MON, span(d(10, 26), d(11, 1), anaphoric=True, ambiguous=True), anchor=NEXT_WEEK_EVENT),
    case("on the day", MON, span(d(10, 26), d(11, 1), anaphoric=True, ambiguous=True), anchor=NEXT_WEEK_EVENT),
    case("that morning", MON, span(d(10, 26), d(11, 1), part_of_day="morning", anaphoric=True, ambiguous=True), anchor=NEXT_WEEK_EVENT),
]

ANAPHORIC_WITHOUT_ANCHOR = [
    case("afterwards", MON, Resolution(kind="unparsed", relation="after", anaphoric=True)),
    case("after that", MON, Resolution(kind="unparsed", relation="after", anaphoric=True)),
    case("once it's done", MON, Resolution(kind="unparsed", relation="after", anaphoric=True)),
    case("beforehand", MON, Resolution(kind="unparsed", relation="before", anaphoric=True)),
    case("before then", MON, Resolution(kind="unparsed", relation="before", anaphoric=True)),
    case("that morning", MON, Resolution(kind="unparsed", part_of_day="morning", anaphoric=True)),
    case("that evening", MON, Resolution(kind="unparsed", part_of_day="evening", anaphoric=True)),
    case("the morning of", MON, Resolution(kind="unparsed", part_of_day="morning", anaphoric=True)),
    case("that day", MON, Resolution(kind="unparsed", anaphoric=True)),
    case("on the day", MON, Resolution(kind="unparsed", anaphoric=True)),
    case("the day before", MON, Resolution(kind="unparsed", relation="before", anaphoric=True)),
    case("the night before", MON, Resolution(kind="unparsed", part_of_day="night", relation="before", anaphoric=True)),
    case("the next day", MON, Resolution(kind="unparsed", relation="after", anaphoric=True)),
    case("the week after", MON, Resolution(kind="unparsed", relation="after", anaphoric=True)),
    case("3 days before", MON, Resolution(kind="unparsed", relation="before", anaphoric=True)),
    # spec: an anchor with no dates gives nothing to resolve against, so it behaves like no anchor
    case("afterwards", MON, only(kind="unparsed", relation="after", anaphoric=True), anchor=UNPARSED),
    case("beforehand", MON, only(kind="unparsed", relation="before", anaphoric=True), anchor=VAGUE),
]

# Expressions relative to today ignore an anchor and stay non-anaphoric.
NON_ANAPHORIC_WITH_ANCHOR = [
    case("tomorrow", MON, exact(d(10, 20)), anchor=FRIDAY_EVENT),
    case("next week", MON, span(d(10, 26), d(11, 1)), anchor=NEXT_WEEK_EVENT),
    case("Christmas", MON, exact(d(12, 25)), anchor=FRIDAY_EVENT),
    case("14 May", MON, exact(d(5, 14, 2027)), anchor=NEXT_WEEK_EVENT),
]


BEFORE_AFTER_A_DATE = [
    case("before Friday", MON, span(d(10, 19), d(10, 22), relation="before")),
    case("before Monday", MON, span(d(10, 19), d(10, 25), relation="before")),
    case("before the 14th", MON, span(d(10, 19), d(11, 13), relation="before")),
    case("before 14 May", MON, span(d(10, 19), d(5, 13, 2027), relation="before")),
    case("after Friday", MON, exact(d(10, 24), relation="after")),
    case("after Sunday", MON, exact(d(10, 26), relation="after")),
    case("after the 14th", MON, exact(d(11, 15), relation="after")),
    case("after 14 May", MON, exact(d(5, 15, 2027), relation="after")),
    # spec: "treat like before Friday but include Friday" keeps relation "before". "by" is also a tolerated
    # leading preposition, but this specific rule must win over stripping it.
    case("by Friday", MON, span(d(10, 19), d(10, 23), relation="before")),
    case("by Tuesday", MON, span(d(10, 19), d(10, 20), relation="before")),
    case("by the 14th", MON, span(d(10, 19), d(11, 14), relation="before")),
    case("by tmrw", MON, span(d(10, 19), d(10, 20), relation="before")),
    case("before Friday", SAT, span(d(12, 26), d(12, 31), relation="before")),
    case("by Friday", SAT, span(d(12, 26), d(1, 1, 2027), relation="before")),
    case("by Monday", SAT, span(d(12, 26), d(12, 28), relation="before")),
    case("after Sunday", SAT, exact(d(12, 28), relation="after")),
    case("by Friday", SUN, span(d(3, 1), d(3, 6), relation="before")),
]


VAGUE_EXPRESSIONS = [
    *(case(text, MON, VAGUE) for text in ("soon", "at some point", "sometime", "later", "one day", "when I can", "eventually", "in a bit")),
    case("Soon!", MON, VAGUE),
    case("SOMETIME", MON, VAGUE),
    case("um, at some point", MON, VAGUE),
    case("sometime next week", SAT, span(d(12, 28), d(1, 3, 2027))),
    case("at some point next week", MON, span(d(10, 26), d(11, 1))),
    case("at some point in March", MON, span(d(3, 1, 2027), d(3, 31, 2027))),
    case("sometime in November", MON, span(d(11, 1), d(11, 30))),
    case("at some point next month", MON, span(d(11, 1), d(11, 30))),
    case("sometime this weekend", MON, span(d(10, 24), d(10, 25))),
    case("sometime over the summer", MON, span(d(6, 1, 2027), d(8, 31, 2027))),
]


FILLERS_PUNCTUATION_AND_CASE = [
    case("um tomorrow", MON, exact(d(10, 20))),
    case("uh tomorrow", MON, exact(d(10, 20))),
    case("so tomorrow", MON, exact(d(10, 20))),
    # spec: a comma after a filler is the "punctuation" the spec says spans may contain
    case("um, tomorrow", MON, exact(d(10, 20))),
    case("like next week", MON, span(d(10, 26), d(11, 1))),
    case("on Friday", MON, exact(d(10, 23))),
    case("for Friday", MON, exact(d(10, 23))),
    case("for next week", MON, span(d(10, 26), d(11, 1))),
    case("on the 3rd", SAT, exact(d(1, 3, 2027))),
    case("around 3pm", MON, only_exact(d(10, 19), time="15:00")),
    case("about 3pm", MON, only_exact(d(10, 19), time="15:00")),
    # spec: "around" is a listed leading preposition to tolerate, so it does not widen the date
    case("around Christmas", MON, only_exact(d(12, 25))),
    # spec: several leading fillers/prepositions chain
    case("um so on friday", MON, exact(d(10, 23))),
    case("tomorrow.", MON, exact(d(10, 20))),
    case("tomorrow!", MON, exact(d(10, 20))),
    case("tomorrow,", MON, exact(d(10, 20))),
    case("tomorrow...", MON, exact(d(10, 20))),
    case("next week?", MON, span(d(10, 26), d(11, 1))),
    case("Friday!", MON, exact(d(10, 23))),
    case("Christmas.", MON, exact(d(12, 25))),
    # spec: surrounding whitespace is part of tolerating a labelled span as typed
    case("  tomorrow  ", MON, exact(d(10, 20))),
    case("TOMORROW", MON, exact(d(10, 20))),
    case("Next Week", MON, span(d(10, 26), d(11, 1))),
    case("NEXT FRIDAY", MON, exact(d(10, 30), ambiguous=True)),
    case("CHRISTMAS EVE", MON, exact(d(12, 24))),
    case("Mid-March", MON, span(d(3, 11, 2027), d(3, 20, 2027))),
    case("In A Fortnight", MON, exact(d(11, 2))),
    # spec: typed and iOS-keyboard apostrophes must not change the holiday
    case("new years eve", MON, exact(d(12, 31))),
    case("valentines day", MON, exact(d(2, 14, 2027))),
    case("New Year’s Day", MON, exact(d(1, 1, 2027))),
]

ABBREVIATIONS = [
    *(case(text, MON, exact(d(10, 20))) for text in ("tmrw", "tmw", "tomoz", "2moro", "Tmrw")),
    case("tmrw morning", MON, exact(d(10, 20), part_of_day="morning")),
    # spec: "eve" after a day is the evening abbreviation
    case("tmrw eve", MON, exact(d(10, 20), part_of_day="evening")),
    case("this eve", MON, exact(d(10, 19), part_of_day="evening")),
    case("fri eve", MON, exact(d(10, 23), part_of_day="evening")),
    case("tues", MON, exact(d(10, 20))),
    case("weds", MON, exact(d(10, 21))),
    case("thurs", MON, exact(d(10, 22))),
    case("fri", MON, exact(d(10, 23))),
    case("sat", MON, exact(d(10, 24))),
    case("mon", MON, only_exact(d(10, 26))),
    case("this fri", MON, exact(d(10, 23))),
    case("next thurs", MON, exact(d(10, 29), ambiguous=True)),
    case("next mon", MON, exact(d(10, 26), ambiguous=True)),
    case("fri week", MON, only_exact(d(10, 30))),
    case("a week on fri", MON, only_exact(d(10, 30))),
    case("last fri", MON, only_exact(d(10, 16))),
    case("thurs 3pm", MON, only_exact(d(10, 22), time="15:00")),
    case("sept", MON, span(d(9, 1, 2027), d(9, 30, 2027))),
    case("nxt wk", MON, span(d(10, 26), d(11, 1))),
    case("next wk", MON, span(d(10, 26), d(11, 1))),
    case("this wk", MON, span(d(10, 19), d(10, 25))),
    case("in a wk", MON, exact(d(10, 26))),
    case("this wknd", MON, span(d(10, 24), d(10, 25))),
    case("nxt wknd", MON, span(d(10, 31), d(11, 1), ambiguous=True)),
    case("sat", SAT, only_exact(d(1, 2, 2027))),
    case("this sat", SAT, exact(d(12, 26))),
]

# Phrases that share letters with a rule and must not be mistaken for it.
LOOKALIKES = [
    case("this month", SUN, span(d(3, 1), d(3, 31))),
    # spec: "nothing recognised" means whole words; a rule word inside another word is not a match
    *(
        case(text, MON, UNPARSED)
        for text in ("fridge", "saturn", "monkey", "sunny", "wedding", "marching", "maybe", "tomorrowland", "nightingale")
    ),
]

UNPARSED_INPUTS = [
    *(
        case(text, MON, UNPARSED)
        for text in ("", "   ", "\n", "banana", "um", "uh, like", "the", "?!", "...", "next", "last", "this", "mañana", "🎉", "call mum")
    ),
]

# Inputs whose result the spec does not pin down, beyond "never raise" and the Resolution invariants.
MUST_NOT_RAISE = [
    "x" * 5000,
    "1/" * 200,
    "\x00",
    "in 999999999 days",
    "in 99999 months",
    "in 999999999 weeks",
    "14/05/0000",
    "31/12/99999",
    "the 99999th",
    "25:00",
    "13pm",
    "99:99",
    "0/0/0",
    "at half",
    "quarter to",
    "in a couple of",
    "next next next",
    "by",
    "before after",
    "    um    ",
]


def get_invariant_violations(result: Resolution) -> list[str]:
    if not isinstance(result, Resolution):
        return [f"not a Resolution: {result!r}"]

    checks = {
        "kind is one of the four kinds": result.kind in KINDS,
        "part_of_day is a known part": result.part_of_day in PARTS_OF_DAY,
        "relation is before/after/None": result.relation in RELATIONS,
        "flags are bools": isinstance(result.anaphoric, bool) and isinstance(result.ambiguous, bool),
        "time is HH:MM 24h": result.time is None or bool(CLOCK.fullmatch(result.time)),
        "exact has start == end": result.kind != "exact" or (result.start is not None and result.start == result.end),
        "range has start <= end": result.kind != "range" or (None not in (result.start, result.end) and result.start <= result.end),
        "unparsed has no dates": result.kind != "unparsed" or (result.start is None and result.end is None),
    }
    return [f"{rule}: {result!r}" for rule, holds in checks.items() if not holds]


@pytest.mark.parametrize("c", DEICTIC)
def test_deictic_days_resolve_against_today(c):
    assert_case(c)


@pytest.mark.parametrize("c", WEEKDAY_SEMANTICS)
def test_weekday_forms_pick_the_spec_occurrence(c):
    assert_case(c)


@pytest.mark.parametrize("c", WEEKDAY_WITH_TIME)
def test_weekday_with_part_of_day_or_time(c):
    assert_case(c)


@pytest.mark.parametrize("c", CALENDAR_DATES)
def test_calendar_dates_are_future_biased_without_a_year(c):
    assert_case(c)


@pytest.mark.parametrize("c", NUMERIC_DATES)
def test_numeric_dates_follow_day_first_with_fallback(c):
    assert_case(c)


@pytest.mark.parametrize("c", DAY_OF_MONTH)
def test_day_of_month_rolls_to_next_month_once_past(c):
    assert_case(c)


@pytest.mark.parametrize("c", MONTHS)
def test_months_resolve_to_whole_or_sliced_month_ranges(c):
    assert_case(c)


@pytest.mark.parametrize("c", SEASONS)
def test_seasons_resolve_to_northern_hemisphere_ranges(c):
    assert_case(c)


@pytest.mark.parametrize("c", WEEKS_AND_WEEKENDS)
def test_weeks_start_on_monday_and_weekends_track_today(c):
    assert_case(c)


@pytest.mark.parametrize("c", OFFSETS)
def test_offsets_from_today_are_exact(c):
    assert_case(c)


@pytest.mark.parametrize("c", MONTH_END_CLAMPING)
def test_month_offsets_clamp_to_month_end(c):
    assert_case(c)


@pytest.mark.parametrize("c", APPROXIMATE_COUNTS)
def test_approximate_counts_widen_into_ranges(c):
    assert_case(c)


@pytest.mark.parametrize("c", HOLIDAYS)
def test_holidays_resolve_to_next_occurrence(c):
    assert_case(c)


@pytest.mark.parametrize("c", TIMES)
def test_times_set_clock_and_resolve_their_date(c):
    assert_case(c)


@pytest.mark.parametrize("c", ANAPHORIC_EXACT_ANCHOR)
def test_anaphoric_expressions_resolve_against_an_exact_anchor(c):
    assert_case(c)


@pytest.mark.parametrize("c", ANAPHORIC_RANGE_ANCHOR)
def test_anaphoric_expressions_resolve_against_a_range_anchor(c):
    assert_case(c)


@pytest.mark.parametrize("c", ANAPHORIC_WITHOUT_ANCHOR)
def test_anaphoric_expressions_without_an_anchor_are_unparsed(c):
    assert_case(c)


@pytest.mark.parametrize("c", NON_ANAPHORIC_WITH_ANCHOR)
def test_today_relative_expressions_ignore_the_anchor(c):
    assert_case(c)


@pytest.mark.parametrize("c", BEFORE_AFTER_A_DATE)
def test_before_after_and_by_a_date(c):
    assert_case(c)


@pytest.mark.parametrize("c", VAGUE_EXPRESSIONS)
def test_vague_words_are_vague_unless_a_date_is_attached(c):
    assert_case(c)


@pytest.mark.parametrize("c", FILLERS_PUNCTUATION_AND_CASE)
def test_fillers_punctuation_and_case_are_tolerated(c):
    assert_case(c)


@pytest.mark.parametrize("c", ABBREVIATIONS)
def test_abbreviations_are_understood(c):
    assert_case(c)


@pytest.mark.parametrize("c", LOOKALIKES)
def test_lookalike_phrases_are_not_confused(c):
    assert_case(c)


@pytest.mark.parametrize("c", UNPARSED_INPUTS)
def test_unrecognised_input_is_unparsed(c):
    assert_case(c)


@pytest.mark.parametrize("text", MUST_NOT_RAISE)
@pytest.mark.parametrize("today", [MON, SAT, SUN], ids=str)
def test_hostile_input_never_raises(text, today):
    assert get_invariant_violations(resolve(text, today)) == []


ALL_CASES = [
    p.values[0]
    for table in (
        DEICTIC,
        WEEKDAY_SEMANTICS,
        WEEKDAY_WITH_TIME,
        CALENDAR_DATES,
        NUMERIC_DATES,
        DAY_OF_MONTH,
        MONTHS,
        SEASONS,
        WEEKS_AND_WEEKENDS,
        OFFSETS,
        MONTH_END_CLAMPING,
        APPROXIMATE_COUNTS,
        HOLIDAYS,
        TIMES,
        ANAPHORIC_EXACT_ANCHOR,
        ANAPHORIC_RANGE_ANCHOR,
        ANAPHORIC_WITHOUT_ANCHOR,
        NON_ANAPHORIC_WITH_ANCHOR,
        BEFORE_AFTER_A_DATE,
        VAGUE_EXPRESSIONS,
        FILLERS_PUNCTUATION_AND_CASE,
        ABBREVIATIONS,
        LOOKALIKES,
        UNPARSED_INPUTS,
    )
    for p in table
]


def test_every_result_satisfies_the_resolution_invariants():
    violations = {label(c): found for c in ALL_CASES if (found := get_invariant_violations(run(c)))}

    assert violations == {}


def test_resolution_is_frozen():
    resolution = exact(d(10, 19))

    with pytest.raises(dataclasses.FrozenInstanceError):
        resolution.kind = "range"  # type: ignore[misc]
