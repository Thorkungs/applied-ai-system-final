# AI Interactions Log

Two kinds of AI interaction are recorded here:

1. **Reasoning traces from VibeFinder's own agent**: the intermediate steps it took for real requests.
2. **How an AI coding assistant was used to build the project**: the task, what it did, and what had to be corrected.

---

## 1. Agent reasoning traces

Every request runs through the same loop: guardrail, interpret, plan, retrieve, score, self-check, revise if needed, verify, estimate confidence. Each step is recorded by `AgentResult.step()` in `src/agent.py` and written to `logs/vibefinder.log`.

The traces below were saved with the `--save-trace` flag and are also committed as [`assets/sample_runs/08_agent_traces.md`](assets/sample_runs/08_agent_traces.md). To add a new one:

```bash
python -m src.main "heading to the gym for leg day" --save-trace assets/sample_runs/08_agent_traces.md
```

The same steps as they appear in the log file are in [`assets/sample_runs/09_vibefinder_log_sample.txt`](assets/sample_runs/09_vibefinder_log_sample.txt), and terminal versions (the `--trace` flag) are in [`assets/sample_runs/03_self_check_and_revision.txt`](assets/sample_runs/03_self_check_and_revision.txt).

What to look for in each trace:

| Trace | What it shows |
| --- | --- |
| "heading to the gym for leg day" | Few-shot interpretation: no labels in the request, mood and energy come from the nearest example |
| "happy k-pop" | Tool use across two sources: the genre guide supplies neighbors for a genre the catalog does not have |
| "pop but really calm and low energy" | A full decision chain: score, self-check finds a conflict, revise, self-check again |
| "sad folk songs but high energy" | A revision that is rejected: no song fits, so the first ranking is kept and flagged |
| "my girlfriend broke up with me" | A failure: step 2 shows the wrong example being matched, and nothing later catches it |
| "what is the capital of France" | An early stop: nothing understood, nothing retrieved, the agent asks instead of answering |

### Request: "heading to the gym for leg day"

| # | Phase | Tool | What happened |
| --- | --- | --- | --- |
| 1 | guardrail | `check_request` | ok (30 chars) |
| 2 | act | `interpret_request` | mood=intense (few-shot 0.78) / energy=0.92 (few-shot 0.78) / nearest example: "music for the gym" (0.47) |
| 3 | plan | `make_plan` | 5 steps: look up the mood guide for 'intense' (neighbors, typical energy); search the song liner notes for the wording of the request; score all 20 songs and rank them; self-check the top results and re-rank if a stated preference was ignored; verify songs, citations and quotes before answering |
| 4 | act | `retrieve_knowledge` | moods.md#intense, song_notes.md#gym-hero (0.24), song_notes.md#rainy-day-blues (0.20), song_notes.md#island-time (0.11) |
| 5 | act | `score_catalog` | Gym Hero 2.96, Storm Runner 2.48, Iron Cathedral 1.93 |
| 6 | check | `self_check` | no issues |
| 7 | guardrail | `verify_output` | ok (3 songs in catalog, 2 citations checked) |
| 8 | act | `estimate_confidence` | 0.91 (high) |

**Final answer:** Gym Hero (2.96), Storm Runner (2.48), Iron Cathedral (1.93). Confidence 0.91 (high).

### Request: "happy k-pop"

| # | Phase | Tool | What happened |
| --- | --- | --- | --- |
| 1 | guardrail | `check_request` | ok (11 chars) |
| 2 | act | `interpret_request` | genre=k-pop (keyword) / mood=happy (keyword) |
| 3 | plan | `make_plan` | 7 steps: look up the genre guide for 'k-pop' (neighbors, typical energy); look up the mood guide for 'happy' (neighbors, typical energy); search the song liner notes for the wording of the request; no energy level stated, so take a typical energy from the guides; score all 20 songs and rank them; self-check the top results and re-rank if a stated preference was ignored; verify songs, citations and quotes before answering |
| 4 | act | `retrieve_knowledge` | genres.md#k-pop, moods.md#happy |
| 5 | act | `score_catalog` | Sunrise City 2.70, Laser Bloom 2.10, Rooftop Lights 1.74 |
| 6 | check | `self_check` | genre_unavailable |
| 7 | guardrail | `verify_output` | ok (3 songs in catalog, 6 citations checked) |
| 8 | act | `estimate_confidence` | 0.79 (medium) |

**Final answer:** Sunrise City (2.70), Laser Bloom (2.10), Rooftop Lights (1.74). Confidence 0.79 (medium).

> The catalog has no k-pop songs. Using the closest genres from the guide instead: pop, edm, hip hop.

### Request: "pop but really calm and low energy"

| # | Phase | Tool | What happened |
| --- | --- | --- | --- |
| 1 | guardrail | `check_request` | ok (34 chars) |
| 2 | act | `interpret_request` | genre=pop (keyword) / energy=0.30 (keyword) |
| 3 | plan | `make_plan` | 5 steps: look up the genre guide for 'pop' (neighbors, typical energy); search the song liner notes for the wording of the request; score all 20 songs and rank them; self-check the top results and re-rank if a stated preference was ignored; verify songs, citations and quotes before answering |
| 4 | act | `retrieve_knowledge` | genres.md#pop |
| 5 | act | `score_catalog` | Sunrise City 2.72, Gym Hero 2.56, Velvet Hours 2.17 |
| 6 | check | `self_check` | energy_conflict |
| 7 | revise | `rerank` | only songs within 0.30 of energy 0.30: Velvet Hours 2.17, Cabin Letters 1.50, Spacewalk Thoughts 1.47 |
| 8 | check | `self_check` | no issues after revision |
| 9 | guardrail | `verify_output` | ok (3 songs in catalog, 1 citations checked) |
| 10 | act | `estimate_confidence` | 0.75 (medium) |

**Final answer:** Velvet Hours (2.17), Cabin Letters (1.50), Spacewalk Thoughts (1.47). Confidence 0.75 (medium).

> My first ranking put Sunrise City (energy 0.82) on top although you asked for about 0.30, so I re-ranked using only songs near that energy.

### Request: "sad folk songs but high energy"

| # | Phase | Tool | What happened |
| --- | --- | --- | --- |
| 1 | guardrail | `check_request` | ok (30 chars) |
| 2 | act | `interpret_request` | genre=folk (keyword) / mood=sad (keyword) / energy=0.90 (keyword) |
| 3 | plan | `make_plan` | 6 steps: look up the genre guide for 'folk' (neighbors, typical energy); look up the mood guide for 'sad' (neighbors, typical energy); search the song liner notes for the wording of the request; score all 20 songs and rank them; self-check the top results and re-rank if a stated preference was ignored; verify songs, citations and quotes before answering |
| 4 | act | `retrieve_knowledge` | genres.md#folk, moods.md#sad |
| 5 | act | `score_catalog` | Cabin Letters 3.60, Rainy Day Blues 2.81, Dusty Back Roads 1.98 |
| 6 | check | `self_check` | energy_conflict |
| 7 | revise | `rerank` | no song near energy 0.90 fits the rest of the request and its stated labels (best was Night Drive Loop 1.77), keeping the first ranking |
| 8 | guardrail | `verify_output` | ok (3 songs in catalog, 2 citations checked) |
| 9 | act | `estimate_confidence` | 0.45 (low), flagged for human review |

**Final answer:** Cabin Letters (3.60), Rainy Day Blues (2.81), Dusty Back Roads (1.98). Confidence 0.45 (low).

> Nothing in the catalog is both sad folk and near energy 0.90. The top pick matches your labels but not the energy; the closest song by energy alone is Storm Runner (rock, intense, energy 0.91).

### Request: "my girlfriend broke up with me"

| # | Phase | Tool | What happened |
| --- | --- | --- | --- |
| 1 | guardrail | `check_request` | ok (30 chars) |
| 2 | act | `interpret_request` | mood=romantic (few-shot 0.65) / energy=0.50 (few-shot 0.65) / nearest example: "something for a candlelit evening with my girlfriend" (0.39) |
| 3 | plan | `make_plan` | 5 steps: look up the mood guide for 'romantic' (neighbors, typical energy); search the song liner notes for the wording of the request; score all 20 songs and rank them; self-check the top results and re-rank if a stated preference was ignored; verify songs, citations and quotes before answering |
| 4 | act | `retrieve_knowledge` | moods.md#romantic |
| 5 | act | `score_catalog` | Velvet Hours 2.47, Island Time 1.88, Coffee Shop Stories 1.80 |
| 6 | check | `self_check` | no issues |
| 7 | guardrail | `verify_output` | ok (3 songs in catalog, 2 citations checked) |
| 8 | act | `estimate_confidence` | 0.86 (high) |

**Final answer:** Velvet Hours (2.47), Island Time (1.88), Coffee Shop Stories (1.80). Confidence 0.86 (high).

### Request: "what is the capital of France"

| # | Phase | Tool | What happened |
| --- | --- | --- | --- |
| 1 | guardrail | `check_request` | ok (29 chars) |
| 2 | act | `interpret_request` | nothing I can score |
| 3 | plan | `make_plan` | 4 steps: search the song liner notes for the wording of the request; score all 20 songs and rank them; self-check the top results and re-rank if a stated preference was ignored; verify songs, citations and quotes before answering |
| 4 | act | `retrieve_knowledge` | nothing relevant found |
| 5 | check | `self_check` | no preference understood and no liner notes matched, asking the user |

**Final answer:** status `clarify`. I couldn't find a music preference in that. Tell me a genre, a mood, an energy level, or what you're doing, for example: 'chill lofi for studying' or 'something for the gym'.

---

## 2. Building the project with an AI coding assistant

**Tool:** Claude Code, in agent mode.

**Task given to the agent.** I pointed it at the final project page and asked it to look through everything from the course and build the project from the directions.

**What the agent did.**

- Read the project requirements and the grading rubric in the browser.
- Checked which earlier course projects I had (Game Glitch Investigator, PawPal+, Music Recommender), read the Music Recommender in full, and chose it as the base because its model card already listed specific weaknesses to fix.
- Cloned that repository into a new folder and added `assets/` and `diagrams/`.
- Wrote the knowledge base (`data/knowledge/`), the few-shot examples and the evaluation sets.
- Wrote the new modules in `src/`: `textutil.py`, `knowledge.py`, `retriever.py`, `interpreter.py`, `rag_scoring.py`, `guardrails.py`, `agent.py`, `report.py`, `evaluate.py`, and extended `main.py`. `recommender.py` was left unchanged.
- Wrote 67 new tests in `tests/`.
- Ran the system, the evaluation harness and the test suite repeatedly during the build, and committed the work in steps.
- Drafted the README, the model card, the architecture diagram and this file, pasting command output from real runs.

**What was verified, and how.**

- `pytest`: 74 tests pass, including the 7 from the original project.
- `python -m src.evaluate`: 23 of 24 predefined cases pass, against 13 of 24 with retrieval and few-shot switched off.
- The code was also run on the system Python 3.9 as well as 3.14, with the same results.
- The Mermaid diagram was rendered in a browser to confirm the source is valid.

**Corrections made during the build.** Each of these was found by running a concrete request and reading the output.

| What the first version did | How it showed up | What it was changed to |
| --- | --- | --- |
| Few-shot matching let weak neighbors outvote a strong one | "something for date night" was not understood, because two weak matches on "night" diluted the strong "date night" match | Ignore neighbors less than half as similar as the best one, and weight votes by similarity squared |
| Result lists were padded to k songs even when only one song earned points | The output guardrail failed verification with "has no explanation" for the padded songs | Songs that earn no points are no longer recommended, so a list can be shorter than k |
| The genre guide was searched with the whole request | For "pop but really calm and low energy" the extra words pulled up a different passage, so pop got no neighbors | Search the guide by the label alone, and only accept a passage whose heading is that label |
| The revision step re-ranked with energy doubled and genre halved | "pop but really calm" returned a lofi song and no pop | Re-rank only among songs within 0.30 of the requested energy, with the original weights |
| The revision was accepted whenever the new top pick scored well enough | "upbeat country for a road trip" was revised into a pop song, because a guessed mood outweighed the stated genre | A revision must keep every stated genre and mood, or a related one |
| An energy-only request reported confidence 1.00 | "upbeat music, anything but pop" looked certain although only one preference was understood | Confidence is scaled down when fewer than two of genre, mood and energy were understood |

**What was left out on purpose.** A language model for interpreting requests and writing answers. It would need an API key, cost money and could change its answer between runs, which works against a project that has to be reproducible from text evidence. See "Design decisions" in the README.
