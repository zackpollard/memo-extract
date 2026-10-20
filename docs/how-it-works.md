# How memo-extract works, and how it was built

A plain-English walkthrough for someone who has never trained a model. It explains what the system does, the ideas it rests on, and the order things were done in. The technical handover for whoever continues the work is [handoff.md](handoff.md).

## 1. The goal

After a conversation you jot down or dictate a short memo:

> Priya's mum is having surgery next week. She's worried.

The app should notice the useful parts and offer them for review:

- **People**: Priya, and Priya's mum.
- **Details to save**: Priya's mum has surgery (a medical event) next week; Priya is worried.
- **A reminder to confirm**: "Check in with Priya about her mum". The date needs confirming because "next week" is not a precise day.

The six examples it was designed around:

| Memo | What the app should offer |
| --- | --- |
| Maya loves pottery. Her birthday is 14 May. Remind me to message her that morning. | Save pottery as an interest and 14 May as her birthday; a birthday-morning reminder, asking you to confirm the time |
| Daniel starts his new job on 2 November 2026. Remind me to ask how it went the next day. | Save the job start; "Ask Daniel how his first day went" on 3 November 2026 |
| Alex has an interview sometime next week. I should check in afterwards. | Save the interview; a follow-up, but ask which Alex and which day |
| Maya has her driving test on 12 November. | "Ask Maya how her driving test went" after 12 November |
| Daniel's birthday is 14 May. He loves pottery. | "Get Daniel a birthday gift" before 14 May, with pottery as the gift idea |
| Priya's mum is having surgery next week. She's worried. | "Check in with Priya about her mum", confirm the date |

The hard constraint is that it must run **on the phone**, including old phones: small to download, fast, and private (memos never leave the device).

## 2. The key idea: the model reads, plain code writes

The obvious approach is to ask a chatbot-style model (a large language model, or LLM) to read the memo and write the reminders. That was rejected:

- **Size and speed.** Even the smallest useful chat models are hundreds of megabytes and generate text one word at a time. On an old phone that is slow and heavy.
- **Made-up facts.** A model that writes free text can write a wrong date or a person who was never mentioned, and you cannot easily tell.

So the job is split in two:

1. A **small model reads** the memo and highlights pieces of it: "Priya" is a person, "surgery" is an event, "next week" is a date, and that date belongs to the surgery. It never writes any text of its own.
2. **Ordinary code writes** the suggestions from those highlights. It works out what "next week" means from today's date, picks the wording ("Check in with … about …") from fixed templates, and decides when to ask you to confirm.

Because every suggestion points back to words that are actually in the memo, the system cannot invent a date or a person. The model is also far smaller: it only has to recognise things, not generate language.

## 3. A little background

**A model** is a large mathematical function with millions of adjustable numbers (called *parameters* or *weights*). You show it examples with the right answers and nudge the numbers, a little at a time, until its answers get closer to the right ones. That nudging is called **training**.

**Tokens.** Before a model sees text, the text is split into small pieces called tokens, roughly words or parts of words: `priya`, `'`, `s`, `mum`, `is`, `having`, `surgery`, …. Each token has an entry in a fixed list, the **vocabulary**.

**An encoder** is a kind of model that reads all the tokens of a text at once and produces, for each token, a list of a few hundred numbers describing what that token means *in this sentence*. "Mum" next to "Priya's" comes out different from "mum" at the start of a sentence. The encoders used here are all in the BERT family.

**Pretraining and fine-tuning.** Training an encoder from nothing takes huge amounts of text and compute. Others have already done that and published the results (**pretrained** models). We start from one of those, which already "knows" English, and **fine-tune** it: we add a few small output layers for our task and train the whole thing on our own examples. Fine-tuning a small encoder is cheap enough to do on a desktop CPU.

## 4. What the model actually outputs

Here is the real output of the 8 MB model for the Priya memo:

| Highlight | Type | Extra answers | Points to |
| --- | --- | --- | --- |
| Priya | `PERSON` | pronoun: she | |
| mum | `RELATION` | | owner → Priya |
| surgery | `EVENT` | event type: medical; follow-up: check in | owner → mum |
| next week | `DATE` | | anchor → surgery |
| worried | `FACT` | fact type: feeling | owner → Priya |

The model produces this in three steps:

1. **Highlighting (tagging).** For every token it picks a tag: `B-PERSON` (a person's name starts here), `I-PERSON` (the name continues), `O` (nothing), and so on for each type. This standard trick is called **BIO tagging** (Begin, Inside, Outside). There are two layers of tags, because a reminder request ("remind me to message her") can contain other highlights inside it.
2. **Answering questions about each highlight.** Small extra outputs, called **heads**, look at each highlighted piece and answer multiple-choice questions: what kind of event is this (birthday, wedding, job, exam, medical, …, 15 kinds)? What follow-up does it deserve (ask how it went, check in, wish luck, congratulate, buy a gift, or none)? Is this fact a feeling, a job, a pet, a diet?
3. **Pointing.** Two more heads answer "who does this belong to?" (*owner*) and "what does this date time?" (*anchor*). Each highlight scores every other highlight, plus a "nobody" option, and the best score wins.

Then plain code takes over:

- **The date resolver** (`memo_extract/dates.py`) turns "next week" into a real range: Monday 26 October to Sunday 1 November 2026 (if today is 20 October). It understands things like "14 May", "the 21st", "the next day", "end of Jan", "Friday" and "sometime next week", and says when a date is vague or ambiguous. It is ordinary code with about 1,100 tests, so it is predictable and never guesses.
- **The suggestion layer** (`memo_extract/suggest.py` and `templates.py`) applies rules. A surgery with the follow-up "check in" becomes "Check in with Priya about her mum". Because the surgery belongs to the mum and the mum belongs to Priya, the reminder is about Priya (you would text Priya, not her mum). The date is a range, so the reminder is scheduled after it ends and marked **confirm: date**. If your contacts contain two Alexes, an "Alex" reminder is marked **confirm: person**.

The final suggestion from the model for this memo was:

```json
{"title": "Check in with Priya about her mum", "person": "Priya", "date": "2026-11-02", "time": "09:00", "source": "suggested", "confirm": ["date"]}
```

## 5. Where the training data came from

No public dataset of personal memos labelled this way exists, so one had to be made. That was most of the work.

**A rulebook first.** [labeling.md](labeling.md) defines exactly what counts as a person, an event or a date, where each highlight starts and ends, and what every pointer means. It is the single source of truth: the data, the model and the evaluation all follow it. Without a precise rulebook, examples contradict each other and the model learns the contradictions.

**Then Claude agents, in an assembly line.** Each batch of data started from a **brief**: a short assignment such as "20 memos, dictated style, topics: health and family, dates written as weekdays, these names". For each brief:

1. A **writer** agent wrote memo text only, with no labels.
2. Two **annotator** agents each labelled the memos *independently*, without seeing the other's work ("blind").
3. Wherever the two disagreed, an **adjudicator** agent read the rulebook and decided the right answer.

Two blind annotators are used for the same reason exams are double-marked: when two careful readers disagree, either one made a mistake or the rulebook is unclear. Disagreements were used to fix both.

**A pilot first.** A small trial of 240 memos came first. In the pilot the writer also labelled its own memos, and a second agent relabelled them blind. They agreed on 72% of memos. When the adjudicator settled the rest, the writer turned out to be right far less often than the fresh pair of eyes: 20 times against 42. Writing and labelling at once is error-prone, so the main run split them into separate agents. The adjudicators' notes also became the second version of the rulebook (for example: hobbies described as verbs, "ties his own flies", count as interests; cancelled events are not labelled).

**The main run.** 196 briefs produced 11,600 memos. Each workflow runs at most 16 agents at once, so the briefs were split across two copies of the same workflow running side by side. That took about two hours of agent time, plus a two-and-a-half-hour pause when the account hit its usage limit. Annotators agreed on every detail of 62% of memos; the adjudicator settled the other 4,402 and dropped 13 that could not be labelled consistently. Agreement was lower than in the pilot because the main run deliberately included harder cases (nicknames, pets, cancelled plans, shared events), and because some disagreements are real ambiguities in English: does "next week" in "remind me to call her next week" time the call or the event?

How often the two annotators agree also tells you **how good a model can possibly get**. Scored against each other with the model's own measure (section 7), the two annotators reach 0.918. A model that matched that would be as consistent as a careful person.

The scripts that ran these assembly lines are in [`workflows/`](../workflows). The final labelled set has 10,787 training memos, 300 development memos and 500 test memos. A further 30,000 memos were written without labels (another 500 agents) for the teacher step in section 9.

One lesson from the process: the annotator agents shared a scratch folder and some of them wrote helper scripts with the same file names, so they briefly overwrote each other's work (35 briefs were affected). Agreement in those briefs was no worse than elsewhere, so the data was kept, but parallel agents should never share a scratch folder.

## 6. Training on a desktop CPU

The machine has no graphics card (GPU), so all training ran on its 24-thread CPU. Small encoders train fine like that. Every training run took between 5 and 27 minutes. The 8 MB model took about 15 minutes on the 10,787 gold memos, and 27 minutes with the 30,000 silver memos and the teacher added (section 9). One surprise: PyTorch was fastest with 8 to 16 threads, and slower with all 24.

Training repeats over the data several times (each pass is an **epoch**). After each pass the model is scored on the development set, and the best-scoring version is kept.

## 7. Measuring how good it is

**Three separate piles of data.** The model trains on the *train* set. Choices such as how long to train are made by watching the *dev* (development) set. The *test* set's labels are used only at the end, so the final score is on memos the model and its builder never tuned against. Otherwise the score flatters the model. One small exception: trimming the vocabulary (section 8) kept every word piece the test memos use. Without the test texts, 10 of the 500 test memos would be split into tokens differently, so the trimmed models may be flattered slightly.

**F1**, the main score, balances two questions:

- **Precision**: of the things the model highlighted, how many were right?
- **Recall**: of the things it should have highlighted, how many did it find?

F1 combines the two into one number between 0 and 1, and it is only high when both are. If a memo has 10 things to find and the model finds 8, all correct, plus 2 wrong ones, precision is 8/10, recall is 8/10 and F1 is 0.8.

**Strict F1** counts a highlight as right only if everything about it is right: type, exact boundaries, every extra answer and every pointer. The project also reports scores on the final product: **reminders F1** (were the right reminders proposed, with the right person, date and wording?), **details F1**, and **fully right** (the share of memos where the reminders, details and people all match: each reminder's person, date and wording, each detail's person, kind and text, and the people's names. Reminder times and saved event dates are not checked).

## 8. Making it small

The phone budget drove four techniques.

**Smaller encoders.** The same task was trained on encoders from 2.5 million to 32 million parameters. Bigger models are better, but the gains shrink quickly; see the results below.

**Trimming the vocabulary.** A tiny encoder spends most of its size on the vocabulary table: 30,522 entries, each with its own list of numbers. Memos use a small fraction of those. `tools/prune_vocab.py` keeps the 15,102 entries memos need and drops the rest. This made the smallest model about 40% smaller with no loss in accuracy.

**Quantisation.** Each of the model's numbers is normally stored as a 32-bit decimal number. Storing them as 8-bit whole numbers (**int8**) makes the file 4× smaller and faster to run, at the cost of a tiny loss of precision. For the BERT models the score barely moved. A newer encoder family (Ettin) lost 2 to 4 points when quantised, which is why it was dropped.

**ONNX.** The trained model is exported to ONNX, a standard file format that phone runtimes (ONNX Runtime on Android and iOS) can run without Python or PyTorch.

## 9. Teacher and student

The best way found to make the small model better was to let a bigger model teach it.

1. Train a bigger **teacher** model (MiniLM, 23 MB at int8) on the labelled data. It is too big for old phones but scores higher.
2. Let the teacher label the 30,000 extra unlabelled memos. Its labels are not as reliable as the agent-checked ones, so they are called **silver** data (the checked set is **gold**).
3. Train the small **student** on gold plus silver. In addition, at every token the student is also trained to match the teacher's full set of probabilities, not just its final answer. This is called **knowledge distillation**. "80% sure this is a date, 15% an event" carries more information than "date".

What happened:

- Distillation on gold data alone did not help.
- Adding silver data helped.
- Both together helped most: the 8 MB student reached 0.775 strict F1, almost the teacher's 0.783 at a third of the size.

## 10. Results

Scores on the 500 test memos, int8 models:

| Model | Size | Strict F1 | Reminders F1 | Fully right | Time per memo* |
| --- | --- | --- | --- | --- | --- |
| Tiny (vocab trimmed) | 2.9 MB | 0.674 | 0.521 | 24% | ~0.7 ms |
| Tiny (vocab trimmed, + silver + teacher) | 2.9 MB | 0.710 | 0.582 | 28% | ~0.7 ms |
| Mini (vocab trimmed) | 8.0 MB | 0.745 | 0.614 | 34% | ~1.3 ms |
| **Mini (vocab trimmed, + silver + teacher)** | **8.0 MB** | **0.775** | **0.653** | **36%** | **~1.3 ms** |
| MiniLM (the teacher) | 23.7 MB | 0.783 | 0.678 | 38% | ~2.7 ms |
| Two annotators vs each other | n/a | 0.918 | 0.864 | | |

\* one desktop CPU thread, a rough stand-in for one phone core. A real old phone will be several times slower; still well under a second.

How to read this:

- The 8 MB model is the recommended size: it is nearly as good as the teacher and fits comfortably on any phone.
- All of the tiny, mini and teacher models above get the six example memos from section 1 exactly right: the same reminders, dates, times and "please confirm" flags as the hand labels.
- On the harder test memos, even the best model gets every suggestion in a memo right only about a third of the time. Counted per reminder, the teacher gets 70% exactly right. The commonest miss is a slightly different title wording ("Check in with Tariq" instead of "Check in with Tariq about his Q4 client deck"), then a wrong or missing person, then a wrong date. That is why the app shows suggestions for you to review rather than saving them silently.
- People agreeing with each other score 0.918, so there is room to improve. Training on 25%, 50% and 100% of the data gave 0.679, 0.716 and 0.745, still rising, so **more labelled data is the clearest next step**.

## 11. The playground

`tools/serve.py` runs a small web page for trying models side by side. Type or pick a memo, choose models, and see each one's highlights and suggestions, with how long each took. Saved prompts are kept in `playground/prompts.json` so everyone tests against the same examples. Any newly trained model appears on the page automatically.

It was shared using Tailscale Funnel, which puts a local web server on a public HTTPS address and handles the certificate itself. Note that the page has no login, so anyone with the link can use it.

## 12. Checking the work

- **Tests.** 1,265 automated tests cover the rulebook's record format, the label alignment, decoding, the date resolver (with test cases written from its spec by separate agents), the suggestion rules and the web server.
- **A second opinion.** A different AI model (OpenAI's Codex) reviewed the whole codebase and found 14 real bugs, for example a person "belonging" to themselves through a loop of pointers, or a reminder swapping the wrong pronoun. Each was fixed with a test that failed before the fix.

## 13. What is next

The full list with details is in [handoff.md](handoff.md). In short: label the 30,000 extra memos properly and retrain, re-run the evaluations after the latest wording fixes, measure speed on a real old phone, and port the plain-code parts (date resolver, suggestion rules) from Python to the app's language.

## Glossary

| Term | Meaning |
| --- | --- |
| Model / weights / parameters | A function with millions of adjustable numbers, tuned on examples |
| Token / vocabulary | A piece of text the model sees / the fixed list of all pieces it knows |
| Encoder (BERT, MiniLM, Ettin) | A model that turns each token into numbers describing its meaning in context |
| Pretrained / fine-tuned | Trained by others on general text / then trained further on our task |
| Span | A highlighted piece of memo text |
| BIO tags | Begin / Inside / Outside labels that mark where spans start and continue |
| Head | A small extra output layer answering one question about a span |
| Owner / anchor | Pointers: who a span belongs to / which event a date times |
| Gold / silver data | Labels checked by two annotators and an adjudicator / labels from the teacher model |
| Distillation | Training a small model to imitate a bigger one's probabilities |
| Quantisation (int8) | Storing the numbers in 8 bits instead of 32 to make the model 4× smaller |
| ONNX | A portable model file format phones can run |
| Precision / recall / F1 | Share of answers that were right / share of right answers found / their balance |
| Train / dev / test | Data to learn from / to make choices with / to measure on once at the end |
| Epoch | One full pass over the training data |
