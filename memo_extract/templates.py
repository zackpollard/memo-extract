"""English reminder titles, keyed like translation strings so the app can localise them."""

import re

TEMPLATES = {
    "ask_outcome": "Ask {name} how {possessive} {event} went",
    "ask_outcome_relation": "Ask {name} how {possessive} {relation}'s {event} went",
    "ask_outcome_first_day": "Ask {name} how {possessive} first day went",
    "ask_outcome_plain": "Ask {name} how it went",
    "wish_luck": "Wish {name} luck with {possessive} {event}",
    "wish_luck_relation": "Wish {name}'s {relation} luck with the {event}",
    "wish_luck_plain": "Wish {name} luck",
    "congratulate": "Congratulate {name} on {possessive} {event}",
    "congratulate_relation": "Congratulate {name} on {possessive} {relation}'s {event}",
    "congratulate_plain": "Congratulate {name}",
    "congratulate_baby": "Congratulate {name} on the baby",
    "check_in": "Check in with {name} about {possessive} {event}",
    "check_in_relation": "Check in with {name} about {possessive} {relation}",
    "check_in_plain": "Check in with {name}",
    "gift_birthday": "Get {name} a birthday gift",
    "gift_relation_birthday": "Get {name}'s {relation} a birthday gift",
    "gift": "Get {name} a gift for {possessive} {event}",
    "gift_relation": "Get {name}'s {relation} a gift for the {event}",
    "gift_plain": "Get {name} a gift",
    "message": "Message {name}",
    "message_birthday": "Message {name} on {possessive} birthday",
    "message_event": "Message {name} about {possessive} {event}",
    "call": "Call {name}",
    "call_birthday": "Call {name} on {possessive} birthday",
    "call_event": "Call {name} about {possessive} {event}",
    "meet": "Meet up with {name}",
}

POSSESSIVES = {"she": "her", "he": "his", "they": "their", "unknown": "their"}
# "moving to Leeds", "getting married", "retiring" are verb phrases; "driving test", "leaving drinks", "wedding" are nouns
VERB_PHRASE = re.compile(
    r"^(?!(wedding|christening|housewarming|meeting|reading|screening|hearing|fitting|opening)\b)\w+ing(\s+(to|up|out|back|off|on|over|away|into|in|abroad|home|married|engaged|freelance|a|an|the|his|her|their)\b.*)?$",
    re.IGNORECASE,
)
FINITE_VERB = re.compile(
    r"^(\w+ed|had|has|got|gets|went|goes|was|is|are|made|broke|lost|found|left|took|came|fell|split|quit)\b", re.IGNORECASE
)
FIRST_DAY = re.compile(r"\b(new job|first day|start|starts|starting|new role)\b", re.IGNORECASE)
# words after "her" that mark it as an object ("get her a gift") rather than a possessive ("her mum")
OBJECT_FOLLOWERS = {
    "a",
    "an",
    "the",
    "some",
    "something",
    "anything",
    "to",
    "for",
    "about",
    "on",
    "at",
    "in",
    "up",
    "out",
    "back",
    "how",
    "that",
    "this",
    "when",
    "what",
    "if",
    "and",
    "know",
    "luck",
    "well",
    "over",
    "round",
    "around",
    "soon",
}


def title_for(kind, name, pronoun, event=None, event_type=None, relation=None):
    """Reminder title for a follow-up kind (an EVENT followup or ACTION action_type)."""
    key = template_key(kind, event, event_type, relation)
    if key is None:
        return None

    if event and FINITE_VERB.match(event):
        # "had tonsils out", "moved back" do not fit "about his {event}"; say less rather than something ungrammatical
        return title_for(kind, name, pronoun, None, event_type, relation)

    template = TEMPLATES[key]
    if event and not relation and VERB_PHRASE.match(event):
        template = template.replace("{possessive} {event}", "{event}")  # "Congratulate Sam on retiring", not "on his retiring"
    return template.format(name=name, possessive=POSSESSIVES[pronoun], event=event, relation=relation)


def template_key(kind, event, event_type, relation):
    if kind in ("message", "call"):
        if event_type == "birthday":
            return f"{kind}_birthday"
        return f"{kind}_event" if event else kind
    if kind == "meet":
        return "meet"
    if kind == "congratulate" and event_type == "baby" and not relation:
        return "congratulate_baby"
    if kind == "gift" and event_type == "birthday":
        return "gift_relation_birthday" if relation else "gift_birthday"
    if kind == "ask_outcome" and event_type == "job" and event and FIRST_DAY.search(event) and not relation:
        return "ask_outcome_first_day"
    if kind not in ("ask_outcome", "wish_luck", "congratulate", "check_in", "gift"):
        return None
    if relation and (event or kind == "check_in"):
        return f"{kind}_relation"
    return kind if event else f"{kind}_plain"


def rewrite_action(text, name):
    """Use the user's own words as the title, swapping the object pronoun ("text him") for the person's name.
    Possessives stay as written: in "ask Nasser to cover his clients", "his" is someone else."""
    if name is None:
        return text[:1].upper() + text[1:]

    words = re.split(r"(\W+)", text)
    swapped = False
    for i, word in enumerate(words):
        lower = word.lower()
        following = next((w.lower() for w in words[i + 1 :] if w.strip() and re.match(r"\w", w)), None)
        if not swapped and (lower in ("him", "them") or (lower == "her" and (following is None or following in OBJECT_FOLLOWERS))):
            words[i] = name
            swapped = True
    rewritten = "".join(words).strip()
    return rewritten[:1].upper() + rewritten[1:]
