# Vocabulary

- **memo**: a short note the user types or dictates after talking to someone.
- **span**: a labelled piece of memo text (`PERSON`, `RELATION`, `INTEREST`, `EVENT`, `DATE`, `ACTION`, `FACT`).
- **mention / entity**: every occurrence of a person's name is a mention; mentions of the same person form one entity, represented by its first mention.
- **owner**: pointer from a span to the person (or relation) it belongs to.
- **anchor**: pointer from a `DATE` to the event or action it times, or from an `ACTION` to the event it is about.
- **followup**: the implicit follow-up an `EVENT` deserves (`ask_outcome`, `check_in`, ...), independent of explicit requests.
- **explicit reminder**: produced from an `ACTION` span. **Suggested reminder**: produced from an `EVENT` followup when no `ACTION` covers that event.
- **resolution**: the deterministic reading of a `DATE` span (`memo_extract/dates.py`): exact day, range, vague or unparsed.
- **confirm reasons**: why the app should ask before saving a reminder: `person` (several contacts match), `date` (missing, range, vague or ambiguous), `time` (a part of day was given, not a clock time).
- **brief**: one data-generation assignment (style, topics, date styles, names).
- **gen / lab / adj**: the generator's labels, the blind second annotator's labels, and the adjudicator's resolution of their disagreements.
- **strict F1**: span F1 where a span only counts if its type, boundaries, attributes and pointers are all right.
