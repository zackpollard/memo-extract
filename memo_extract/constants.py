"""Label vocabulary shared by the labelling tools, the model and the suggestion layer.

The first value of every attribute tuple is its default.
"""

SPAN_TYPES = ("PERSON", "RELATION", "INTEREST", "EVENT", "DATE", "ACTION", "FACT")

# Spans in different layers may nest (an ACTION can contain a PERSON); spans in the same layer never overlap.
TAG_LAYERS = {
    "entity": ("PERSON", "RELATION", "INTEREST", "EVENT", "DATE", "FACT"),
    "action": ("ACTION",),
}
LAYER_OF = {span_type: layer for layer, types in TAG_LAYERS.items() for span_type in types}

PRONOUNS = ("unknown", "she", "he", "they")
EVENT_TYPES = (
    "other",
    "birthday",
    "anniversary",
    "wedding",
    "baby",
    "job",
    "interview",
    "exam",
    "medical",
    "travel",
    "move",
    "performance",
    "party",
    "school",
    "loss",
)
FOLLOWUPS = ("none", "ask_outcome", "wish_luck", "congratulate", "check_in", "gift")
ACTION_TYPES = (
    "other",
    "message",
    "call",
    "ask_outcome",
    "check_in",
    "wish_luck",
    "congratulate",
    "gift",
    "meet",
    "send",
)
TIMINGS = ("unspecified", "before", "on", "after")
FACT_TYPES = ("other", "job", "home", "relationship", "diet", "health", "pet", "feeling", "dislike")

# span type -> attribute -> allowed values
ATTRIBUTES = {
    "PERSON": {"pronoun": PRONOUNS},
    "EVENT": {"event_type": EVENT_TYPES, "followup": FOLLOWUPS},
    "ACTION": {"action_type": ACTION_TYPES, "timing": TIMINGS},
    "FACT": {"fact_type": FACT_TYPES},
}

# span type -> span types its pointer may target (a missing pointer means "the user / nobody")
OWNER_TARGETS = {
    "PERSON": {"PERSON", "RELATION"},
    "RELATION": {"PERSON", "RELATION"},
    "INTEREST": {"PERSON", "RELATION"},
    "EVENT": {"PERSON", "RELATION"},
    "ACTION": {"PERSON", "RELATION"},
    "FACT": {"PERSON", "RELATION"},
}
ANCHOR_TARGETS = {
    "DATE": {"EVENT", "ACTION"},
    "ACTION": {"EVENT"},
}

POINTERS = {"owner": OWNER_TARGETS, "anchor": ANCHOR_TARGETS}

# span types whose repeated mentions refer to the same entity; pointers must target the first mention
ENTITY_TYPES = {"PERSON", "RELATION"}
# words skipped when matching a later mention ("Rahul") to an earlier one ("Dr Rahul Gupta")
TITLES = {
    "dr",
    "mr",
    "mrs",
    "ms",
    "miss",
    "prof",
    "aunt",
    "auntie",
    "aunty",
    "uncle",
    "nan",
    "nana",
    "grandma",
    "grandpa",
    "granny",
    "cousin",
    "sir",
    "dame",
}

MAX_MEMO_CHARS = 700

# Suggestion policy
GIFT_LEAD_DAYS = 7  # suggest buying a gift this many days before the event
NUDGE_DAYS = 1  # "before" and "after" follow-ups land this many days from the event
DEFAULT_TIME = "09:00"
PART_OF_DAY_TIMES = {"morning": "09:00", "afternoon": "14:00", "evening": "18:00", "night": "20:00"}
# EVENT followup -> when the suggested reminder lands relative to the event
FOLLOWUP_TIMING = {"ask_outcome": "after", "check_in": "after", "wish_luck": "before", "congratulate": "on", "gift": "before"}
