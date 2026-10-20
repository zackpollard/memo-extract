"""Turn a labelled memo into what the app shows: people, details to save, and reminder suggestions to confirm."""

from dataclasses import replace
from datetime import date, timedelta

from .constants import DEFAULT_TIME, FOLLOWUP_TIMING, GIFT_LEAD_DAYS, NUDGE_DAYS, PART_OF_DAY_TIMES
from .dates import Resolution, resolve
from .records import first_mention
from .templates import rewrite_action, title_for


def display_name(text):
    return text if any(c.isupper() for c in text) else text.title()


class Context:
    def __init__(self, memo, today, day_first=True):
        self.memo, self.today, self.day_first = memo, today, day_first
        self.by_id = {s.id: s for s in memo.spans}

    def of_type(self, span_type):
        return [s for s in self.memo.spans if s.type == span_type]

    def entities(self, span_type):
        return [s for s in self.of_type(span_type) if first_mention(self.memo.spans, s) is s]

    def get(self, span_id):
        return self.by_id.get(span_id) if span_id else None

    def label(self, entity, seen=frozenset()):
        if entity.type == "PERSON":
            return display_name(entity.text)

        owner = self.get(entity.owner)
        if owner is None or owner.id in seen:
            return f"your {entity.text.lower()}"
        return f"{self.label(owner, seen | {entity.id})}'s {entity.text.lower()}"

    def recipient(self, owner_id):
        """(name, pronoun, None) for whoever an explicit action is directed at: "call her mum" calls Priya's mum."""
        owner = self.get(owner_id)
        if owner is None:
            return None
        return self.label(owner), owner.attrs.get("pronoun", "unknown"), None

    def target(self, owner_id):
        """(name, pronoun, relation) of the person to contact about something owned by `owner_id`, or None."""
        owner = self.get(owner_id)
        if owner is None:
            return None
        if owner.type == "PERSON":
            return display_name(owner.text), owner.attrs["pronoun"], None

        person = self.get(owner.owner)
        if person is not None and person.type == "PERSON":
            return display_name(person.text), person.attrs["pronoun"], owner.text.lower()
        return f"your {owner.text.lower()}", "unknown", None

    def dates_for(self, span):
        return [s for s in self.of_type("DATE") if s.anchor == span.id]

    def resolve(self, text, anchor=None):
        when = resolve(text, self.today, anchor=anchor, day_first=self.day_first)
        if anchor is not None and when.anaphoric and (anchor.kind != "exact" or anchor.ambiguous):
            when = replace(when, ambiguous=True)  # "afterwards" is only as certain as the event it follows
        return when

    def resolve_all(self, date_spans, anchor=None):
        """Merge the DATE spans timing one thing: the first that names a day, then clock times ("at 3",
        "that morning") resolved on that day. Ambiguity from any contributing span carries over."""
        if not date_spans:
            return None

        times = [s for s in date_spans if is_time_only(s.text, self.today, self.day_first)]
        days = [self.resolve(s.text, anchor) for s in date_spans if s not in times]
        best = next((r for r in days if r.start is not None), days[0] if days else None)
        if not times:
            return best

        base = best if best is not None and best.start is not None else anchor
        timed = [self.resolve(s.text, base) for s in times]
        if best is None:
            return timed[0]
        clock = next((r for r in timed if r.time or r.part_of_day), None)
        if clock is None or best.time or best.part_of_day:
            return best
        return replace(best, time=clock.time, part_of_day=clock.part_of_day, ambiguous=best.ambiguous or clock.ambiguous)

    def event_when(self, event):
        return self.resolve_all(self.dates_for(event)) if event is not None else None

    def interests(self, owner_id):
        return [s.text for s in self.of_type("INTEREST") if s.owner == owner_id]


TIME_ONLY_PROBE = Resolution(kind="exact", start=date(2000, 1, 3), end=date(2000, 1, 3))


def is_time_only(text, today, day_first):
    """A clock time or part of day with no day of its own: it lands on whatever day it is anchored to."""
    probe = resolve(text, today, anchor=TIME_ONLY_PROBE, day_first=day_first)
    return probe.start == TIME_ONLY_PROBE.start and probe.relation is None and bool(probe.time or probe.part_of_day)


def shift(when, relation, days):
    """One proposed day `days` before/after (or on) a resolved event; uncertain when the event was."""
    if when is None or when.start is None:
        return None

    day = {"before": when.start - timedelta(days=days), "after": when.end + timedelta(days=days)}.get(relation, when.start)
    keep_time = relation not in ("before", "after")
    return Resolution(
        kind="exact",
        start=day,
        end=day,
        time=when.time if keep_time else None,
        part_of_day=when.part_of_day if keep_time else None,
        ambiguous=when.ambiguous or when.kind != "exact",
    )


def schedule(when, today):
    """(date, time, confirm reasons) for a reminder."""
    if when is None or when.start is None:
        return None, DEFAULT_TIME, ["date"]

    confirm = [] if when.kind == "exact" and not when.ambiguous else ["date"]
    day = max(when.start, today)
    time = when.time or PART_OF_DAY_TIMES.get(when.part_of_day, DEFAULT_TIME)
    if when.time is None and when.part_of_day is not None:
        confirm.append("time")
    return day.isoformat(), time, confirm


def reminder(ctx, kind, title, target, when, source, context=()):
    day, time, confirm = schedule(when, ctx.today)
    return {
        "kind": kind,
        "title": title,
        "person": target[0] if target else None,
        "date": day,
        "time": time,
        "source": source,
        "confirm": confirm,
        "context": list(context),
    }


def explicit_reminders(ctx):
    reminders = []
    for action in ctx.of_type("ACTION"):
        target = ctx.recipient(action.owner)
        event = ctx.get(action.anchor)
        event_when = ctx.event_when(event)
        dates = ctx.dates_for(action)
        timing = action.attrs["timing"]
        if dates:
            when = ctx.resolve_all(dates, anchor=event_when)
        elif timing != "unspecified":
            when = shift(event_when, timing, GIFT_LEAD_DAYS if action.attrs["action_type"] == "gift" and timing == "before" else NUDGE_DAYS)
        else:
            when = event_when

        title = None
        if target is not None:
            name, pronoun, relation = target
            event_text, event_type = (event.text, event.attrs["event_type"]) if event else (None, None)
            title = title_for(action.attrs["action_type"], name, pronoun, event_text, event_type, relation)
            title = title or rewrite_action(action.text, name)
        title = title or rewrite_action(action.text, None)
        context = ctx.interests(action.owner) if action.attrs["action_type"] == "gift" else ()
        reminders.append(reminder(ctx, action.attrs["action_type"], title, target, when, "explicit", context))
    return reminders


def suggested_reminders(ctx):
    covered = {a.anchor for a in ctx.of_type("ACTION") if a.anchor}
    reminders = []
    for event in ctx.of_type("EVENT"):
        followup = event.attrs["followup"]
        target = ctx.target(event.owner)
        if event.id in covered or followup == "none" or target is None:
            continue

        name, pronoun, relation = target
        days = GIFT_LEAD_DAYS if followup == "gift" else NUDGE_DAYS
        when = shift(ctx.event_when(event), FOLLOWUP_TIMING[followup], days)
        title = title_for(followup, name, pronoun, event.text, event.attrs["event_type"], relation)
        context = ctx.interests(event.owner) if followup == "gift" else ()
        reminders.append(reminder(ctx, followup, title, target, when, "suggested", context))
    return reminders


def details(ctx):
    found = []
    for span in ctx.memo.spans:
        owner = ctx.get(span.owner)
        person = ctx.label(owner) if owner else None
        if span.type == "INTEREST":
            found.append({"person": person, "kind": "interest", "text": span.text})
        elif span.type == "FACT":
            found.append({"person": person, "kind": span.attrs["fact_type"], "text": span.text})
        elif span.type == "EVENT":
            when = ctx.event_when(span)
            event_type = span.attrs["event_type"]
            kind = event_type if event_type in ("birthday", "anniversary") else "event"
            entry = {"person": person, "kind": kind, "text": span.text, "event_type": event_type}
            if when is not None and when.start is not None:
                recurring = kind != "event" and when.kind == "exact"
                entry["date"] = when.start.strftime("--%m-%d") if recurring else when.start.isoformat()
                if when.kind != "exact":
                    entry["date_end"] = when.end.isoformat()
            found.append(entry)
    return found


def people(ctx, contacts):
    found = []
    for person in ctx.entities("PERSON"):
        related = ctx.get(person.owner)
        relationship = next((f.text for f in ctx.of_type("FACT") if f.owner == person.id and f.attrs["fact_type"] == "relationship"), None)
        entry = {
            "name": display_name(person.text),
            "pronoun": person.attrs["pronoun"],
            "related_to": ctx.label(related) if related else None,
            "relationship": relationship,
        }
        if contacts is not None:
            first = person.text.split()[0].casefold()
            entry["matches"] = [c for c in contacts if c.split()[0].casefold() == first]
        found.append(entry)
    for relation in ctx.entities("RELATION"):
        found.append(
            {
                "name": ctx.label(relation),
                "pronoun": "unknown",
                "related_to": ctx.label(ctx.get(relation.owner)) if relation.owner else None,
                "relationship": relation.text.lower(),
            }
        )
    return found


def suggest(memo, today, contacts=None, day_first=True):
    """Everything the review screen needs. `contacts` (full names) enables "which Alex?" checks."""
    ctx = Context(memo, today, day_first)
    found_people = people(ctx, contacts)
    reminders = explicit_reminders(ctx) + suggested_reminders(ctx)
    if contacts is not None:
        ambiguous = {p["name"] for p in found_people if len(p.get("matches", [])) > 1}
        for r in reminders:
            if r["person"] in ambiguous:
                r["confirm"].insert(0, "person")
    return {"people": found_people, "details": details(ctx), "reminders": reminders}
