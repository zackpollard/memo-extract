import pytest

from memo_extract.records import parse, word_occurrences


def record(text, *spans):
    return {"id": "m", "text": text, "spans": list(spans)}


PERSON = {"id": "p1", "type": "PERSON", "text": "Sam", "pronoun": "he"}


def errors_of(rec):
    return parse(rec)[1]


class TestWordOccurrences:
    def test_skips_matches_inside_words(self):
        assert word_occurrences("her here, her", "her") == [0, 10]

    def test_allows_punctuation_edges(self):
        assert word_occurrences("Sam's (Sam)", "Sam") == [0, 7]


class TestParse:
    def test_valid_record_resolves_offsets(self):
        memo, errors = parse(record("I saw Sam and Sam", PERSON, {**PERSON, "id": "p2"}))

        assert errors == []
        assert [(s.start, s.end) for s in memo.spans] == [(6, 9), (14, 17)]

    def test_explicit_occurrence_skips_an_unlabelled_mention(self):
        memo, _ = parse(record("Sam and Sam", {**PERSON, "occ": 2}))

        assert memo.spans[0].start == 8

    @pytest.mark.parametrize(
        "spans, message",
        [
            ([{**PERSON, "text": "Samuel"}], "not found on word boundaries"),
            ([{**PERSON, "pronoun": "it"}], "pronoun must be one of"),
            ([{**PERSON, "type": "PLACE"}], "unknown type"),
            ([{**PERSON, "colour": "red"}], "unknown keys"),
            ([{"id": "d1", "type": "DATE", "text": "Friday", "owner": "p1"}], "DATE spans have no owner"),
            (
                [{"id": "e1", "type": "EVENT", "text": "party", "event_type": "party", "followup": "none", "owner": "zz"}],
                "is not a span id",
            ),
            ([PERSON, {**PERSON, "id": "p1"}], "duplicate span id"),
        ],
    )
    def test_reports_shape_errors(self, spans, message):
        text = "Sam has a party Friday Sam"

        assert any(message in e for e in errors_of(record(text, *spans)))

    def test_spans_must_be_in_order(self):
        errors = errors_of(record("Sam on Friday", {"id": "d1", "type": "DATE", "text": "Friday"}, PERSON))

        assert any("after the previous span" in e for e in errors)

    def test_explicit_occurrence_out_of_order_is_reported(self):
        errors = errors_of(record("Sam on Friday", {"id": "d1", "type": "DATE", "text": "Friday"}, {**PERSON, "occ": 1}))

        assert any("order of appearance" in e for e in errors)

    def test_same_layer_spans_may_not_overlap(self):
        spans = [
            {"id": "e1", "type": "EVENT", "text": "big party", "event_type": "party", "followup": "none"},
            {"id": "i1", "type": "INTEREST", "text": "party", "occ": 1},
        ]

        assert any("overlap" in e for e in errors_of(record("a big party", *spans)))

    def test_placement_skips_text_inside_an_earlier_span(self):
        spans = [
            {"id": "p1", "type": "PERSON", "text": "Rahul Gupta", "pronoun": "he"},
            {"id": "p2", "type": "PERSON", "text": "Rahul", "pronoun": "he"},
        ]

        memo, errors = parse(record("Rahul Gupta said Rahul is fine", *spans))

        assert errors == []
        assert memo.spans[1].start == 17

    def test_later_first_name_mention_is_the_same_person(self):
        spans = [
            {"id": "p1", "type": "PERSON", "text": "Dr Rahul Gupta", "pronoun": "he"},
            {"id": "p2", "type": "PERSON", "text": "Rahul", "pronoun": "he"},
            {"id": "i1", "type": "INTEREST", "text": "golf", "owner": "p2"},
        ]

        assert any("first mention p1" in e for e in errors_of(record("Dr Rahul Gupta and Rahul love golf", *spans)))

    def test_nickname_links_with_same_as(self):
        spans = [
            {"id": "p1", "type": "PERSON", "text": "Siddharth", "pronoun": "he"},
            {"id": "p2", "type": "PERSON", "text": "Sid", "pronoun": "he", "same_as": "p1"},
            {"id": "i1", "type": "INTEREST", "text": "golf", "owner": "p2"},
        ]

        assert any("first mention p1" in e for e in errors_of(record("Siddharth aka Sid loves golf", *spans)))

    def test_same_as_must_point_backwards_at_an_entity(self):
        spans = [
            {"id": "p1", "type": "PERSON", "text": "Sid", "pronoun": "he", "same_as": "p2"},
            {"id": "p2", "type": "PERSON", "text": "Siddharth", "pronoun": "he"},
        ]

        assert any("same_as must be" in e for e in errors_of(record("Sid is Siddharth", *spans)))

    def test_person_mentions_share_an_owner(self):
        spans = [
            {"id": "p1", "type": "PERSON", "text": "Ana", "pronoun": "she"},
            {"id": "p2", "type": "PERSON", "text": "Sam", "pronoun": "he", "owner": "p1"},
            {"id": "p3", "type": "PERSON", "text": "Sam", "pronoun": "he"},
        ]

        assert any("owner differs" in e for e in errors_of(record("Ana's son Sam, Sam", *spans)))

    def test_same_relation_noun_with_different_owners_is_two_relations(self):
        spans = [
            {"id": "p1", "type": "PERSON", "text": "Ana", "pronoun": "she"},
            {"id": "r1", "type": "RELATION", "text": "mum", "owner": "p1"},
            {"id": "p2", "type": "PERSON", "text": "Bob", "pronoun": "he"},
            {"id": "r2", "type": "RELATION", "text": "mum", "owner": "p2"},
            {"id": "e1", "type": "EVENT", "text": "surgery", "owner": "r2", "event_type": "medical", "followup": "check_in"},
        ]

        assert errors_of(record("Ana's mum and Bob's mum, surgery", *spans)) == []

    def test_owner_cycles_are_rejected(self):
        spans = [
            {"id": "r1", "type": "RELATION", "text": "mum", "owner": "r2"},
            {"id": "r2", "type": "RELATION", "text": "sister", "owner": "r1"},
        ]

        assert any("cycle" in e for e in errors_of(record("mum and sister", *spans)))

    def test_action_may_contain_a_person(self):
        spans = [
            {
                "id": "a1",
                "type": "ACTION",
                "text": "ask Sam how it went",
                "action_type": "ask_outcome",
                "timing": "unspecified",
                "owner": "p1",
            },
            PERSON,
        ]

        assert errors_of(record("ask Sam how it went", *spans)) == []

    def test_span_may_not_cross_an_action_edge(self):
        spans = [
            {"id": "a1", "type": "ACTION", "text": "call Sam", "action_type": "call", "timing": "unspecified"},
            {"id": "p1", "type": "PERSON", "text": "Sam Lee", "pronoun": "he"},
        ]

        assert any("crosses the edge" in e for e in errors_of(record("call Sam Lee", *spans)))

    def test_pointer_must_target_first_mention(self):
        spans = [PERSON, {**PERSON, "id": "p2"}, {"id": "i1", "type": "INTEREST", "text": "golf", "owner": "p2"}]

        assert any("first mention p1" in e for e in errors_of(record("Sam and Sam like golf", *spans)))

    def test_pointer_target_type_is_checked(self):
        spans = [{"id": "d1", "type": "DATE", "text": "Friday"}, {"id": "i1", "type": "INTEREST", "text": "golf", "owner": "d1"}]

        assert any("must point at" in e for e in errors_of(record("Friday golf", *spans)))

    def test_mentions_share_a_pronoun(self):
        errors = errors_of(record("Sam and Sam", PERSON, {**PERSON, "id": "p2", "pronoun": "she"}))

        assert any("pronoun differs" in e for e in errors)
