"""Training-time rewrites that keep labels aligned: swap person names, and turn typed text into dictation-style text."""

import re
from dataclasses import replace

from .constants import TITLES
from .records import Memo, first_mention, first_name

DICTATION_PUNCTUATION = re.compile(r"[.,!?;:](?!\d)|(?<!\d)[.:]")


def apply_edits(memo, edits):
    """Memo with non-overlapping (start, end, replacement) char edits applied and span offsets moved with them."""
    pieces, mapping, cursor, shift = [], {}, 0, 0
    for start, end, new in sorted(edits):
        pieces += [memo.text[cursor:start], new]
        for p in range(cursor, start + 1):
            mapping[p] = p + shift
        shift += len(new) - (end - start)
        mapping[end] = end + shift
        cursor = end
    pieces.append(memo.text[cursor:])
    for p in range(cursor, len(memo.text) + 1):
        mapping.setdefault(p, p + shift)

    text = "".join(pieces)
    spans = []
    for span in memo.spans:
        start, end = mapping.get(span.start), mapping.get(span.end)
        if start is None or end is None or not text[start:end].strip():
            return memo
        while text[start].isspace():
            start += 1
        while text[end - 1].isspace():
            end -= 1
        spans.append(replace(span, text=text[start:end], start=start, end=end))
    return Memo(memo.id, text, spans)


def match_case(template, word):
    if template.islower():
        return word.lower()
    if template.isupper() and len(template) > 1:
        return word.upper()
    return word


def swap_names(memo, rng, names):
    """Replace each person's given name with a random one: the same new name on every mention of a person,
    and never one already used by someone else in the memo, so people neither merge nor split."""
    taken = {first_name(s) for s in memo.spans if s.type == "PERSON"}
    pool = [n for n in names if n.casefold() not in taken]
    chosen, edits = {}, []
    for span in memo.spans:
        if span.type != "PERSON":
            continue

        words = [(m.start(), m.end()) for m in re.finditer(r"[^\s.]+", span.text)]
        given = next(((s, e) for s, e in words if span.text[s:e].lower() not in TITLES), None)
        key = first_name(first_mention(memo.spans, span))
        if given is None or (key not in chosen and not pool):
            continue

        if key not in chosen:
            chosen[key] = pool.pop(rng.randrange(len(pool)))
        s, e = given
        edits.append((span.start + s, span.start + e, match_case(span.text[s:e], chosen[key])))
    return apply_edits(memo, edits)


def dictate(memo):
    """Lowercase and drop sentence punctuation, as a speech-to-text transcript would."""
    # per-character edits, because lowercasing can change length ("İ" -> "i̇")
    lowered = apply_edits(memo, [(i, i + 1, ch.lower()) for i, ch in enumerate(memo.text) if ch.lower() != ch])
    edits = [(m.start(), m.end(), "") for m in DICTATION_PUNCTUATION.finditer(lowered.text)]
    return apply_edits(lowered, edits)


def augment(memo, rng, names, swap_rate, dictate_rate):
    if rng.random() < swap_rate:
        memo = swap_names(memo, rng, names)
    if rng.random() < dictate_rate:
        memo = dictate(memo)
    return memo
