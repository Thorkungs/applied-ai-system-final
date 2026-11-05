# 🎵 Music Recommender Simulation: VibeFinder 1.0

## Project Summary

VibeFinder 1.0 is a small, CLI first music recommender written in Python. It loads a 20 song catalog from `data/songs.csv`, compares every song to a user "taste profile" (favorite genre, favorite mood, target energy, and an optional acoustic preference), gives each song a weighted score, and prints the top 5 songs along with the exact reasons each song earned its points. The project also stress tests the scoring with normal and adversarial profiles, runs a weight shift experiment, and documents the biases that show up in a simple content based system.

---

## How The System Works

### How real platforms do it

Big platforms like Spotify and YouTube mix two families of techniques. **Collaborative filtering** looks at behavior across many users: if people who share your listening history also loved a track you have not heard, it gets recommended to you. It needs huge amounts of interaction data (plays, likes, skips, saves, playlist adds, replays) but no knowledge of what the music sounds like. **Content based filtering** looks at the attributes of the items themselves (genre, tempo, energy, mood, acousticness, audio embeddings, even lyrics) and recommends things that resemble what you already like. Real systems blend both, add context like time of day and device, and then rank candidates with large learned models.

### What my version prioritizes

VibeFinder is purely **content based** because it only has song attributes and one profile, with no other users to learn from. It prioritizes the things that most define a "vibe" in my experience: genre first, then mood, then how close the energy level is. Acousticness is an optional tie breaker for people who care about organic versus produced sound.

### Features used

`Song` features: `genre`, `mood`, `energy` (0.0 to 1.0), `acousticness` (0.0 to 1.0). The catalog also stores `tempo_bpm`, `valence`, and `danceability`, which are loaded but not scored in version 1.0.

`UserProfile` features: `favorite_genre`, `favorite_mood`, `target_energy`, `likes_acoustic`.

### Algorithm Recipe (Scoring Rule for one song)

| Rule | Points |
| --- | --- |
| Genre matches exactly | +2.0 |
| Mood matches exactly | +1.0 |
| Energy closeness | +1.5 × (1 − abs(song energy − target energy)) |
| Acoustic fit (only if the profile sets `likes_acoustic`) | +0.5 × acousticness if True, +0.5 × (1 − acousticness) if False |

Maximum possible score is 5.0. Energy uses closeness instead of "higher is better", so a chill listener with a target of 0.35 is rewarded for a 0.35 song and penalized for a 0.95 song.

### Ranking Rule (for the whole list)

We need both rules. The Scoring Rule judges one song in isolation, but a recommendation is a comparison, so the Ranking Rule runs the scorer on every song in the catalog, sorts by score from highest to lowest (ties broken alphabetically by title so results are repeatable), and returns the top k. `sorted()` is used instead of `.sort()` because it returns a new list and leaves the original catalog order untouched.

### Data flow

```
Input: user prefs (genre, mood, energy, likes_acoustic)
   |
   v
Process: for each of the 20 songs in songs.csv -> score_song() -> (score, reasons)
   |
   v
Output: sort by score, take top k -> print title, score, and reasons
```

### Expected biases (written before testing)

I expected the system to over prioritize genre, since a genre match alone (2.0) is worth more than a perfect mood plus energy match combined in most cases. That means great songs that fit the user's mood and energy but have a different genre label could get buried. Exact string matching also means near neighbors like "indie pop" and "pop" are treated as completely different.

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows
   ```

2. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

3. Run the app:

   ```bash
   python -m src.main                       # default pop/happy profile
   python -m src.main --all                 # all 7 profiles
   python -m src.main --profile chill_lofi  # one profile
   python -m src.main --all --experiment    # energy x2, genre x0.5
   ```

### Running Tests

```bash
pytest
```

7 tests cover CSV loading and type conversion, the score and reasons output, energy closeness, sorted top k ranking, and the effect of custom weights.

---

## Sample Recommendation Output

Default "pop/happy" profile (`python -m src.main`):

```
Loaded songs: 20
Weights: {'genre': 2.0, 'mood': 1.0, 'energy': 1.5, 'acoustic': 0.5}

========================================================================
Profile: default_pop_happy
Prefs:   genre=pop, mood=happy, energy=0.8
------------------------------------------------------------------------
1. Sunrise City by Neon Echo [pop, happy]  score 4.47
     - genre match: pop (+2.00)
     - mood match: happy (+1.00)
     - energy 0.82 vs target 0.80 (+1.47)
2. Gym Hero by Max Pulse [pop, intense]  score 3.31
     - genre match: pop (+2.00)
     - energy 0.93 vs target 0.80 (+1.30)
3. Rooftop Lights by Indigo Parade [indie pop, happy]  score 2.44
     - mood match: happy (+1.00)
     - energy 0.76 vs target 0.80 (+1.44)
4. Concrete Crown by Block Theory [hip hop, confident]  score 1.47
     - energy 0.78 vs target 0.80 (+1.47)
5. Night Drive Loop by Neon Echo [synthwave, moody]  score 1.43
     - energy 0.75 vs target 0.80 (+1.42)
```

Output for every profile is in [model_card.md](model_card.md#7-evaluation).

---

## Experiments You Tried

**Weight shift:** doubled energy (1.5 to 3.0) and halved genre (2.0 to 1.0) with `--experiment`.

* Default pop/happy: Rooftop Lights (indie pop, happy) jumped from #3 to #2 and pushed Gym Hero (pop, intense) to #3. This felt **more accurate**, because a happy indie pop song really is a better fit for a happy pop listener than an intense workout track.
* High energy pop: Storm Runner (rock) moved above Sunrise City (pop). Different, not clearly better.
* Conflicted sad but hyped: the gap between the slow folk song and loud high energy songs shrank from 2.1 points to 0.2 points, so the system started to "hear" the energy request.
* Chill lofi barely changed, because the lofi songs already matched on every feature.

Overall the experiment showed the default genre weight is doing most of the work, and lowering it makes the system notice songs that cross genre labels.

---

## Limitations and Risks

* Tiny 20 song catalog, so the same handful of songs (Gym Hero, Storm Runner) show up across many profiles.
* Exact genre and mood matching: "indie pop" earns zero genre points for a "pop" fan, and "intense" earns nothing for an "energetic" fan.
* Genre weight dominates, so a genre match on a bad energy fit can beat a perfect energy fit in another genre.
* No lyrics, language, artist familiarity, listening history, or context (time of day, activity).
* Tempo, valence, and danceability are in the data but unused.
* Users whose genre is not in the catalog (for example k-pop) can never earn the largest bonus.

More detail is in the model card.

---

## Reflection

Read the full model card and personal reflection: [**Model Card**](model_card.md)

Building VibeFinder made it clear that a recommender is really just two decisions stacked together: how you turn features into a number for one item, and how you rank all the numbers. Everything that feels like "taste" comes from the weights. When genre was worth 2.0 points, the system acted like a genre purist; when I cut it in half, it started behaving more like someone who cares about vibe. Nothing about the code got smarter, only the priorities changed.

Bias showed up in places I did not expect from such simple code. The catalog decides who gets served well: a lofi fan has three lofi songs to choose from, while a k-pop fan has zero and can never get the biggest bonus. Exact label matching quietly punishes songs with hyphenated or niche genre tags. In a real product with millions of users, those small choices would decide which artists get exposure and which listeners keep getting pushed toward the same mainstream tracks.
