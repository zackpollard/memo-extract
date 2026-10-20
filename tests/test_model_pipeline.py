"""Encoding, augmentation, BIO decoding and scoring, without training a real model."""

import random

import pytest
import torch

from memo_extract.augment import apply_edits, dictate, swap_names
from memo_extract.decode import tags_to_spans, viterbi
from memo_extract.encoding import IGNORE, LAYER_TAGS, TAG_INDEX, encode
from memo_extract.evaluate import score
from memo_extract.records import parse


def memo_of(text, *spans):
    memo, errors = parse({"id": "m", "text": text, "spans": list(spans)})
    assert errors == []
    return memo


SAM = {"id": "p1", "type": "PERSON", "text": "Sam", "pronoun": "he"}
MEMO = memo_of(
    "Sam's driving test is Friday. Remind me to ask him how it went.",
    SAM,
    {"id": "e1", "type": "EVENT", "text": "driving test", "owner": "p1", "event_type": "exam", "followup": "ask_outcome"},
    {"id": "d1", "type": "DATE", "text": "Friday", "anchor": "e1"},
    {
        "id": "a1",
        "type": "ACTION",
        "text": "ask him how it went",
        "owner": "p1",
        "anchor": "e1",
        "action_type": "ask_outcome",
        "timing": "after",
    },
)


class FakeTokenizer:
    """Whitespace-and-punctuation tokenizer with offsets, wrapped in [CLS]/[SEP]."""

    def __call__(self, text, return_offsets_mapping, truncation, max_length):
        import re

        offsets = [(m.start(), m.end()) for m in re.finditer(r"\w+|[^\w\s]", text)][: max_length - 2]
        offsets = [(0, 0), *offsets, (0, 0)]
        return {"input_ids": list(range(len(offsets))), "offset_mapping": offsets}


class TestEncode:
    def test_tags_each_layer_separately(self):
        enc = encode(MEMO, FakeTokenizer(), 64)
        entity = [LAYER_TAGS["entity"][t] if t != IGNORE else None for t in enc.tags["entity"]]
        action = [LAYER_TAGS["action"][t] if t != IGNORE else None for t in enc.tags["action"]]

        assert entity[:5] == [None, "B-PERSON", "O", "O", "B-EVENT"]
        assert action.count("B-ACTION") == 1
        assert action.count("I-ACTION") == 4

    def test_pointer_targets_index_into_null_plus_spans(self):
        enc = encode(MEMO, FakeTokenizer(), 64)

        assert enc.pointers["owner"] == [0, 1, IGNORE, 1]
        assert enc.pointers["anchor"] == [IGNORE, IGNORE, 2, 2]

    def test_truncated_spans_are_dropped_with_their_pointers(self):
        enc = encode(MEMO, FakeTokenizer(), 6)

        assert len(enc.span_bounds) == 1  # "driving test" is cut to "driving", so it is not taught at all
        assert enc.pointers["owner"] == [0]
        assert enc.tags["entity"][4] == IGNORE


class TestAugment:
    def test_swap_names_is_consistent_and_aligned(self):
        memo = memo_of("Sam met sam", SAM, {**SAM, "id": "p2", "text": "sam"})

        swapped = swap_names(memo, random.Random(0), ["Kofi"])

        assert swapped.text == "Kofi met kofi"
        assert [swapped.text[s.start : s.end] for s in swapped.spans] == ["Kofi", "kofi"]

    def test_dictate_drops_punctuation_but_keeps_times(self):
        memo = memo_of("Sam, at 3:30. Bye!", SAM, {"id": "d1", "type": "DATE", "text": "3:30"})

        out = dictate(memo)

        assert out.text == "sam at 3:30 bye"
        assert [s.text for s in out.spans] == ["sam", "3:30"]

    def test_edit_inside_a_span_keeps_it(self):
        memo = memo_of("Dr. Okafor", {"id": "p1", "type": "PERSON", "text": "Dr. Okafor", "pronoun": "unknown"})

        assert apply_edits(memo, [(2, 3, "")]).spans[0].text == "Dr Okafor"


class TestDecode:
    def test_viterbi_never_starts_with_inside(self):
        tags = LAYER_TAGS["entity"]
        log_probs = torch.full((2, len(tags)), -10.0)
        log_probs[0, TAG_INDEX["entity"]["I-PERSON"]] = 0.0
        log_probs[1, TAG_INDEX["entity"]["I-PERSON"]] = 0.0

        path = viterbi(log_probs, "entity")

        assert tags[path[0]] != "I-PERSON"

    def test_tags_to_spans_groups_bio_runs(self):
        tags = LAYER_TAGS["entity"]
        idx = TAG_INDEX["entity"]
        path = [idx["B-PERSON"], idx["O"], idx["B-DATE"], idx["I-DATE"], idx["B-DATE"]]

        assert tags_to_spans(path, tags) == [("PERSON", 0, 0), ("DATE", 2, 3), ("DATE", 4, 4)]


class TestScore:
    def test_perfect_prediction(self):
        metrics = score([MEMO], [MEMO])

        assert metrics["strict"]["f1"] == 1.0
        assert metrics["memo_exact"] == 1.0

    def test_wrong_pointer_counts_against_strict_but_not_spans(self):
        wrong = memo_of(
            "Sam's driving test is Friday. Remind me to ask him how it went.",
            SAM,
            {"id": "e1", "type": "EVENT", "text": "driving test", "event_type": "exam", "followup": "ask_outcome"},
            {"id": "d1", "type": "DATE", "text": "Friday", "anchor": "e1"},
            {
                "id": "a1",
                "type": "ACTION",
                "text": "ask him how it went",
                "owner": "p1",
                "anchor": "e1",
                "action_type": "ask_outcome",
                "timing": "after",
            },
        )

        metrics = score([MEMO], [wrong])

        assert metrics["spans"]["f1"] == 1.0
        assert metrics["strict"]["f1"] == pytest.approx(0.75)
        assert metrics["checks"]["owner:EVENT"] == 0.0
        assert metrics["memo_exact"] == 0.0


class TestDistill:
    def test_kl_is_zero_for_identical_logits_and_positive_otherwise(self):
        from memo_extract.model import kl

        logits = torch.tensor([[2.0, 0.5, -1.0]])

        assert kl(logits, logits, 2.0).item() == pytest.approx(0.0, abs=1e-6)
        assert kl(logits, logits.flip(-1), 2.0).item() > 0

    def test_kl_of_nothing_is_zero(self):
        from memo_extract.model import kl

        assert kl(torch.zeros(0, 3), torch.zeros(0, 3), 2.0).item() == 0.0

    def test_student_pieces_map_into_the_teacher_vocabulary(self):
        from memo_extract.training import student_to_teacher_ids

        class Vocab:
            def __init__(self, pieces):
                self.pieces = pieces

            def __len__(self):
                return len(self.pieces)

            def convert_ids_to_tokens(self, ids):
                return [self.pieces[i] for i in ids]

            def get_vocab(self):
                return {p: i for i, p in enumerate(self.pieces)}

        teacher = Vocab(["[PAD]", "[CLS]", "the", "pot", "##tery", "zebra"])

        assert student_to_teacher_ids(Vocab(["[PAD]", "[CLS]", "pot", "##tery"]), teacher).tolist() == [0, 1, 3, 4]
        with pytest.raises(ValueError, match="not a subset"):
            student_to_teacher_ids(Vocab(["[PAD]", "unseen"]), teacher)


class TestPruneVocab:
    def test_keeps_specials_characters_top_tokens_and_used_tokens(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
        from prune_vocab import keep_ids

        vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "a", "##b", "the", "of", "pottery", "zebra"]
        tokenizer = lambda text, add_special_tokens: {"input_ids": [vocab.index(w) for w in text.split()]}

        kept = keep_ids(vocab, tokenizer, ["pottery"], keep_top=1)

        assert [vocab[i] for i in kept] == ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "a", "##b", "the", "pottery"]


class TestBuildMemo:
    def run(self, text, decoded, owner_targets):
        from memo_extract.decode import build_memo
        from memo_extract.encoding import HEADS

        offsets = [(m.start(), m.end()) for m in __import__("re").finditer(r"\w+|[^\w\s]", text)]
        n = len(decoded)
        attrs = {head: torch.zeros(n, len(values)) for head, (_, _, values) in HEADS.items()}
        owner = torch.full((n, n + 1), -10.0)
        for k, target in enumerate(owner_targets):
            owner[k, target] = 10.0
        anchor = torch.zeros(n, n + 1)
        anchor[:, 0] = 10.0
        return build_memo(text, offsets, decoded, attrs, {"owner": owner, "anchor": anchor})

    def test_owner_cycles_are_broken(self):
        memo = self.run("mum sister", [("RELATION", 0, 0), ("RELATION", 1, 1)], [2, 1])

        assert sum(s.owner is not None for s in memo.spans) == 1

    def test_nickname_prefix_joins_the_earlier_person(self):
        memo = self.run("Siddharth golf Sid", [("PERSON", 0, 0), ("INTEREST", 1, 1), ("PERSON", 2, 2)], [0, 3, 0])

        assert memo.spans[1].owner == memo.spans[0].id


class TestCodexRegressions:
    def test_span_glued_to_unsplittable_text_is_not_taught(self):
        from memo_extract.encoding import encode as enc

        class Glued(FakeTokenizer):
            def __call__(self, text, **kwargs):
                return {"input_ids": [0, 1, 2], "offset_mapping": [(0, 0), (0, len(text)), (0, 0)]}

        memo = memo_of("jazz!", {"id": "i1", "type": "INTEREST", "text": "jazz"})
        out = enc(memo, Glued(), 16)

        assert out.span_bounds == []
        assert out.tags["entity"] == [IGNORE, IGNORE, IGNORE]

    def test_dictate_survives_lowercasing_that_changes_length(self):
        memo = memo_of(
            "İpek likes pottery",
            {"id": "p1", "type": "PERSON", "text": "İpek", "pronoun": "she"},
            {"id": "i1", "type": "INTEREST", "text": "pottery", "owner": "p1"},
        )

        out = dictate(memo)

        assert [s.text for s in out.spans] == ["i̇pek", "pottery"]
        assert all(out.text[s.start : s.end] == s.text for s in out.spans)

    def test_swap_names_never_merges_two_people(self):
        memo = memo_of("Sam likes golf. Ana likes jazz", SAM, {"id": "p2", "type": "PERSON", "text": "Ana", "pronoun": "she"})

        for seed in range(50):
            out = swap_names(memo, random.Random(seed), ["Magda", "Kofi"])
            assert out.spans[0].text != out.spans[1].text

    def test_mentions_of_one_person_get_one_pronoun_and_owner(self):
        from memo_extract.decode import harmonise_mentions
        from memo_extract.records import Span

        spans = [
            Span("s0", "PERSON", "Ana", 0, 3, {"pronoun": "unknown"}),
            Span("s1", "PERSON", "Sam", 4, 7, {"pronoun": "he"}, owner="s0"),
            Span("s2", "PERSON", "Sam", 8, 11, {"pronoun": "unknown"}),
        ]

        harmonise_mentions(spans)

        assert [(s.attrs["pronoun"], s.owner) for s in spans[1:]] == [("he", "s0"), ("he", "s0")]

    @pytest.mark.parametrize(
        "text, start, end, expected", [("find Peck", 0, 6, "find Peck"), ("re-viewing", 5, 10, "viewing"), ("Sam's", 0, 3, "Sam")]
    )
    def test_spans_snap_to_whole_words(self, text, start, end, expected):
        from memo_extract.decode import snap_to_words

        s, e = snap_to_words(text, start, end)

        assert text[s:e] == expected
