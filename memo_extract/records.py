"""Parse labelled memo records into char-offset spans, collecting every spec violation."""

from dataclasses import dataclass, field
from itertools import pairwise

from .constants import ATTRIBUTES, ENTITY_TYPES, LAYER_OF, MAX_MEMO_CHARS, POINTERS, SPAN_TYPES, TITLES

SPAN_KEYS = {"id", "type", "text", "occ", "start", "same_as", *POINTERS, *(a for attrs in ATTRIBUTES.values() for a in attrs)}


@dataclass
class Span:
    id: str
    type: str
    text: str
    start: int
    end: int
    attrs: dict = field(default_factory=dict)
    owner: str | None = None
    anchor: str | None = None
    same_as: str | None = None  # labelled nickname link ("Sid" -> "Siddharth"); the model never predicts it


@dataclass
class Memo:
    id: str
    text: str
    spans: list[Span]


def word_occurrences(text, needle):
    """Start offsets of `needle` in `text` that begin and end on word boundaries."""
    starts = []
    i = text.find(needle)
    while i != -1:
        end = i + len(needle)
        clean_start = not (needle[0].isalnum() and i > 0 and text[i - 1].isalnum())
        clean_end = not (needle[-1].isalnum() and end < len(text) and text[end].isalnum())
        if clean_start and clean_end:
            starts.append(i)
        i = text.find(needle, i + 1)

    return starts


def parse(record):
    """Return (Memo | None, errors) for one record dict."""
    errors = []
    memo_id, text, raw_spans = record.get("id"), record.get("text"), record.get("spans")
    if not isinstance(memo_id, str) or not memo_id:
        errors.append("missing id")
    if not isinstance(text, str) or not text.strip():
        return None, errors + ["missing text"]
    if len(text) > MAX_MEMO_CHARS:
        errors.append(f"text longer than {MAX_MEMO_CHARS} chars")
    if not isinstance(raw_spans, list):
        return None, errors + ["spans must be a list"]

    spans, seen_ids = [], set()
    for n, raw in enumerate(raw_spans):
        where = f"span {n} ({raw.get('id', '?') if isinstance(raw, dict) else '?'})"
        if not isinstance(raw, dict):
            errors.append(f"{where}: not an object")
            continue

        span_errors = check_span_shape(raw, seen_ids)
        errors += [f"{where}: {e}" for e in span_errors]
        if span_errors:
            continue

        seen_ids.add(raw["id"])
        start = place(text, raw, spans)
        if start is None:
            errors.append(
                f"{where}: text {raw['text']!r} not found on word boundaries after the previous span"
                + (f" (occ {raw['occ']})" if "occ" in raw else "")
            )
            continue

        attrs = {a: raw[a] for a in ATTRIBUTES.get(raw["type"], {})}
        spans.append(
            Span(
                raw["id"],
                raw["type"],
                raw["text"],
                start,
                start + len(raw["text"]),
                attrs,
                raw.get("owner"),
                raw.get("anchor"),
                raw.get("same_as"),
            )
        )

    errors += check_layout(spans)
    errors += check_pointers(spans)
    if not errors:
        errors += [f"{s.id}: owner pointers form a cycle" for s in spans if owner_cycle(spans, s)][:1]
    if not errors:
        errors += check_mentions(spans)
    if errors:
        return None, errors

    return Memo(memo_id, text, spans), []


def place(text, raw, placed):
    """Start offset for a span: its `occ`-th occurrence if given, otherwise the first occurrence at or after the
    previous span's start that does not overlap a span already placed in the same layer."""
    occurrences = word_occurrences(text, raw["text"])
    if "start" in raw:  # machine-labelled records carry exact offsets
        return raw["start"] if raw["start"] in occurrences else None
    if "occ" in raw:
        return occurrences[raw["occ"] - 1] if raw["occ"] <= len(occurrences) else None

    floor = placed[-1].start if placed else 0
    end_of = lambda start: start + len(raw["text"])
    same_layer = [s for s in placed if LAYER_OF[s.type] == LAYER_OF[raw["type"]]]
    for start in occurrences:
        if start >= floor and not any(s.start < end_of(start) and start < s.end for s in same_layer):
            return start
    return None


def check_span_shape(raw, seen_ids):
    errors = []
    span_id, span_type, span_text = raw.get("id"), raw.get("type"), raw.get("text")
    if not isinstance(span_id, str) or not span_id:
        errors.append("missing id")
    elif span_id in seen_ids:
        errors.append(f"duplicate span id {span_id!r}")
    if span_type not in SPAN_TYPES:
        return errors + [f"unknown type {span_type!r}"]
    if not isinstance(span_text, str) or not span_text or span_text != span_text.strip():
        errors.append("text must be a non-empty string without surrounding whitespace")
    if "occ" in raw and (not isinstance(raw["occ"], int) or raw["occ"] < 1):
        errors.append("occ must be a positive integer")
    if "start" in raw and (not isinstance(raw["start"], int) or raw["start"] < 0):
        errors.append("start must be a character offset")

    unknown = set(raw) - SPAN_KEYS
    if unknown:
        errors.append(f"unknown keys {sorted(unknown)}")

    allowed_attrs = ATTRIBUTES.get(span_type, {})
    for attr, values in allowed_attrs.items():
        if raw.get(attr) not in values:
            errors.append(f"{attr} must be one of {list(values)}, got {raw.get(attr)!r}")
    for attr in {a for attrs in ATTRIBUTES.values() for a in attrs} - set(allowed_attrs):
        if attr in raw:
            errors.append(f"{span_type} spans have no {attr}")

    if "same_as" in raw and (span_type not in ENTITY_TYPES or raw["same_as"] not in seen_ids):
        errors.append("same_as must be the id of an earlier PERSON or RELATION mention")

    for pointer, targets in POINTERS.items():
        if pointer in raw and span_type not in targets:
            errors.append(f"{span_type} spans have no {pointer}")
        elif pointer in raw and not isinstance(raw[pointer], str):
            errors.append(f"{pointer} must be a span id (leave it out for none)")

    return errors


def check_layout(spans):
    errors = []
    for prev, cur in pairwise(spans):
        if cur.start < prev.start:
            errors.append(f"spans must be listed in order of appearance: {cur.id} comes before {prev.id} in the text")

    for i, a in enumerate(spans):
        for b in spans[i + 1 :]:
            if not (a.start < b.end and b.start < a.end):
                continue
            if LAYER_OF[a.type] == LAYER_OF[b.type]:
                errors.append(f"spans {a.id} and {b.id} overlap")
                continue

            action, other = (a, b) if a.type == "ACTION" else (b, a)
            if not (action.start <= other.start and other.end <= action.end):
                errors.append(f"{other.id} crosses the edge of ACTION {action.id}; an ACTION may only contain whole spans")

    return errors


def check_pointers(spans):
    errors = []
    by_id = {s.id: s for s in spans}
    for span in spans:
        for pointer, targets in POINTERS.items():
            target_id = getattr(span, pointer)
            if target_id is None:
                continue

            target = by_id.get(target_id)
            if target is None:
                errors.append(f"{span.id}: {pointer} {target_id!r} is not a span id")
            elif target is span:
                errors.append(f"{span.id}: {pointer} points at itself")
            elif target.type not in targets[span.type]:
                errors.append(f"{span.id}: {pointer} must point at {sorted(targets[span.type])}, not {target.type}")
            elif target.type in ENTITY_TYPES and first_mention(spans, target) is not target:
                errors.append(f"{span.id}: {pointer} must point at the first mention {first_mention(spans, target).id}, not {target.id}")

    return errors


def check_mentions(spans):
    """Later mentions of a person or relation repeat the first mention's pronoun and owner."""
    errors = []
    by_id = {s.id: s for s in spans}
    for span in spans:
        if span.same_as and by_id.get(span.same_as) and by_id[span.same_as].type != span.type:
            errors.append(f"{span.id}: same_as must point at a {span.type}")
            continue

        first = first_mention(spans, span)
        if first is span:
            continue
        if span.type == "PERSON" and first.attrs["pronoun"] != span.attrs["pronoun"]:
            errors.append(f"{span.id}: pronoun differs from first mention {first.id}")
        if span.owner != first.owner:
            errors.append(f"{span.id}: owner differs from first mention {first.id} (every mention carries the same owner)")

    return errors


def first_name(span):
    words = [w for w in span.text.casefold().replace(".", " ").split() if w not in TITLES]
    return words[0] if words else span.text.casefold()


def mention_key(spans, span, by_id, visiting):
    """What makes two mentions the same entity: a person's first name (titles skipped), or a relation's noun
    together with whose relation it is, so "Ana's mum" and "Bob's mum" stay apart."""
    if span.type == "PERSON":
        return first_name(span)

    owner = by_id.get(span.owner)
    if owner is None or span.id in visiting:
        return (span.text.casefold(), None)
    return (span.text.casefold(), first_mention(spans, owner, visiting | {span.id}).id)


def first_mention(spans, span, visiting=frozenset()):
    if span.type not in ENTITY_TYPES:
        return span

    by_id = {s.id: s for s in spans}
    seen = set()
    while span.same_as and span.same_as in by_id and span.same_as not in seen:
        seen.add(span.same_as)
        span = by_id[span.same_as]

    key = mention_key(spans, span, by_id, visiting)
    return next((s for s in spans if s.type == span.type and not s.same_as and mention_key(spans, s, by_id, visiting) == key), span)


def owner_cycle(spans, span):
    """True when following owner pointers from `span` comes back to a span already visited."""
    by_id = {s.id: s for s in spans}
    seen = set()
    while span is not None:
        if span.id in seen:
            return True
        seen.add(span.id)
        span = by_id.get(span.owner)
    return False


def entity_key(spans, span):
    """Stable key for comparing labellings: the first mention's type and offsets."""
    first = first_mention(spans, span)
    return (first.type, first.start, first.end)
