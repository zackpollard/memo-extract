"""Score predicted memos against gold labels at span, attribute, pointer and whole-memo level."""

from collections import Counter, defaultdict

from .constants import POINTERS
from .records import entity_key
from .suggest import suggest


def span_key(span):
    return (span.type, span.start, span.end)


def pointer_key(memo, span, pointer):
    target_id = getattr(span, pointer)
    if target_id is None:
        return None

    target = next(s for s in memo.spans if s.id == target_id)
    return entity_key(memo.spans, target)


def f1(tp, n_pred, n_gold):
    precision = tp / n_pred if n_pred else 1.0
    recall = tp / n_gold if n_gold else 1.0
    return {"p": precision, "r": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}


def compare_span(gold, gold_span, pred, pred_span):
    """{check name: correct?} for every attribute and pointer the gold span carries."""
    checks = {f"{gold_span.type}.{attr}": pred_span.attrs.get(attr) == value for attr, value in gold_span.attrs.items()}
    for pointer, targets in POINTERS.items():
        if gold_span.type in targets:
            checks[f"{pointer}:{gold_span.type}"] = pointer_key(gold, gold_span, pointer) == pointer_key(pred, pred_span, pointer)
    return checks


def score(golds, preds):
    spans = defaultdict(Counter)
    checks = defaultdict(Counter)
    strict_tp = exact = n_pred = n_gold = 0
    for gold, pred in zip(golds, preds, strict=True):
        gold_spans = {span_key(s): s for s in gold.spans}
        pred_spans = {span_key(s): s for s in pred.spans}
        n_pred += len(pred_spans)
        n_gold += len(gold_spans)
        for key in pred_spans:
            spans[key[0]]["pred"] += 1
        for key in gold_spans:
            spans[key[0]]["gold"] += 1

        memo_ok = gold_spans.keys() == pred_spans.keys()
        for key in gold_spans.keys() & pred_spans.keys():
            spans[key[0]]["tp"] += 1
            span_checks = compare_span(gold, gold_spans[key], pred, pred_spans[key])
            for name, ok in span_checks.items():
                checks[name]["correct"] += ok
                checks[name]["total"] += 1
            if all(span_checks.values()):
                strict_tp += 1
            else:
                memo_ok = False
        exact += memo_ok

    total = Counter()
    for counts in spans.values():
        total.update(counts)
    return {
        "memos": len(golds),
        "memo_exact": exact / len(golds) if golds else 0.0,
        "strict": f1(strict_tp, n_pred, n_gold),
        "spans": f1(total["tp"], total["pred"], total["gold"]),
        "by_type": {t: f1(c["tp"], c["pred"], c["gold"]) | {"support": c["gold"]} for t, c in sorted(spans.items())},
        "checks": {name: c["correct"] / c["total"] for name, c in sorted(checks.items())},
    }


def suggestion_keys(output):
    """What the user would see, as comparable sets."""
    return {
        "reminders": {(r["person"], r["title"], r["date"]) for r in output["reminders"]},
        "reminder_intents": {(r["person"], r["kind"], r["date"]) for r in output["reminders"]},
        "details": {(d["person"], d["kind"], d["text"].casefold()) for d in output["details"]},
        "people": {p["name"].casefold() for p in output["people"]},
    }


def score_suggestions(golds, preds, today):
    """F1 of the reminders, details and people derived from predicted vs gold labels, plus memos fully right."""
    totals = {part: Counter() for part in ("reminders", "reminder_intents", "details", "people")}
    all_right = 0
    for gold, pred in zip(golds, preds, strict=True):
        gold_keys, pred_keys = suggestion_keys(suggest(gold, today)), suggestion_keys(suggest(pred, today))
        all_right += gold_keys == pred_keys
        for part, counts in totals.items():
            counts["tp"] += len(gold_keys[part] & pred_keys[part])
            counts["pred"] += len(pred_keys[part])
            counts["gold"] += len(gold_keys[part])
    return {
        "memos_fully_right": all_right / len(golds) if golds else 0.0,
        **{part: f1(c["tp"], c["pred"], c["gold"]) for part, c in totals.items()},
    }
