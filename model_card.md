# 🎧 Model Card: VibeFinder 2.0

Final project for CodePath AI110. This card covers what the system is, how it was tested, where it fails, how it could be misused, what was surprising, and how AI tools were used to build it. Setup, sample runs and the evaluation output are in the [README](README.md).

---

## 1. System overview

**Name:** VibeFinder 2.0, an explainable music recommender agent.

**Base project:** VibeFinder 1.0, my Module 3 Music Recommender Simulation ([original repo](https://github.com/Thorkungs/ai110-module3show-musicrecommendersimulation-starter)). Version 1.0 scored 20 songs against a hard-coded taste profile with a weighted recipe and printed the top 5 with reasons. Its scoring code is still here, unchanged, in `src/recommender.py`.

**What 2.0 adds:** it takes a request in plain English, interprets it, retrieves knowledge about the genre, the mood and the songs, ranks the catalog using that knowledge, checks and sometimes revises its own answer, verifies the output, and reports a confidence score.

There is no neural network or language model in this system. The "AI" parts are:

| Component | Technique | File |
| --- | --- | --- |
| Interpreter | Keyword rules, then nearest-example matching over 41 labeled requests (TF-IDF similarity) | `src/interpreter.py` |
| Retriever | TF-IDF cosine similarity over 56 knowledge passages | `src/retriever.py` |
| Scorer | The 1.0 weighted recipe plus points derived from retrieved passages | `src/rag_scoring.py` |
| Agent | A fixed plan, act, check, revise loop with a recorded trace | `src/agent.py` |
| Guardrails and confidence | Rule-based checks and a weighted formula | `src/guardrails.py`, `src/agent.py` |

---

## 2. Intended use

VibeFinder suggests up to 10 songs from a 20 song catalog for one request such as "chill lofi for studying" or "something for date night", and explains each pick with its score, its reasons and the sources it used.

It is built for **classroom exploration** of retrieval, agent loops, guardrails and evaluation. It is a good way to see how those pieces fit together because every step is visible and repeatable.

**Not intended for:** a real music product, real users, deciding which artists get promoted or paid, or any kind of emotional support. The crisis message is a safety net for a demo, not a mental health feature.

---

## 3. How it works, in plain language

1. **Check the request.** Empty, very long or wordless requests are turned away. If the request contains crisis language, the system answers with a support message and does not build a playlist.
2. **Work out what was asked.** First it looks for words it knows: genre names, mood names, energy words like "upbeat" or "calm", and negations like "anything but pop". If the request describes a situation instead ("heading to the gym"), it finds the most similar requests in a list of 41 labeled examples and borrows their mood and energy. If those examples disagree with each other, it does not guess.
3. **Make a plan.** It lists which lookups this request needs.
4. **Look things up.** It searches three documents: a genre guide, a mood guide and a set of liner notes with one short note per song.
5. **Score every song.** It starts with the 1.0 recipe (genre +2, mood +1, energy closeness up to +1.5, acoustic fit up to +0.5). Then the retrieved knowledge adds to it: a song in a related genre or mood gets half credit, a typical energy from the guide is used if the listener gave none, and a song whose liner note matches the wording of the request gets up to +1.
6. **Check its own answer.** If the top song is far from the energy that was asked for, it tries again using only songs near that energy. It keeps the new ranking only if the new top song still matches the labels the listener stated. If nothing fits, it says so.
7. **Verify before showing.** Every song must be in the catalog, every cited source must be one that was really retrieved, and every quote must really appear in that source. If anything fails, it falls back to the simple 1.0 ranking and says so.
8. **Report confidence.** A number from 0 to 1 built from how much of the request was understood, how well the top song fits, and whether the self-check found problems. Low confidence answers are marked for human review.

---

## 4. Data

Everything is in the repository, and all of it is synthetic.

| Data | Size | Where it came from |
| --- | --- | --- |
| Song catalog (`data/songs.csv`) | 20 songs, 17 genres, 14 moods | Carried over from 1.0. The songs and their feature values are made up. |
| Knowledge base (`data/knowledge/`) | 56 passages: 22 genre notes, 14 mood notes, 20 song liner notes | Written for this project with AI assistance. Not taken from any published source. |
| Few-shot examples (`data/few_shot_examples.json`) | 41 labeled requests | Written for this project with AI assistance. |
| Agent evaluation cases (`data/eval/agent_cases.json`) | 24 requests with expectations | Written for this project. |
| Interpreter development set | 34 requests | Written before tuning and used while tuning thresholds. |
| Interpreter held-out set | 24 requests | Written after tuning and never tuned against. |

Because there is no real listening data, nothing here says whether a recommendation is one a real person would enjoy. The evaluation measures whether the system does what it was designed to do.

---

## 5. Testing results

Run `python -m src.evaluate` and `pytest` to reproduce every number below. Full output is in the README and in `assets/sample_runs/`.

| Measure | Result |
| --- | --- |
| Agent cases passed, full system | 23 of 24 (96%) |
| Agent cases passed with retrieval and few-shot switched off | 13 of 24 (54%) |
| Guardrail cases passed | 5 of 5 |
| Interpreter accuracy, development set | 26% with keywords only, 82% with few-shot |
| Interpreter accuracy, held-out set | 29% with keywords only, 58% with few-shot |
| Held-out misses with few-shot | 10 of 24: 8 abstentions, 2 wrong guesses |
| Average confidence when songs were returned | 0.83 (passing cases 0.82, the one failing case 0.86) |
| Answers that failed output verification | 0 of 24 |
| Automated tests | 74 of 74 pass |

Agent cases, one row each:

| Input | Evaluation criteria | Result |
| --- | --- | --- |
| "happy pop songs" | Top pick is Sunrise City, confidence at least 0.8 | Pass |
| "intense rock, high energy" | Top pick is Storm Runner, confidence at least 0.8 | Pass |
| "chill lofi" | Top pick is lofi and chill | Pass |
| "confident hip hop" | Top pick is Concrete Crown | Pass |
| "happy pop songs" | Rooftop Lights ranks above Gym Hero, with a cited source | Pass |
| "happy k-pop" | Top pick is Sunrise City or Rooftop Lights, missing genre is reported, source cited | Pass |
| "punk" | Top pick is Storm Runner or Iron Cathedral, missing genre is reported, source cited | Pass |
| "sad folk songs but high energy" | Flagged for review, energy conflict reported, confidence at most 0.5 | Pass |
| "pop but really calm and low energy" | Ranking is revised, top pick energy at most 0.6, source cited | Pass |
| "heading to the gym for leg day" | Top pick is Gym Hero or Storm Runner, energy at least 0.85 | Pass |
| "help me fall asleep" | Top pick energy at most 0.4, Spacewalk Thoughts in the results | Pass |
| "something for date night" | Top pick is Velvet Hours | Pass |
| "jazz for sunday morning coffee" | Top pick is Coffee Shop Stories, source cited | Pass |
| "studying for finals all night" | Top pick is Focus Flow, Midnight Coding or Library Rain | Pass |
| "rainy afternoon reading" | Top pick is Library Rain, source cited | Pass |
| "my girlfriend broke up with me" | Top pick is a sad song | **Fail**: returned Velvet Hours (romantic) at 0.86 confidence |
| "pumping iron" | Top pick is Gym Hero, Storm Runner or Iron Cathedral | Pass (by a title word match, at 0.43 confidence, flagged for review) |
| "upbeat music, anything but pop" | No pop songs, top pick energy at least 0.7 | Pass |
| "something relaxed, no jazz" | No jazz songs, top pick is relaxed | Pass |
| "" (empty) | Rejected | Pass |
| "?!?!?! 12345" | Rejected | Pass |
| A 323 character request | Rejected | Pass |
| "what is the capital of France" | Asks for clarification, returns no songs | Pass |
| "I want to die, play something sad" | Support message, returns no songs | Pass |

---

## 6. Limitations and biases

**It only understands words it has seen.** Both the interpreter and the retriever match on shared words. "Pumping iron", "she left me" and "cramming for an exam" share no words with any example, so the interpreter understands nothing. Worse, a shared word can point the wrong way: "my girlfriend broke up with me" matches a date night example through the word "girlfriend" and gets romantic songs.

**Word overlap creates noise.** "Heading to the gym for leg day" retrieved the liner note for Rainy Day Blues, only because both contain the word "day". It did not change the top 3 that time, but it could.

**The catalog decides who is served well.** This bias is inherited from 1.0. Lofi has 3 songs, pop has 2, and every other genre has 1. A rock fan gets one rock song and then "loud things". Retrieval softens this by giving neighbors partial credit, but it cannot add songs that are not there.

**The knowledge base is one view of music.** The genre guide decides that k-pop is "close to" pop, edm and hip hop, and that folk is close to country and blues. Those are judgment calls made by whoever wrote the file. The genre list is Western and English-language heavy. A request for a genre the guide does not mention (gospel, Bollywood, amapiano) gets no neighbor credit at all, so those listeners are served worse.

**The examples carry assumptions about people.** The few-shot data assumes a breakup means you want sad songs and the gym means you want intense ones. Some people want the opposite. Several relationship examples are also written around "girlfriend", "her" and "wife", which is a narrow picture of who is asking.

**Confidence is not calibrated.** The score measures how well the songs fit what the system thinks was asked. It has no way to know the interpretation was wrong, so its one wrong answer in the evaluation scored higher than the average right answer.

**The numbers are optimistic.** The examples, the knowledge base and the test cases were all written by the same author with the same AI assistant. The gap between the development set (82%) and the held-out set (58%) shows how much the tuning fit the wording it had seen. Real users would phrase things in ways neither set covers.

**Thresholds are hand-set.** The 0.30 energy gap, the 0.5 weak-fit line and the confidence weights were chosen by reasoning and by looking at a few cases. None were learned from data.

**English only**, and still purely content-based: no listening history, no other users.

---

## 7. Misuse and how to prevent it

**Steering recommendations by editing the knowledge base.** Retrieved text changes scores. Anyone who can edit `data/knowledge/` could add their own song's genre to every `related:` list, or stuff a liner note with common request words, and push that song up the rankings. This is the small-scale version of paying for placement. Mitigations in place: the files are in version control so changes are visible, a test checks that every `related:` label is a real catalog label, and every boost is shown to the user with its source and a quote, so a suspicious boost can be traced. What a real system would also need: review of knowledge base changes, and a cap on how much any one passage can add.

**Treating the confidence score as truth.** Someone could use "confidence 0.86" to claim the system is right. The evaluation shows it can be confidently wrong. The README and this card say so directly, and the output says "please review" on low-confidence answers. A real product should not show a raw number without calibration.

**Reading emotions from requests.** Requests reveal mood and life events ("just got dumped", "can't sleep"), and the log file stores them in plain text. Here the log stays on the user's own machine and is excluded from git. A deployed version should not store raw requests, or should delete them quickly, and should never use them to profile people.

**Relying on the crisis check.** It is a short keyword list. It will miss most ways of saying the same thing, and it will also trigger on a request for a song whose title contains one of the phrases. It exists so that the worst-case input gets a humane answer and a real phone number in a demo. It should never be described as a safety system.

**Prompt injection, if a language model is added later.** Today there is no model to hijack: user text and retrieved text are only matched and quoted, never followed as instructions. If an LLM is added to write the answers, both the request and the knowledge base passages would have to be treated as untrusted input, and the output guardrail that checks songs, citations and quotes would matter even more.

---

## 8. What surprised me while testing reliability

**The system was most confident when it was wrong.** A wrong answer would be expected to come with low confidence. Instead, "my girlfriend broke up with me" returned romantic songs at 0.86, higher than the 0.82 average of the cases that passed. Looking at the formula explains it: confidence rewards a good fit to the interpretation, and the fit to "romantic" was excellent. The formula never questions the interpretation itself. This was the most useful thing the evaluation found.

**The output guardrail caught a development bug before it caught anything hostile.** Guardrails are usually described as protection against bad input. The first thing `verify_output` actually stopped was a development bug: when only one song earned points, the list was padded with zero-score songs that had no explanation. Verification failed with "has no explanation" and the system fell back as designed. The fix was to stop recommending songs that earned nothing.

**The held-out number was much lower than the development number.** Few-shot accuracy was 82% on the requests the thresholds were tuned against and 58% on requests written afterwards. On its own, 82% looked like the result. The held-out set showed that part of it was the tuning fitting the wording of the examples.

**Fixing a problem can create a worse one.** The first revision step re-ranked with energy counting double. For "pop but really calm" it returned lofi and no pop at all. The replacement (only consider songs near the requested energy) fixed that case, and then turned "upbeat country for a road trip" into a pop song because a guessed mood outweighed the stated genre. It took a third rule, that a revision must keep the labels the listener stated, before both cases behaved.

**Abstaining turned out to be the main failure mode, and that is the better one.** Of the 10 held-out requests the interpreter got wrong, 8 were "I don't understand" and only 2 were wrong guesses. A system that says it does not know is much easier to live with than one that guesses.

---

## 9. Collaboration with AI during this project

**How AI was used.** This project was built with Claude Code working in agent mode. I gave it the assignment page and asked it to look through my course work and build the final project from the directions. It read the requirements and the grading rubric, checked my earlier course projects, proposed extending VibeFinder because its model card already listed concrete weaknesses, and then wrote the modules, the knowledge base, the examples, the tests and the first draft of this documentation. It ran the evaluation harness and the test suite repeatedly during the build, and every output pasted in the README came from real runs.

**A suggestion that was accepted: abstain when the examples disagree.** The first test of the few-shot matcher showed it copying the mood of whichever example shared a word, even a weak one. "Need something for my morning run" tied between a running example and a "sunday morning coffee" example. Claude's suggestion was to make the interpreter give up when the nearest examples do not agree on a mood, and to let a mood the listener stated outright always win over a guessed one. This was kept. It is the reason wrong guesses are rare (2 of 24 on the held-out set): the system says "I don't understand" before it guesses.

**A suggestion that was not accepted as written: revising by re-weighting.** Claude's first version of the revision step reused the weight experiment from 1.0. When the top pick ignored the requested energy, it re-ranked everything with energy doubled and genre halved. Running "pop but really calm and low energy" showed the problem: the answer was a lofi song with no connection to pop, so the fix for ignoring one preference was to ignore another. That version was replaced with a narrower rule (re-rank only among songs near the requested energy, keep the original weights), and later tightened again so that a revision must keep the labels the listener stated.

**A second one that was left out: a language model layer.** An LLM to interpret requests and write the answers was considered early on. It was left out because the project is graded from text evidence that someone else must be able to reproduce, and a model call needs an API key, costs money and can change its answer between runs. The cost of that decision is visible in the evaluation (the system cannot understand "pumping iron"), and it is listed first under future work.

**Where AI output needed checking.** Three of the corrections above (the zero-score padding, the overshooting revision, the revision that dropped a stated genre) were bugs in code the AI had written minutes earlier. Each one was found by running the system on a concrete request and reading the output, not by reading the code. AI-written code needs the same thing human-written code needs: a harness that runs real inputs and a person who reads the results.

---

## 10. Specialization: keyword baseline vs few-shot interpreter

The few-shot stage is the specialized part of the system: 41 labeled examples that teach it how people describe situations. The baseline is the keyword stage alone, which only understands labels that literally appear.

A request counts as correct only if every expected slot (genre, mood, energy within 0.15, acoustic preference) is right and no genre is invented.

| Request set | Keyword baseline | With few-shot |
| --- | --- | --- |
| Development: explicit labels (8) | 8 of 8 | 8 of 8 |
| Development: situational (20) | 0 of 20 | 18 of 20 |
| Development: no shared words (4) | 0 of 4 | 0 of 4 |
| Development: mixed (2) | 1 of 2 | 2 of 2 |
| **Development total (34)** | **9 of 34 (26%)** | **28 of 34 (82%)** |
| Held-out: explicit labels (6) | 6 of 6 | 6 of 6 |
| Held-out: situational (18) | 1 of 18 | 8 of 18 |
| **Held-out total (24)** | **7 of 24 (29%)** | **14 of 24 (58%)** |

The same difference on individual requests, and what it does to the final answer:

| Request | Keyword baseline understood | Few-shot understood | Baseline top pick | Full system top pick |
| --- | --- | --- | --- | --- |
| "heading to the gym for leg day" | nothing | mood=intense, energy=0.92 | (asks for clarification) | Gym Hero |
| "something for date night" | nothing | mood=romantic, energy=0.50 | (asks for clarification) | Velvet Hours |
| "studying for finals all night" | nothing | mood=focused, energy=0.40 | (asks for clarification) | Focus Flow |
| "I need a good cry" | nothing | mood=sad, energy=0.30 | (asks for clarification) | Cabin Letters |
| "trying to sleep" | nothing | nothing (abstained) | (asks for clarification) | (asks for clarification) |
| "my girlfriend broke up with me" | nothing | mood=romantic, energy=0.50 (**wrong**) | (asks for clarification) | Velvet Hours (**wrong**) |
| "I'm so mad at my boss" | nothing | mood=confident, energy=0.80 (**wrong**) | (asks for clarification) | Concrete Crown (**wrong**) |

The last two rows matter as much as the first four. The baseline never gives a wrong answer to a situational request because it never gives any answer. The specialized interpreter answers many more requests correctly and also introduces a new kind of error.

---

## 11. Future improvements

1. **Use a language model to interpret requests**, with the current keyword and few-shot path as the fallback when no API key is set. Keep the output guardrail in front of anything the model writes.
2. **Replace word matching with embeddings** for both the examples and the knowledge base, so "pumping iron" lands near "gym".
3. **Make confidence account for interpretation risk.** Lower it when the nearest example matched on a single word, or when the keyword stage and the few-shot stage point in different directions.
4. **Collect real judgments.** Have other people rate the top pick for 30 or so requests and compare those ratings with the confidence score.
5. **Add a diversity rule** so one artist or genre cannot fill the list, which was already on the 1.0 list.
6. **Grow the catalog and the guide** beyond 20 songs and 22 genres, with attention to which listeners are currently left out.
