from datetime import date

import pytest

from memo_extract.dates import Resolution, easter_sunday, resolve

MONDAY = date(2026, 10, 19)
SATURDAY = date(2026, 12, 26)

UNPARSED = Resolution("unparsed")
VAGUE = Resolution("vague")


def d(month, day, year=2026):
    return date(year, month, day)


def exact(day, **fields):
    return Resolution("exact", day, day, **fields)


def span(start, end, **fields):
    return Resolution("range", start, end, **fields)


def anaphoric(**fields):
    return Resolution("unparsed", anaphoric=True, **fields)


def cases(table):
    return pytest.mark.parametrize("text, expected", table, ids=[text for text, _ in table])


DEICTIC = [
    ("today", exact(d(10, 19))),
    ("tonight", exact(d(10, 19), part_of_day="night")),
    ("this morning", exact(d(10, 19), part_of_day="morning")),
    ("this afternoon", exact(d(10, 19), part_of_day="afternoon")),
    ("this evening", exact(d(10, 19), part_of_day="evening")),
    ("tomorrow", exact(d(10, 20))),
    ("tmrw", exact(d(10, 20))),
    ("tmw", exact(d(10, 20))),
    ("tomoz", exact(d(10, 20))),
    ("2moro", exact(d(10, 20))),
    ("Tomorrow morning", exact(d(10, 20), part_of_day="morning")),
    ("tomorrow afternoon", exact(d(10, 20), part_of_day="afternoon")),
    ("tomorrow evening", exact(d(10, 20), part_of_day="evening")),
    ("tmrw eve", exact(d(10, 20), part_of_day="evening")),
    ("tomorrow night", exact(d(10, 20), part_of_day="night")),
    ("the day after tomorrow", exact(d(10, 21))),
    ("yesterday", exact(d(10, 18))),
    ("last night", exact(d(10, 18), part_of_day="night")),
    ("Um, TOMORROW.", exact(d(10, 20))),
    ("uh like so tomorrow!!", exact(d(10, 20))),
]

WEEKDAYS = [
    ("Friday", exact(d(10, 23))),
    ("fri", exact(d(10, 23))),
    ("on Friday", exact(d(10, 23))),
    ("Monday", exact(d(10, 26))),
    ("tues", exact(d(10, 20))),
    ("weds", exact(d(10, 21))),
    ("thurs", exact(d(10, 22))),
    ("sat", exact(d(10, 24))),
    ("this Friday", exact(d(10, 23))),
    ("this Monday", exact(d(10, 19))),
    ("next Friday", exact(d(10, 30), ambiguous=True)),
    ("next Monday", exact(d(10, 26), ambiguous=True)),
    ("nxt tues", exact(d(10, 27), ambiguous=True)),
    ("Friday week", exact(d(10, 30))),
    ("a week on Friday", exact(d(10, 30))),
    ("last Friday", exact(d(10, 16))),
    ("last Monday", exact(d(10, 12))),
    ("Friday morning", exact(d(10, 23), part_of_day="morning")),
    ("Friday at 3pm", exact(d(10, 23), time="15:00")),
    ("fri 3pm", exact(d(10, 23), time="15:00")),
    ("friday next week", exact(d(10, 30))),
    ("friday the 23rd", exact(d(10, 23))),
    ("friday the 24th", exact(d(10, 24), ambiguous=True)),
]

CALENDAR_DATES = [
    ("14 May", exact(d(5, 14, 2027))),
    ("14th May", exact(d(5, 14, 2027))),
    ("14th of May", exact(d(5, 14, 2027))),
    ("May 14", exact(d(5, 14, 2027))),
    ("May 14th", exact(d(5, 14, 2027))),
    ("the fourteenth of may", exact(d(5, 14, 2027))),
    ("may fourteenth", exact(d(5, 14, 2027))),
    ("the twenty first of may", exact(d(5, 21, 2027))),
    ("14 May 2027", exact(d(5, 14, 2027))),
    ("May 14, 2027", exact(d(5, 14, 2027))),
    ("14 May 2026", exact(d(5, 14, 2026))),
    ("2 November 2026", exact(d(11, 2))),
    ("sept 14", exact(d(9, 14, 2027))),
    ("19 October", exact(d(10, 19))),
    ("18 October", exact(d(10, 18, 2027))),
    ("14/05", exact(d(5, 14, 2027))),
    ("14/5", exact(d(5, 14, 2027))),
    ("14.05", exact(d(5, 14, 2027))),
    ("14/05/2027", exact(d(5, 14, 2027))),
    ("14/05/27", exact(d(5, 14, 2027))),
    ("5/14", exact(d(5, 14, 2027))),
    ("5/6", exact(d(6, 5, 2027))),
    ("2026-11-02", exact(d(11, 2))),
    ("the 3rd", exact(d(11, 3))),
    ("the 19th", exact(d(10, 19))),
    ("the 31st", exact(d(10, 31))),
    ("the fourteenth", exact(d(11, 14))),
    ("29 feb", exact(d(2, 29, 2028))),
    ("31 June", UNPARSED),
    ("31/06", UNPARSED),
    ("30 february 2027", UNPARSED),
    ("13/13", UNPARSED),
]

MONTHS_AND_SEASONS = [
    ("March", span(d(3, 1, 2027), d(3, 31, 2027))),
    ("in March", span(d(3, 1, 2027), d(3, 31, 2027))),
    ("October", span(d(10, 1), d(10, 31))),
    ("September", span(d(9, 1, 2027), d(9, 30, 2027))),
    ("early March", span(d(3, 1, 2027), d(3, 10, 2027))),
    ("mid March", span(d(3, 11, 2027), d(3, 20, 2027))),
    ("mid-March", span(d(3, 11, 2027), d(3, 20, 2027))),
    ("late March", span(d(3, 21, 2027), d(3, 31, 2027))),
    ("end of March", span(d(3, 21, 2027), d(3, 31, 2027))),
    ("late October", span(d(10, 21), d(10, 31))),
    ("early October", span(d(10, 1, 2027), d(10, 10, 2027))),
    ("late feb", span(d(2, 21, 2027), d(2, 28, 2027))),
    ("March 2027", span(d(3, 1, 2027), d(3, 31, 2027))),
    ("next March", span(d(3, 1, 2027), d(3, 31, 2027))),
    ("next October", span(d(10, 1, 2027), d(10, 31, 2027))),
    ("last March", span(d(3, 1), d(3, 31))),
    ("next month", span(d(11, 1), d(11, 30))),
    ("this month", span(d(10, 1), d(10, 31))),
    ("last month", span(d(9, 1), d(9, 30))),
    ("end of the month", span(d(10, 21), d(10, 31))),
    ("end of next month", span(d(11, 21), d(11, 30))),
    ("beginning of next month", span(d(11, 1), d(11, 10))),
    ("spring", span(d(3, 1, 2027), d(5, 31, 2027))),
    ("summer", span(d(6, 1, 2027), d(8, 31, 2027))),
    ("autumn", span(d(9, 1), d(11, 30))),
    ("fall", span(d(9, 1), d(11, 30))),
    ("winter", span(d(12, 1), d(2, 28, 2027))),
    ("this summer", span(d(6, 1, 2027), d(8, 31, 2027))),
    ("next summer", span(d(6, 1, 2027), d(8, 31, 2027))),
    ("over the summer", span(d(6, 1, 2027), d(8, 31, 2027))),
    ("in the summer", span(d(6, 1, 2027), d(8, 31, 2027))),
    ("this autumn", span(d(9, 1), d(11, 30))),
    ("next autumn", span(d(9, 1, 2027), d(11, 30, 2027))),
    ("last winter", span(d(12, 1, 2025), d(2, 28))),
    ("summer 2028", span(d(6, 1, 2028), d(8, 31, 2028))),
]

WEEKS_AND_WEEKENDS = [
    ("this week", span(d(10, 19), d(10, 25))),
    ("next week", span(d(10, 26), d(11, 1))),
    ("nxt wk", span(d(10, 26), d(11, 1))),
    ("the week after next", span(d(11, 2), d(11, 8))),
    ("later this week", span(d(10, 20), d(10, 25))),
    ("this weekend", span(d(10, 24), d(10, 25))),
    ("this wknd", span(d(10, 24), d(10, 25))),
    ("at the weekend", span(d(10, 24), d(10, 25))),
    ("next weekend", span(d(10, 31), d(11, 1), ambiguous=True)),
    ("last weekend", span(d(10, 17), d(10, 18))),
    ("end of the week", span(d(10, 23), d(10, 25))),
    ("end of next week", span(d(10, 30), d(11, 1))),
    ("beginning of next week", span(d(10, 26), d(10, 27))),
    ("sometime next week", span(d(10, 26), d(11, 1))),
    ("last week", span(d(10, 12), d(10, 18))),
    ("next year", span(d(1, 1, 2027), d(12, 31, 2027))),
]

OFFSETS = [
    ("in 3 days", exact(d(10, 22))),
    ("in three days", exact(d(10, 22))),
    ("in a week", exact(d(10, 26))),
    ("in 2 weeks", exact(d(11, 2))),
    ("in two weeks time", exact(d(11, 2))),
    ("in a fortnight", exact(d(11, 2))),
    ("in a month", exact(d(11, 19))),
    ("in six months", exact(d(4, 19, 2027))),
    ("in a year", exact(d(10, 19, 2027))),
    ("in a couple of days", span(d(10, 20), d(10, 22))),
    ("in a few days", span(d(10, 21), d(10, 23))),
    ("in several days", span(d(10, 22), d(10, 24))),
    ("in couple weeks", span(d(10, 30), d(11, 5))),
    ("in a couple of weeks", span(d(10, 30), d(11, 5))),
    ("in a few weeks", span(d(11, 6), d(11, 12))),
    ("in a couple of months", span(d(12, 12), d(12, 26))),
    ("in a few months", span(d(1, 12, 2027), d(1, 26, 2027))),
]

HOLIDAYS = [
    ("Christmas", exact(d(12, 25))),
    ("Xmas", exact(d(12, 25))),
    ("Christmas Day", exact(d(12, 25))),
    ("Christmas Eve", exact(d(12, 24))),
    ("xmas eve", exact(d(12, 24))),
    ("christmas morning", exact(d(12, 25), part_of_day="morning")),
    ("Boxing Day", exact(d(12, 26))),
    ("New Year's Eve", exact(d(12, 31))),
    ("New Year's Day", exact(d(1, 1, 2027))),
    ("New Year", exact(d(1, 1, 2027))),
    ("Valentine's", exact(d(2, 14, 2027))),
    ("Valentine's Day", exact(d(2, 14, 2027))),
    ("Halloween", exact(d(10, 31))),
    ("Easter", exact(d(3, 28, 2027))),
    ("Easter Sunday", exact(d(3, 28, 2027))),
    ("good friday", exact(d(3, 26, 2027))),
    ("bonfire night", exact(d(11, 5))),
    ("christmas 2027", exact(d(12, 25, 2027))),
    ("after Christmas", span(d(12, 26), d(12, 31), relation="after")),
    ("before Christmas", span(d(10, 19), d(12, 24), relation="before")),
    ("the day before christmas", exact(d(12, 24), relation="before")),
]

TIMES = [
    ("3pm", exact(d(10, 19), time="15:00")),
    ("3 pm", exact(d(10, 19), time="15:00")),
    ("3 p.m.", exact(d(10, 19), time="15:00")),
    ("3:30pm", exact(d(10, 19), time="15:30")),
    ("12am", exact(d(10, 19), time="00:00")),
    ("15:00", exact(d(10, 19), time="15:00")),
    ("09:30", exact(d(10, 19), time="09:30")),
    ("9:30", exact(d(10, 19), time="09:30", ambiguous=True)),
    ("at 3", exact(d(10, 19), time="15:00", ambiguous=True)),
    ("at 7", exact(d(10, 19), time="07:00", ambiguous=True)),
    ("at 12", exact(d(10, 19), time="12:00", ambiguous=True)),
    ("at 6", exact(d(10, 19), time="18:00", ambiguous=True)),
    ("at 15", exact(d(10, 19), time="15:00")),
    ("at 3.30", exact(d(10, 19), time="15:30", ambiguous=True)),
    ("3 o'clock", exact(d(10, 19), time="15:00", ambiguous=True)),
    ("at half 9", exact(d(10, 19), time="09:30", ambiguous=True)),
    ("half past nine", exact(d(10, 19), time="09:30", ambiguous=True)),
    ("quarter past 2", exact(d(10, 19), time="14:15", ambiguous=True)),
    ("quarter to 5", exact(d(10, 19), time="16:45", ambiguous=True)),
    ("quarter to 7", exact(d(10, 19), time="06:45", ambiguous=True)),
    ("twenty past three", exact(d(10, 19), time="15:20", ambiguous=True)),
    ("noon", exact(d(10, 19), time="12:00")),
    ("midday", exact(d(10, 19), time="12:00")),
    ("midnight", exact(d(10, 19), time="00:00")),
    ("lunchtime", exact(d(10, 19), time="12:30", part_of_day="afternoon")),
    ("9 in the morning", exact(d(10, 19), time="09:00", part_of_day="morning")),
    ("7 in the evening", exact(d(10, 19), time="19:00", part_of_day="evening")),
    ("three thirty", exact(d(10, 19), time="15:30", ambiguous=True)),
    ("in the morning", exact(d(10, 19), part_of_day="morning")),
    ("afternoon", exact(d(10, 19), part_of_day="afternoon")),
    ("tonight at 8", exact(d(10, 19), time="20:00", part_of_day="night")),
    ("8 tonight", exact(d(10, 19), time="20:00", part_of_day="night")),
    ("tomorrow at 7 in the evening", exact(d(10, 20), time="19:00", part_of_day="evening")),
    ("tomorrow morning at 9", exact(d(10, 20), time="09:00", part_of_day="morning")),
    ("14 May at 9", exact(d(5, 14, 2027), time="09:00", ambiguous=True)),
    ("3pm tomorrow", exact(d(10, 20), time="15:00")),
    ("before 3pm", exact(d(10, 19), time="15:00", relation="before")),
    ("by 3pm", exact(d(10, 19), time="15:00", relation="before")),
    ("after 3pm", exact(d(10, 19), time="15:00", relation="after")),
]

ANAPHORIC_WITHOUT_ANCHOR = [
    ("that morning", anaphoric(part_of_day="morning")),
    ("that day", anaphoric()),
    ("on the day", anaphoric()),
    ("the morning of", anaphoric(part_of_day="morning")),
    ("the night before", anaphoric(relation="before", part_of_day="night")),
    ("the day before", anaphoric(relation="before")),
    ("the day after", anaphoric(relation="after")),
    ("the next day at 9am", anaphoric(relation="after", time="09:00")),
    ("the week before", anaphoric(relation="before")),
    ("two weeks after", anaphoric(relation="after")),
    ("afterwards", anaphoric(relation="after")),
    ("once it's done", anaphoric(relation="after")),
    ("beforehand", anaphoric(relation="before")),
    ("before then", anaphoric(relation="before")),
]

VAGUE_EXPRESSIONS = [
    ("soon", VAGUE),
    ("at some point", VAGUE),
    ("sometime", VAGUE),
    ("later", VAGUE),
    ("one day", VAGUE),
    ("when I can", VAGUE),
    ("eventually", VAGUE),
    ("in a bit", VAGUE),
    ("sometime soon", VAGUE),
    ("sometime around the wedding", VAGUE),
    ("at some point in March", span(d(3, 1, 2027), d(3, 31, 2027))),
    ("next week sometime", span(d(10, 26), d(11, 1))),
    ("sometime tomorrow", exact(d(10, 20))),
    ("later today", exact(d(10, 19))),
]

RELATIVE_TO_DATES = [
    ("before Friday", span(d(10, 19), d(10, 22), relation="before")),
    ("by Friday", span(d(10, 19), d(10, 23), relation="before")),
    ("after Friday", exact(d(10, 24), relation="after")),
    ("after the 14th", exact(d(11, 15), relation="after")),
    ("before next week", span(d(10, 19), d(10, 25), relation="before")),
    ("by the end of the month", span(d(10, 19), d(10, 31), relation="before")),
    ("before tomorrow", exact(d(10, 19), relation="before")),
    ("after next friday", exact(d(10, 31), relation="after", ambiguous=True)),
]

UNPARSEABLE = [
    ("", UNPARSED),
    ("   ", UNPARSED),
    ("um", UNPARSED),
    ("the wedding", UNPARSED),
    ("blah at 3pm", UNPARSED),
    ("before the party", UNPARSED),
    ("a week before the party", UNPARSED),
]


class TestResolveOnMonday:
    @cases(DEICTIC)
    def test_deictic_days(self, text, expected):
        assert resolve(text, MONDAY) == expected

    @cases(WEEKDAYS)
    def test_weekdays(self, text, expected):
        assert resolve(text, MONDAY) == expected

    @cases(CALENDAR_DATES)
    def test_calendar_dates(self, text, expected):
        assert resolve(text, MONDAY) == expected

    @cases(MONTHS_AND_SEASONS)
    def test_months_and_seasons(self, text, expected):
        assert resolve(text, MONDAY) == expected

    @cases(WEEKS_AND_WEEKENDS)
    def test_weeks_and_weekends(self, text, expected):
        assert resolve(text, MONDAY) == expected

    @cases(OFFSETS)
    def test_offsets_from_today(self, text, expected):
        assert resolve(text, MONDAY) == expected

    @cases(HOLIDAYS)
    def test_holidays(self, text, expected):
        assert resolve(text, MONDAY) == expected

    @cases(TIMES)
    def test_times(self, text, expected):
        assert resolve(text, MONDAY) == expected

    @cases(ANAPHORIC_WITHOUT_ANCHOR)
    def test_anaphoric_without_anchor_is_unparsed(self, text, expected):
        assert resolve(text, MONDAY) == expected

    @cases(VAGUE_EXPRESSIONS)
    def test_vague(self, text, expected):
        assert resolve(text, MONDAY) == expected

    @cases(RELATIVE_TO_DATES)
    def test_before_and_after_a_date(self, text, expected):
        assert resolve(text, MONDAY) == expected

    @cases(UNPARSEABLE)
    def test_unrecognised_text_is_unparsed(self, text, expected):
        assert resolve(text, MONDAY) == expected


ON_SATURDAY = [
    ("today", exact(d(12, 26))),
    ("tonight", exact(d(12, 26), part_of_day="night")),
    ("tomorrow", exact(d(12, 27))),
    ("yesterday", exact(d(12, 25))),
    ("the day after tomorrow", exact(d(12, 28))),
    ("Saturday", exact(d(1, 2, 2027))),
    ("Friday", exact(d(1, 1, 2027))),
    ("Monday", exact(d(12, 28))),
    ("this Saturday", exact(d(12, 26))),
    ("this Sunday", exact(d(12, 27))),
    ("this Friday", exact(d(1, 1, 2027))),
    ("next Friday", exact(d(1, 1, 2027), ambiguous=True)),
    ("next Monday", exact(d(12, 28), ambiguous=True)),
    ("next Sunday", exact(d(1, 3, 2027), ambiguous=True)),
    ("Friday week", exact(d(1, 8, 2027))),
    ("last Friday", exact(d(12, 25))),
    ("last Saturday", exact(d(12, 19))),
    ("this week", span(d(12, 26), d(12, 27))),
    ("next week", span(d(12, 28), d(1, 3, 2027))),
    ("last week", span(d(12, 14), d(12, 20))),
    ("the week after next", span(d(1, 4, 2027), d(1, 10, 2027))),
    ("later this week", exact(d(12, 27))),
    ("end of the week", span(d(12, 25), d(12, 27))),
    ("this weekend", span(d(12, 26), d(12, 27))),
    ("the weekend", span(d(12, 26), d(12, 27))),
    ("next weekend", span(d(1, 2, 2027), d(1, 3, 2027), ambiguous=True)),
    ("Christmas", exact(d(12, 25, 2027))),
    ("Christmas Eve", exact(d(12, 24, 2027))),
    ("Boxing Day", exact(d(12, 26))),
    ("New Year's Eve", exact(d(12, 31))),
    ("New Year's Day", exact(d(1, 1, 2027))),
    ("after Christmas", span(d(12, 26), d(12, 31), relation="after")),
    ("Easter", exact(d(3, 28, 2027))),
    ("Halloween", exact(d(10, 31, 2027))),
    ("Valentine's Day", exact(d(2, 14, 2027))),
    ("the 3rd", exact(d(1, 3, 2027))),
    ("the 26th", exact(d(12, 26))),
    ("the 31st", exact(d(12, 31))),
    ("14 May", exact(d(5, 14, 2027))),
    ("25 December", exact(d(12, 25, 2027))),
    ("1/1", exact(d(1, 1, 2027))),
    ("this month", span(d(12, 1), d(12, 31))),
    ("next month", span(d(1, 1, 2027), d(1, 31, 2027))),
    ("end of the month", span(d(12, 21), d(12, 31))),
    ("end of next month", span(d(1, 21, 2027), d(1, 31, 2027))),
    ("beginning of next month", span(d(1, 1, 2027), d(1, 10, 2027))),
    ("December", span(d(12, 1), d(12, 31))),
    ("January", span(d(1, 1, 2027), d(1, 31, 2027))),
    ("winter", span(d(12, 1), d(2, 28, 2027))),
    ("this winter", span(d(12, 1), d(2, 28, 2027))),
    ("next winter", span(d(12, 1, 2027), d(2, 29, 2028))),
    ("summer", span(d(6, 1, 2027), d(8, 31, 2027))),
    ("in a week", exact(d(1, 2, 2027))),
    ("in 3 days", exact(d(12, 29))),
    ("in a month", exact(d(1, 26, 2027))),
    ("in a couple of weeks", span(d(1, 6, 2027), d(1, 12, 2027))),
    ("before Friday", span(d(12, 26), d(12, 31), relation="before")),
    ("by Monday", span(d(12, 26), d(12, 28), relation="before")),
    ("after new year", exact(d(1, 2, 2027), relation="after")),
    ("this year", span(d(1, 1), d(12, 31))),
    ("next year", span(d(1, 1, 2027), d(12, 31, 2027))),
]


class TestResolveOnSaturday:
    @cases(ON_SATURDAY)
    def test_rolls_over_the_year_and_weekend(self, text, expected):
        assert resolve(text, SATURDAY) == expected


FRIDAY_30_OCT = exact(d(10, 30))
WEEK_OF_26_OCT = span(d(10, 26), d(11, 1))
UNSURE_FRIDAY = exact(d(10, 30), ambiguous=True)

ANCHORED = [
    # exact anchor
    ("that morning", FRIDAY_30_OCT, exact(d(10, 30), part_of_day="morning", anaphoric=True)),
    ("that afternoon", FRIDAY_30_OCT, exact(d(10, 30), part_of_day="afternoon", anaphoric=True)),
    ("that evening", FRIDAY_30_OCT, exact(d(10, 30), part_of_day="evening", anaphoric=True)),
    ("that night", FRIDAY_30_OCT, exact(d(10, 30), part_of_day="night", anaphoric=True)),
    ("that day", FRIDAY_30_OCT, exact(d(10, 30), anaphoric=True)),
    ("on the day", FRIDAY_30_OCT, exact(d(10, 30), anaphoric=True)),
    ("the morning of", FRIDAY_30_OCT, exact(d(10, 30), part_of_day="morning", anaphoric=True)),
    ("the night before", FRIDAY_30_OCT, exact(d(10, 29), part_of_day="night", relation="before", anaphoric=True)),
    ("the day before", FRIDAY_30_OCT, exact(d(10, 29), relation="before", anaphoric=True)),
    ("the day after", FRIDAY_30_OCT, exact(d(10, 31), relation="after", anaphoric=True)),
    ("the next day", FRIDAY_30_OCT, exact(d(10, 31), relation="after", anaphoric=True)),
    ("the following day", FRIDAY_30_OCT, exact(d(10, 31), relation="after", anaphoric=True)),
    ("the next morning", FRIDAY_30_OCT, exact(d(10, 31), part_of_day="morning", relation="after", anaphoric=True)),
    ("the week before", FRIDAY_30_OCT, span(d(10, 23), d(10, 29), relation="before", anaphoric=True)),
    ("the week after", FRIDAY_30_OCT, span(d(10, 31), d(11, 6), relation="after", anaphoric=True)),
    ("a week before", FRIDAY_30_OCT, exact(d(10, 23), relation="before", anaphoric=True)),
    ("a week after", FRIDAY_30_OCT, exact(d(11, 6), relation="after", anaphoric=True)),
    ("3 days before", FRIDAY_30_OCT, exact(d(10, 27), relation="before", anaphoric=True)),
    ("two weeks after", FRIDAY_30_OCT, exact(d(11, 13), relation="after", anaphoric=True)),
    ("2 days after that", FRIDAY_30_OCT, exact(d(11, 1), relation="after", anaphoric=True)),
    ("a few days after", FRIDAY_30_OCT, span(d(11, 1), d(11, 3), relation="after", anaphoric=True)),
    ("afterwards", FRIDAY_30_OCT, exact(d(10, 31), relation="after", anaphoric=True)),
    ("after", FRIDAY_30_OCT, exact(d(10, 31), relation="after", anaphoric=True)),
    ("after it", FRIDAY_30_OCT, exact(d(10, 31), relation="after", anaphoric=True)),
    ("after that", FRIDAY_30_OCT, exact(d(10, 31), relation="after", anaphoric=True)),
    ("once it's done", FRIDAY_30_OCT, exact(d(10, 31), relation="after", anaphoric=True)),
    ("beforehand", FRIDAY_30_OCT, exact(d(10, 29), relation="before", anaphoric=True)),
    ("before", FRIDAY_30_OCT, exact(d(10, 29), relation="before", anaphoric=True)),
    ("before then", FRIDAY_30_OCT, exact(d(10, 29), relation="before", anaphoric=True)),
    ("at 3pm", FRIDAY_30_OCT, exact(d(10, 30), time="15:00", anaphoric=True)),
    ("in the morning", FRIDAY_30_OCT, exact(d(10, 30), part_of_day="morning", anaphoric=True)),
    ("that evening at 7", FRIDAY_30_OCT, exact(d(10, 30), time="19:00", part_of_day="evening", anaphoric=True)),
    ("the day before at 3", FRIDAY_30_OCT, exact(d(10, 29), time="15:00", relation="before", anaphoric=True, ambiguous=True)),
    ("before 3pm", FRIDAY_30_OCT, exact(d(10, 30), time="15:00", relation="before", anaphoric=True)),
    ("a month after", exact(d(1, 31, 2027)), exact(d(2, 28, 2027), relation="after", anaphoric=True)),
    # range anchor: before/after count from its first/last day, the same day keeps the whole range
    ("afterwards", WEEK_OF_26_OCT, exact(d(11, 2), relation="after", anaphoric=True)),
    ("beforehand", WEEK_OF_26_OCT, exact(d(10, 25), relation="before", anaphoric=True)),
    ("the day after", WEEK_OF_26_OCT, exact(d(11, 2), relation="after", anaphoric=True)),
    ("the week after", WEEK_OF_26_OCT, span(d(11, 2), d(11, 8), relation="after", anaphoric=True)),
    ("the week before", WEEK_OF_26_OCT, span(d(10, 19), d(10, 25), relation="before", anaphoric=True)),
    ("that day", WEEK_OF_26_OCT, span(d(10, 26), d(11, 1), anaphoric=True, ambiguous=True)),
    ("that morning", WEEK_OF_26_OCT, span(d(10, 26), d(11, 1), part_of_day="morning", anaphoric=True, ambiguous=True)),
    ("at 3pm", WEEK_OF_26_OCT, exact(d(10, 26), time="15:00", anaphoric=True, ambiguous=True)),
    # an uncertain anchor makes everything resolved against it uncertain
    ("the day before", UNSURE_FRIDAY, exact(d(10, 29), relation="before", anaphoric=True, ambiguous=True)),
    # an anchor without dates is no anchor
    ("the day before", Resolution("vague"), anaphoric(relation="before")),
    # expressions that are not anaphoric ignore the anchor
    ("Friday", FRIDAY_30_OCT, exact(d(10, 23))),
    ("the day before christmas", FRIDAY_30_OCT, exact(d(12, 24), relation="before")),
    ("tomorrow at 9am", WEEK_OF_26_OCT, exact(d(10, 20), time="09:00")),
]


class TestResolveWithAnchor:
    @pytest.mark.parametrize("text, anchor, expected", ANCHORED, ids=[f"{text} @ {anchor.kind}" for text, anchor, _ in ANCHORED])
    def test_resolves_against_the_anchor(self, text, anchor, expected):
        assert resolve(text, MONDAY, anchor) == expected


MONTH_FIRST = [
    ("5/6", exact(d(5, 6, 2027))),
    ("14/05", exact(d(5, 14, 2027))),
    ("05/14/2027", exact(d(5, 14, 2027))),
    ("10/30", exact(d(10, 30))),
]


class TestResolveMonthFirst:
    @cases(MONTH_FIRST)
    def test_reads_numeric_dates_month_first(self, text, expected):
        assert resolve(text, MONDAY, day_first=False) == expected


class TestResolveNeverRaises:
    @pytest.mark.parametrize(
        "text",
        [
            "in 999 years",
            "before " * 40 + "friday",
            "sometime " * 30,
            "31/31/31",
            "0/0",
            "the 0th",
            "the 99th",
            "at 99",
            "25:99",
            "december 2199 and after",
            "after december 2199",
            "next winter 2199",
            "😀 tomorrow 😀",
            "x" * 1000,
        ],
    )
    def test_returns_a_resolution(self, text):
        assert isinstance(resolve(text, MONDAY), Resolution)


class TestEasterSunday:
    @pytest.mark.parametrize(
        "year, expected", [(2024, d(3, 31, 2024)), (2025, d(4, 20, 2025)), (2026, d(4, 5)), (2027, d(3, 28, 2027)), (2038, d(4, 25, 2038))]
    )
    def test_matches_known_dates(self, year, expected):
        assert easter_sunday(year) == expected
