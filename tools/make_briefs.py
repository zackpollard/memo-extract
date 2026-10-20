#!/usr/bin/env python3
"""Write generation briefs (style, topics, names) for the data workflow. Seeded, so reruns give the same briefs."""

import argparse
import json
import random

import _path  # noqa: F401

from memo_extract.names import SURNAMES, TRAIN_NAMES

STYLES = {
    "typed-tidy": "typed on a phone with care: normal capitalisation and punctuation, full sentences",
    "typed-quick": "typed in a hurry: lowercase starts, few commas, abbreviations (bday, tmrw, appt, wk, mtg, w/, b4), the odd typo, emoji rare",
    "dictated": "speech-to-text transcript: mostly lowercase, little or no punctuation, run-on sentences, fillers (um, uh, like, so, oh and), self-corrections ('on tuesday no wednesday'), numbers sometimes as words",
    "recap": "a longer recap after a catch-up: 3 to 6 sentences covering 2 to 4 people, mixed facts and plans",
    "shorthand": "telegraphic notes: fragments, dashes, slashes and @, 'Jen - new job @ NHS from Mon. ask how 1st wk went'",
    "mixed": "a mix of all styles: tidy typing, hurried typing, dictation transcripts, shorthand and longer recaps",
}

TOPICS = [
    "birthdays, gift ideas and what people are into",
    "anniversaries, engagements and weddings",
    "pregnancies, new babies and christenings",
    "new jobs, first days, promotions, leaving and retiring",
    "job interviews and applications",
    "exams, tests, driving tests, auditions and results days",
    "operations, hospital stays, appointments and recovery",
    "illness, injuries and someone's parent or child being unwell",
    "holidays, trips abroad and long flights",
    "moving house, flat viewings and new cities",
    "gigs, plays, recitals, matches, races and competitions",
    "parties, dinners, housewarmings and things the user was invited to",
    "graduations and kids' milestones (first day of school, exams)",
    "bereavement, funerals, breakups and redundancy",
    "pets: new puppies, sick cats, pet birthdays",
    "food preferences, allergies, diets and drinks people like",
    "hobbies and interests in detail (sport teams, music, crafts, games, books)",
    "work chat about colleagues, managers and clients",
    "plans to meet up, call, visit or send someone something",
    "facts only: where people live and work, family details, with no event or reminder",
    "notes about errands or the user's own plans with no other person in them",
    "several people and relatives in one memo with pronouns that need resolving",
    "relatives of the person the user spoke to (their mum, kids, partner, brother)",
    "explicit 'remind me to...' requests with times relative to an event ('the day before', 'that evening', 'the week after')",
    "vague or imprecise timing ('sometime next month', 'in the spring', 'soon', 'after Christmas')",
]

DATE_FOCUS = [
    "day-month dates written British style ('14 May', '3rd of June', '14/05')",
    "month-day dates written American style ('May 14', 'June 3rd', '5/14')",
    "dates with years ('2 November 2026', 'March 2027')",
    "weekdays and relative days ('Friday', 'next Tuesday', 'this weekend', 'tomorrow', 'in a fortnight')",
    "times of day attached to dates ('Friday at 3pm', 'tomorrow morning', 'the 12th at half 9')",
    "anaphoric times relative to the event ('that morning', 'the next day', 'afterwards', 'the day before', 'a week after')",
    "vague ranges ('sometime next week', 'end of the month', 'early March', 'over the summer')",
]


def make_brief(rng, brief_id, split, per_brief):
    style = rng.choice(list(STYLES))
    names = rng.sample(TRAIN_NAMES, 30)
    return {
        "id": brief_id,
        "split": split,
        "n": per_brief,
        "style": style,
        "style_description": STYLES[style],
        "topics": rng.sample(TOPICS, 3),
        "date_focus": rng.sample(DATE_FOCUS, 2),
        "names": names,
        "surnames": rng.sample(SURNAMES, 8),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--per-brief", type=int, default=100)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--prefix", required=True, help="brief id prefix, e.g. 'p' for pilot")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    briefs = [make_brief(rng, f"{args.prefix}{i:03d}", args.split, args.per_brief) for i in range(args.count)]
    print(json.dumps(briefs, ensure_ascii=False))


if __name__ == "__main__":
    main()
