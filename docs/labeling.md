# Memo labelling spec (v2)

A **memo** is a short note the user types or dictates, usually just after talking to someone: "Just had coffee with Jen, she starts at the hospital on Monday". The tiny on-device model reads a memo and marks **spans** of text, gives some of them **attributes**, and links them with two **pointers** (`owner`, `anchor`). Plain code then turns that into suggestions ("Ask Jen how her first day went", 3 Nov) for the user to review. The model never sees the memo's date and never writes text, so every label must be recoverable from the words in the memo.

This file is the single source of truth for labels. `memo_extract/constants.py` holds the same vocabulary in code, and `tools/validate.py` enforces everything that can be checked mechanically. Consistency matters more than any single judgement call: when two readings are defensible, pick the one these rules point to, every time.

## Record format

One JSON object per line:

```json
{"id": "b007-012", "text": "Jen starts her new job at the hospital on Monday. Remind me to text her that evening.",
 "spans": [
  {"id": "p1", "type": "PERSON", "text": "Jen", "pronoun": "she"},
  {"id": "e1", "type": "EVENT", "text": "new job at the hospital", "owner": "p1", "event_type": "job", "followup": "ask_outcome"},
  {"id": "d1", "type": "DATE", "text": "Monday", "anchor": "e1"},
  {"id": "a1", "type": "ACTION", "text": "text her", "owner": "p1", "anchor": "e1", "action_type": "message", "timing": "on"},
  {"id": "d2", "type": "DATE", "text": "that evening", "anchor": "a1"}
 ]}
```

- `text` is the memo exactly as the user would have typed or dictated it.
- `spans` are listed in order of appearance. When an `ACTION` and a span inside it start at the same character, list the `ACTION` first.
- Each span's `text` is copied **exactly** (same case, same characters) from the memo and starts and ends on word boundaries.
- Each span is placed at the first occurrence of its text at or after the previous span's start that does not overlap an already-placed span of the same layer. That makes repeated words and "Rahul" after "Rahul Gupta" work automatically. Add `"occ": N` (1-based, counting every occurrence in the memo) only to force a different occurrence (rare).
- Spans never overlap, with one exception: an `ACTION` may contain other spans whole ("ask **Kofi** how his **interview** went"). Label those inner spans too.
- `owner` and `anchor` hold the `id` of another span. Leave the key out when there is no target.
- Attributes are required for the span types that have them.

## Span types

| Type | What | Boundaries |
| --- | --- | --- |
| `PERSON` | A named person other than the user: "Jen", "Dr Okafor", "Aunt Rosa", "Tom Baker", "jen" | The name with any attached title or surname. Label **every** mention, not pronouns. A later mention by first name ("Rahul" after "Rahul Gupta") is matched automatically; a nickname or other form ("Sid" after "Siddharth", "Mo" after "Mohammed") needs `"same_as": "<id of the first mention>"` |
| `RELATION` | A person who is never named in the memo, referred to by relationship or role: "mum", "brother", "boss", "kids", "parents", "flatmate" | The relationship noun only, no possessive or article: "her mum" → `mum`. Label every mention. Mentions with the same noun and the same owner are one relation; "Ana's mum" and "Bob's mum" are two |
| `INTEREST` | A hobby, passion, like or favourite thing that helps with conversation or a gift: "pottery", "Arsenal", "jazz", "sourdough", "Taylor Swift", "norfolk coast" | The noun phrase without "loves", "is into", articles or "those". Keep modifiers and post-modifiers that pin down a specific item: "vintage cameras", "proper espresso machine", "fancy candles from the shop in Bath". With no noun phrase, use the minimal verb phrase without subject: "ties his own flies" |
| `EVENT` | A specific happening in someone's life that has (or had) a time: "birthday", "driving test", "new job", "interview at Google", "surgery", "wedding", "trip to Japan", "moving to Leeds", "pregnant" | Prefer the noun phrase, without determiners or possessives: "her driving test" → `driving test`; "starts his new job" → `new job`; "starts reception" → `reception`. Keep a complement that names the employer, school, place or destination: "interview at Google", "made redundant from the bank", "long weekend somewhere warm". With no noun, use the minimal verb phrase without subject or auxiliary: "is moving to Leeds" → `moving to Leeds`, "getting married" |
| `DATE` | Any time expression: "14 May", "May 14th", "14/05", "next week", "sometime next week", "Friday at 3pm", "tomorrow morning", "in two weeks", "in March", "by Friday", "from 5:30", "the next day", "that morning", "afterwards", "b4 it gets cold", "once she's home" | A date and time together are one span ("Friday at 3pm", "14 May at 9"). Drop only a leading `on`, `at`, `@` or `for`. Keep every other leading word (`in`, `by`, `from`, `until`, `since`, `before`, `after`, `b4`) |
| `ACTION` | Something the user explicitly wants to do or be reminded to do ("remind me to", "I should", "need to", "must", "don't forget to", "want to"), or a bare to-do item | The verb phrase without the request words and without its time expression: "Remind me to message her that morning" → `message her`. Drop trailing hedges ("or something", "or whatever"). Verbs joined by "and" that make one task are one ACTION ("load the iPad and drop it round"); separate tasks are separate ACTIONs |
| `FACT` | A durable personal detail worth saving, still true and useful next month: "vegetarian", "allergic to peanuts", "works at the council", "lives in Bristol", "top floor, no lift", "has twins", "only 8", "owns 200+ games", "wants to be a ref", "husband", "cat Mango", and every stated feeling: "worried", "fine", "in bits", "going to miss him loads" | The words needed to understand the fact out of context, without subject or "is"/"'s". Drop intensifiers and stale qualifiers: "really down" → `down`, "v nervous" → `nervous`, "full vegan" → `vegan`, "new partner" → `partner`, "even more relieved" → `relieved`. Intensifiers are really, so, v, very, totally, full, well. Keep softeners and set idioms, which change the meaning: "slightly terrified", "a bit shaken", "worried sick", "over the moon", "chuffed to bits". Split separate feelings: "slightly terrified but mostly relieved" → two FACTs. Leave out a location unless the location is the fact ("lives in Bristol"; "in hospital up in Inverness" → `in hospital`) |

### Special cases

- **Named relatives**: "her brother Sam" → `PERSON` "Sam" with `owner` → her, and `FACT` "brother" (`relationship`) with `owner` → Sam. Use `RELATION` only for people never named.
- **Pets** are not people. Label the pet as a `FACT` (`pet`) owned by its human, with the animal and name together: "cat Mango", "dog Rolo", "new puppy". Leave later mentions of the pet's name unlabelled. Pet events (vet operation, went missing, put to sleep, first birthday) are `EVENT`s owned by the human. Pronouns that refer to the pet do not set anyone's `pronoun`.
- **Pregnancy**: "pregnant", "expecting", "due" is always an `EVENT` (`baby`, `congratulate`), even with no date. `FACT health` is for complications ("morning sickness").
- **A role that starts later** ("starts as head of dept after half term") is its own `EVENT` (`job`, `ask_outcome`) and takes the date, even when a promotion or offer is also labelled; the promotion stays `congratulate`.
- **Gift hints and wishes** are `FACT other`: "vouchers wd go down well", "dropping hints about a nicer hook set", "wants a new kettle".

### Do not label

- The user ("I", "me", "my"), pronouns, or generic filler ("had a chat", "caught up").
- The setting of the conversation ("at the gym", "at 5 a side"), even when it is an activity.
- An event word used as a general frame with no specific occurrence ("for future bday reference").
- An event the memo says is cancelled or called off ("wedding's off"); label what replaced it (the breakup) instead.
- The user's own existing plans stated as fact, not as a request ("I'm taking his mum", "doing food for the bbq"). They are not ACTIONs.
- Situational opinions tied to one moment ("super qualified", "did great"), feelings the memo says are over ("had been worrying, all clear now"), and notes about secrecy ("hasn't told anyone").
- A time expression that only says when the conversation happened is still labelled `DATE` with no anchor ("saw Jen yesterday": `yesterday`).

## Attributes

| Span type | Attribute | Values |
| --- | --- | --- |
| `PERSON` | `pronoun` | `she`, `he`, `they` from a pronoun in the memo that refers to this one person; `unknown` when none does. A plural "they/their" for a couple or group sets nobody's pronoun. Same value on every mention |
| `EVENT` | `event_type` | `birthday`; `anniversary`; `wedding` (also engagement, stag/hen); `baby` (pregnancy, birth, due date, christening); `job` (paid work only: new job, first day, promotion, leaving, retiring, redundancy meetings, reviews); `interview`; `exam` (exams, tests, driving tests, auditions, results); `medical` (surgery, appointment, scan, illness, recovery, diagnosis appointments); `travel` (trip, holiday, flight, visit abroad); `move` (moving house or city, flat viewings); `performance` (gig, play, recital, match, race, competition, presentation; not rehearsals or training); `party` (party, dinner, housewarming, celebration, meet-up, leaving drinks); `school` (starting or finishing nursery, school, uni, a course or PhD, graduation, getting into a school or uni); `loss` (death, funeral, breakup, redundancy); `other` (rehearsals, training, getting into a team or choir, pets arriving, anything else) |
| `EVENT` | `followup` | The single best follow-up for this event **ignoring any explicit request in the memo**, from the table below |
| `ACTION` | `action_type` | Choose by the stated **purpose** when there is one, otherwise by the verb. Purposes: `ask_outcome` (find out how it went: "text her to see how it went"), `check_in` (see how they're doing), `wish_luck` ("text him good luck"), `congratulate` ("send congrats"), `gift` (get, buy or chip in for a present, flowers or a card to give). Verbs: `message` (text, message, email, WhatsApp, write to), `call` (call, ring, phone, FaceTime), `meet` (meet up, visit, pop round, invite, take for coffee), `send` (send or share a thing), `other` (everything else, including signing a card and errands) |
| `ACTION` | `timing` | When the action happens relative to its `anchor` event, judged from all the wording: relative phrases ("the day before" → `before`; "that morning", "on the day" → `on`; "the next day", "afterwards" → `after`), dates on both, or the action itself (asking how something went is `after`; wishing luck is `before`). An action about an event that has already happened is `after`. An ACTION listed straight after a timed ACTION, with no time of its own, takes the same timing. `unspecified` only when there is no anchor or no way to tell |
| `FACT` | `fact_type` | `job` (current work, employer, role, studies), `home` (where they live, housing details), `relationship` (partner, family role, how the user knows them), `diet` (food preferences, allergies, coeliac), `health` (conditions, diagnoses, injuries, pregnancy complications), `pet`, `feeling` (any emotional state, including "fine"), `dislike`, `other` (ages, aspirations, possessions, collections, gift hints) |

Followups (the first matching row wins):

| Event | `followup` |
| --- | --- |
| the user's own event, an event the user attends or takes part in themselves (a party they're going to, taking someone to an appointment), routine plans, or events long past with nothing to follow up (a death two years ago) | `none` |
| medical, loss, an event caused by hardship (going part time to care for someone, flying out for a funeral), or any event the owner is struggling or stressed about (including stressed about hosting it) | `check_in` |
| birthday | `gift` |
| anniversary, wedding, engagement, baby (including pregnancy), graduation, promotion, retiring, a celebrated last day at a job, getting into something, and any success already achieved ("got the job", "passed", "all clear") | `congratulate` |
| an upcoming exam, interview or performance the owner is clearly nervous about (only these three types) | `wish_luck` |
| any other job start, school start, interview, exam, performance, travel, move, or outcome-bearing event | `ask_outcome` |

"Nervous" and "struggling" refer to the event's owner. A parent or partner feeling it does not change the followup; label their feeling as a `FACT`.

## Pointers

**`owner`** says whose span it is. It may be set on `PERSON`, `RELATION`, `INTEREST`, `EVENT`, `ACTION` and `FACT`, and must point to a `PERSON` or `RELATION`.

- `INTEREST`, `FACT`, `EVENT`: the person the detail or event belongs to. "Priti's dad has a hip operation": `operation` → `dad`, `dad` → `Priti`.
- Deaths and funerals belong to the **bereaved** person the user would support, not the person who died: "Funmi's grandma passed away" → `passed away` → `Funmi` (and `grandma` → `Funmi`).
- An event the user shares with one named person ("me and Shanice are planning an Iceland trip") belongs to that person. An event belonging to a couple or group belongs to the first-named person.
- An event arranged by one person for another (a surprise party) belongs to the person it is for.
- `ACTION`: the person the action is directed at or about. "text her" → the person "her" refers to.
- `RELATION`: the person they are a relation of; leave it out for the user's own relations ("my mum").
- `PERSON`: only when the named person is introduced as someone else's relation ("her brother Sam" → Sam's owner is her).
- Resolve pronouns: "She's worried" points at whoever "she" refers to.
- Always point at the **first mention** of a person or relation. Every later mention carries the same `owner` (and `pronoun`) as the first.
- Leave `owner` out when the span belongs to the user or to nobody.

**`anchor`** says what a time or action attaches to.

- `DATE` → the `EVENT` or `ACTION` it times. "Her birthday is 14 May" → `14 May` anchors to `birthday`. "Remind me to text her that evening" → `that evening` anchors to `text her`. A heading date that introduces an occasion with plans under it ("Sat 13th - Keisha's 30th, dinner after") anchors to the occasion.
- Tie-breaks for `DATE` anchors, applied in this order:
  1. A date at the end of a request says when to do it, so it anchors to the `ACTION`: "Remind me to ask Manon how her mum's knee operation went on Tuesday" → `Tuesday` → the ACTION. It anchors to the event only when the wording ties it there inside the request ("ask how her Tuesday op went").
  2. A date that says when something was learned, told or decided ("found out on Monday", "told me last week") has no anchor; it is not the event's time.
  3. A relative time ("a wk after", "the day before") whose target is not labelled anchors to the event it counts from ("flying out Oct 30, back a wk after" → `a wk after` → `flying out`).
- `ACTION` → the `EVENT` it is about. When the action has a time expression relative to an event ("b4 they go", "when she's back"), anchor to that event, and label it if it is a happening ("flying out"). Otherwise anchor to the event that prompted the action. When two related events compete (a celebration lunch and the birthday it celebrates), anchor to the one that has a DATE.
- Leave `anchor` out when there is nothing to attach to.

## Worked examples

```json
{"id": "ex-1", "text": "Bumped into Tomasz, his wife Ania is due in March! He's knackered already lol",
 "spans": [
  {"id": "p1", "type": "PERSON", "text": "Tomasz", "pronoun": "he"},
  {"id": "f1", "type": "FACT", "text": "wife", "owner": "p2", "fact_type": "relationship"},
  {"id": "p2", "type": "PERSON", "text": "Ania", "owner": "p1", "pronoun": "unknown"},
  {"id": "e1", "type": "EVENT", "text": "due", "owner": "p2", "event_type": "baby", "followup": "congratulate"},
  {"id": "d1", "type": "DATE", "text": "in March", "anchor": "e1"},
  {"id": "f2", "type": "FACT", "text": "knackered", "owner": "p1", "fact_type": "feeling"}
 ]}
{"id": "ex-2", "text": "so um lunch with kofi he's got his citizenship ceremony on the 3rd and he's really into chess at the moment remind me to get him something chess related before",
 "spans": [
  {"id": "p1", "type": "PERSON", "text": "kofi", "pronoun": "he"},
  {"id": "e1", "type": "EVENT", "text": "citizenship ceremony", "owner": "p1", "event_type": "other", "followup": "congratulate"},
  {"id": "d1", "type": "DATE", "text": "the 3rd", "anchor": "e1"},
  {"id": "i1", "type": "INTEREST", "text": "chess", "owner": "p1"},
  {"id": "a1", "type": "ACTION", "text": "get him something chess related", "owner": "p1", "anchor": "e1", "action_type": "gift", "timing": "before"},
  {"id": "d2", "type": "DATE", "text": "before", "anchor": "a1"}
 ]}
{"id": "ex-3", "text": "Chat w/ Lucía & her sister. Sister's vegan, Lucía hates coriander. Lucía's flat viewing Sat, ask how it went",
 "spans": [
  {"id": "p1", "type": "PERSON", "text": "Lucía", "pronoun": "she"},
  {"id": "r1", "type": "RELATION", "text": "sister", "owner": "p1"},
  {"id": "r2", "type": "RELATION", "text": "Sister", "owner": "p1"},
  {"id": "f1", "type": "FACT", "text": "vegan", "owner": "r1", "fact_type": "diet"},
  {"id": "p2", "type": "PERSON", "text": "Lucía", "pronoun": "she"},
  {"id": "f2", "type": "FACT", "text": "hates coriander", "owner": "p1", "fact_type": "dislike"},
  {"id": "p3", "type": "PERSON", "text": "Lucía", "pronoun": "she"},
  {"id": "e1", "type": "EVENT", "text": "flat viewing", "owner": "p1", "event_type": "move", "followup": "ask_outcome"},
  {"id": "d1", "type": "DATE", "text": "Sat", "anchor": "e1"},
  {"id": "a1", "type": "ACTION", "text": "ask how it went", "owner": "p1", "anchor": "e1", "action_type": "ask_outcome", "timing": "after"}
 ]}
{"id": "ex-4", "text": "Need to pick up dry cleaning tomorrow and book the car in.",
 "spans": [
  {"id": "a1", "type": "ACTION", "text": "pick up dry cleaning", "action_type": "other", "timing": "unspecified"},
  {"id": "d1", "type": "DATE", "text": "tomorrow", "anchor": "a1"},
  {"id": "a2", "type": "ACTION", "text": "book the car in", "action_type": "other", "timing": "unspecified"}
 ]}
{"id": "ex-5", "text": "Rang Siddharth - his dog Biscuit had an op today, Sid's a bit shaken. Remind me to ask Sid how Biscuit is doing on Friday",
 "spans": [
  {"id": "p1", "type": "PERSON", "text": "Siddharth", "pronoun": "he"},
  {"id": "f1", "type": "FACT", "text": "dog Biscuit", "owner": "p1", "fact_type": "pet"},
  {"id": "e1", "type": "EVENT", "text": "op", "owner": "p1", "event_type": "medical", "followup": "check_in"},
  {"id": "d1", "type": "DATE", "text": "today", "anchor": "e1"},
  {"id": "p2", "type": "PERSON", "text": "Sid", "pronoun": "he", "same_as": "p1"},
  {"id": "f2", "type": "FACT", "text": "a bit shaken", "owner": "p1", "fact_type": "feeling"},
  {"id": "a1", "type": "ACTION", "text": "ask Sid how Biscuit is doing", "owner": "p1", "anchor": "e1", "action_type": "check_in", "timing": "after"},
  {"id": "p3", "type": "PERSON", "text": "Sid", "pronoun": "he", "same_as": "p1"},
  {"id": "d2", "type": "DATE", "text": "Friday", "anchor": "a1"}
 ]}
```

In ex-3, "her sister" makes Lucía's pronoun `she` on every mention. "Sister's" is a second mention of the same relation (`r2`) and repeats its owner. Every later span points at the first mention (`r1` / `p1`).

In ex-5, "Sid" is a nickname, so both later mentions carry `same_as`. The ACTION contains the PERSON "Sid", which is labelled inside it and listed after it. "a bit shaken" keeps "a bit" because softeners change the meaning; only intensifiers are dropped. Biscuit's later mention is not labelled because pets are not people.
