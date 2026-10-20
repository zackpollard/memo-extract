"""The suggestion layer reproduces the product examples from correct labels."""

from datetime import date
from pathlib import Path

import pytest

from memo_extract.data import load_memos
from memo_extract.records import Memo, Span
from memo_extract.suggest import suggest
from memo_extract.templates import rewrite_action, title_for

TODAY = date(2026, 10, 19)  # a Monday
CONTACTS = ["Maya Okafor", "Daniel Reyes", "Alex Chen", "Alex Romero", "Priya Shah"]
EXAMPLES = {m.id: m for m in load_memos([Path(__file__).parent.parent / "data/eval/user_examples.jsonl"])[0]}


def reminders(memo_id):
    return suggest(EXAMPLES[memo_id], TODAY, CONTACTS)["reminders"]


def test_birthday_message_that_morning_confirms_time():
    out = suggest(EXAMPLES["user-1"], TODAY, CONTACTS)

    assert {"person": "Maya", "kind": "interest", "text": "pottery"} in out["details"]
    assert any(d["kind"] == "birthday" and d["date"] == "--05-14" for d in out["details"])
    assert out["reminders"] == [
        {
            "kind": "message",
            "title": "Message Maya on her birthday",
            "person": "Maya",
            "date": "2027-05-14",
            "time": "09:00",
            "source": "explicit",
            "confirm": ["time"],
            "context": [],
        }
    ]


def test_ask_about_first_day_the_next_day():
    out = suggest(EXAMPLES["user-2"], TODAY, CONTACTS)

    assert any(d["kind"] == "event" and d["date"] == "2026-11-02" for d in out["details"])
    assert out["reminders"] == [
        {
            "kind": "ask_outcome",
            "title": "Ask Daniel how his first day went",
            "person": "Daniel",
            "date": "2026-11-03",
            "time": "09:00",
            "source": "explicit",
            "confirm": [],
            "context": [],
        }
    ]


def test_vague_interview_asks_which_alex_and_when():
    (only,) = reminders("user-3")

    assert only["title"] == "Check in with Alex about their interview"
    assert only["confirm"] == ["person", "date"]


def test_driving_test_suggests_asking_after():
    assert reminders("user-4") == [
        {
            "kind": "ask_outcome",
            "title": "Ask Maya how her driving test went",
            "person": "Maya",
            "date": "2026-11-13",
            "time": "09:00",
            "source": "suggested",
            "confirm": [],
            "context": [],
        }
    ]


def test_birthday_suggests_gift_a_week_before_with_interests():
    assert reminders("user-5") == [
        {
            "kind": "gift",
            "title": "Get Daniel a birthday gift",
            "person": "Daniel",
            "date": "2027-05-07",
            "time": "09:00",
            "source": "suggested",
            "confirm": [],
            "context": ["pottery"],
        }
    ]


def test_relative_surgery_next_week_checks_in_with_the_person():
    (only,) = reminders("user-6")

    assert only["title"] == "Check in with Priya about her mum"
    assert only["person"] == "Priya"
    assert only["confirm"] == ["date"]


def test_explicit_reminder_does_not_also_suggest_for_the_same_event():
    titles = [r["title"] for r in reminders("user-1")]

    assert "Get Maya a birthday gift" not in titles


def test_memo_without_people_keeps_the_users_own_words():
    memo = Memo(
        "m", "Need to book the car in", [Span("a1", "ACTION", "book the car in", 8, 23, {"action_type": "other", "timing": "unspecified"})]
    )

    (only,) = suggest(memo, TODAY)["reminders"]

    assert only["title"] == "Book the car in"
    assert only["person"] is None
    assert only["confirm"] == ["date"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("send him the recipe", "Send Kofi the recipe"),
        ("get her a card", "Get Kofi a card"),
        ("return her drill", "Return her drill"),
        ("ask Nasser to cover his clients", "Ask Nasser to cover his clients"),
        ("text him and tell him", "Text Kofi and tell him"),
        ("tell them about it", "Tell Kofi about it"),
    ],
)
def test_rewrite_action_swaps_pronouns_for_the_name(text, expected):
    assert rewrite_action(text, "Kofi") == expected


@pytest.mark.parametrize(
    "kind, event, event_type, expected",
    [
        ("congratulate", "retiring", "job", "Congratulate Sam on retiring"),
        ("ask_outcome", "moving to Leeds", "move", "Ask Sam how moving to Leeds went"),
        ("congratulate", "due", "baby", "Congratulate Sam on the baby"),
        ("congratulate", "promotion", "job", "Congratulate Sam on his promotion"),
        ("ask_outcome", "new job", "job", "Ask Sam how his first day went"),
    ],
)
def test_title_for_reads_naturally(kind, event, event_type, expected):
    assert title_for(kind, "Sam", "he", event, event_type) == expected


@pytest.mark.parametrize("event", ["driving test", "leaving drinks", "wedding", "housewarming"])
def test_title_for_keeps_the_possessive_on_noun_events(event):
    assert title_for("ask_outcome", "Sam", "he", event, "other") == f"Ask Sam how his {event} went"


def span(span_id, span_type, text, memo_text, **fields):
    start = memo_text.index(text)
    attrs = {k: fields.pop(k) for k in list(fields) if k not in ("owner", "anchor")}
    return Span(span_id, span_type, text, start, start + len(text), attrs, fields.get("owner"), fields.get("anchor"))


def test_relation_owner_cycle_does_not_crash():
    text = "mum and sister"
    memo = Memo("m", text, [span("r1", "RELATION", "mum", text, owner="r2"), span("r2", "RELATION", "sister", text, owner="r1")])

    assert len(suggest(memo, TODAY)["people"]) == 2


@pytest.mark.parametrize("kind", ["ask_outcome", "wish_luck", "congratulate", "check_in", "gift", "message", "call", "meet"])
@pytest.mark.parametrize("relation", [None, "sister"])
@pytest.mark.parametrize("event, event_type", [(None, None), ("wedding", "wedding"), ("birthday", "birthday"), ("new job", "job")])
def test_every_template_combination_renders(kind, relation, event, event_type):
    title = title_for(kind, "Sam", "he", event, event_type, relation)

    assert title is None or ("{" not in title and "None" not in title)


def test_action_without_owner_keeps_the_users_words():
    assert rewrite_action("send him the recipe", None) == "Send him the recipe"


def test_calling_a_relative_addresses_the_relative():
    text = "Priya's mum's birthday is Friday; I should call her mum"
    first_mum = text.index("mum")
    spans = [
        span("p1", "PERSON", "Priya", text, pronoun="she"),
        Span("r1", "RELATION", "mum", first_mum, first_mum + 3, {}, "p1"),
        span("e1", "EVENT", "birthday", text, event_type="birthday", followup="gift", owner="r1"),
        span("d1", "DATE", "Friday", text, anchor="e1"),
        span("a1", "ACTION", "call her mum", text, action_type="call", timing="on", owner="r1", anchor="e1"),
    ]

    (only,) = suggest(Memo("m", text, spans), TODAY)["reminders"]

    assert only["title"] == "Call Priya's mum on their birthday"
    assert only["date"] == "2026-10-23"


def test_clock_time_lands_on_the_named_day_and_keeps_its_ambiguity():
    text = "Sam's appointment is at 3, that's on Friday"
    spans = [
        span("p1", "PERSON", "Sam", text, pronoun="he"),
        span("e1", "EVENT", "appointment", text, event_type="medical", followup="check_in", owner="p1"),
        span("d1", "DATE", "at 3", text, anchor="e1"),
        span("d2", "DATE", "Friday", text, anchor="e1"),
    ]

    event = next(d for d in suggest(Memo("m", text, spans), TODAY)["details"] if d["kind"] == "event")
    from memo_extract.suggest import Context

    when = Context(Memo("m", text, spans), TODAY).event_when(spans[1])

    assert event["date"] == "2026-10-23"
    assert when.time == "15:00" and when.ambiguous


@pytest.mark.parametrize("event", ["had tonsils out", "moved back", "got made redundant", "split"])
def test_finite_verb_events_fall_back_to_the_plain_title(event):
    assert title_for("check_in", "Omar", "he", event, "medical") == "Check in with Omar"
