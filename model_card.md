# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

**VibeFinder 1.0**

---

## 2. Intended Use

VibeFinder suggests the top 5 songs from a small catalog that best match one listener's stated taste: a favorite genre, a favorite mood, a target energy level, and optionally whether they like acoustic sound.

It assumes the user can describe their taste in those few words and that the taste is stable (it does not change with time of day or activity). It is built for **classroom exploration** of how recommenders turn data into ranked predictions. It is not meant for real users.

**Not intended for:** a production music app, recommending to people whose taste does not fit one genre label, making decisions about which artists get paid or promoted, or any setting where fairness to artists matters.

---

## 3. How the Model Works

Think of VibeFinder as a judge giving each song points on a scorecard.

* If the song's genre is exactly the listener's favorite genre, it gets 2 points.
* If the song's mood is exactly the listener's favorite mood, it gets 1 point.
* For energy, it gets up to 1.5 points depending on how *close* the song's energy is to what the listener wants. A perfect match gets all 1.5; a song that is way too loud or way too sleepy gets very few.
* If the listener said whether they like acoustic sound, songs that fit that preference get up to half a point more.

The judge scores every song in the catalog, lines them up from highest to lowest, and hands back the top 5. Each recommendation comes with its reasons, like "genre match: pop (+2.00)", so the listener can see why it was picked.

**Changes from the starter:** I implemented all the empty functions, added the closeness based energy score and the optional acoustic bonus, made the weights adjustable so experiments are one flag away, added a tie breaker by title so results are repeatable, and fixed the starter `main.py` import so `python -m src.main` actually runs.

---

## 4. Data

The catalog has **20 songs** in `data/songs.csv`. The starter had 10; I added 10 more to cover genres and moods that were missing.

* **Genres (17):** pop, lofi, rock, ambient, jazz, synthwave, indie pop, hip hop, metal, classical, country, edm, r&b, folk, reggae, blues, latin. Lofi has 3 songs and pop has 2; every other genre has 1.
* **Moods (14):** happy, chill, intense, relaxed, moody, focused, confident, angry, melancholy, nostalgic, euphoric, romantic, sad, energetic.
* **Numeric features:** energy, tempo_bpm, valence, danceability, acousticness (all 0 to 1 except tempo).

**What is missing:** lyrics and language, artist popularity, release year, any listening history, and most of the world's genres (no k-pop, afrobeats, gospel, punk, and so on). The songs and their feature values are made up, so there is no ground truth for what a "correct" recommendation is.

---

## 5. Strengths

* **Clear single genre listeners are served well.** The chill lofi, deep intense rock, and high energy pop profiles all got a top pick that matched every feature (scores of 4.93 out of 5).
* **Energy closeness works the way I hoped.** The chill lofi listener got slow, quiet songs from other genres (Spacewalk Thoughts, Coffee Shop Stories) instead of anything loud.
* **Explanations are transparent.** Every score is fully explained by its reasons, so it is easy to see why a song ranked where it did.

---

## 6. Limitations and Bias

The biggest weakness I found is that **the genre weight creates a filter bubble around exact genre labels.** A genre match is worth 2 points, which is more than a perfect energy match (1.5), so a song in the "right" genre can beat a better fitting song from a neighboring genre. For the default pop/happy profile, Gym Hero (pop, intense) ranked #2 over Rooftop Lights (indie pop, happy), even though Rooftop Lights matches the listener's mood and is closer in energy, simply because the label "indie pop" does not exactly equal "pop". The catalog makes this worse: lofi has 3 songs while most genres have 1, so lofi fans get a full page of on genre picks while a jazz or folk fan gets one genre match and then filler. Listeners whose genre is not in the catalog at all (the k-pop profile) can never earn the largest bonus, so the system quietly serves them worse. Mood matching has the same exact string problem: "energetic" and "intense" are treated as totally unrelated.

---

## 7. Evaluation

I tested **7 profiles**: the starter pop/happy profile, three normal listeners (high energy pop, chill lofi, deep intense rock), and three adversarial ones designed to trick the scoring (a folk fan who wants sad songs at 0.9 energy, a k-pop fan, and a profile that only sets energy 0.5). For each, I checked whether the top 5 "felt" right for that listener and looked for songs that kept showing up everywhere.

### Profile outputs (default weights)

```
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
```
Profile: high_energy_pop
Prefs:   genre=pop, mood=intense, energy=0.9, likes_acoustic=False
------------------------------------------------------------------------
1. Gym Hero by Max Pulse [pop, intense]  score 4.93
     - genre match: pop (+2.00)
     - mood match: intense (+1.00)
     - energy 0.93 vs target 0.90 (+1.46)
     - produced/electronic feel 0.95 (+0.47)
2. Sunrise City by Neon Echo [pop, happy]  score 3.79
     - genre match: pop (+2.00)
     - energy 0.82 vs target 0.90 (+1.38)
     - produced/electronic feel 0.82 (+0.41)
3. Storm Runner by Voltline [rock, intense]  score 2.94
     - mood match: intense (+1.00)
     - energy 0.91 vs target 0.90 (+1.48)
     - produced/electronic feel 0.90 (+0.45)
4. Laser Bloom by Pulse Garden [edm, euphoric]  score 1.91
     - energy 0.95 vs target 0.90 (+1.43)
     - produced/electronic feel 0.96 (+0.48)
5. Iron Cathedral by Black Anvil [metal, angry]  score 1.88
     - energy 0.97 vs target 0.90 (+1.40)
     - produced/electronic feel 0.97 (+0.48)

```
```
Profile: chill_lofi
Prefs:   genre=lofi, mood=chill, energy=0.35, likes_acoustic=True
------------------------------------------------------------------------
1. Library Rain by Paper Lanterns [lofi, chill]  score 4.93
     - genre match: lofi (+2.00)
     - mood match: chill (+1.00)
     - energy 0.35 vs target 0.35 (+1.50)
     - acoustic feel 0.86 (+0.43)
2. Midnight Coding by LoRoom [lofi, chill]  score 4.75
     - genre match: lofi (+2.00)
     - mood match: chill (+1.00)
     - energy 0.42 vs target 0.35 (+1.40)
     - acoustic feel 0.71 (+0.35)
3. Focus Flow by LoRoom [lofi, focused]  score 3.81
     - genre match: lofi (+2.00)
     - energy 0.40 vs target 0.35 (+1.42)
     - acoustic feel 0.78 (+0.39)
4. Spacewalk Thoughts by Orbit Bloom [ambient, chill]  score 2.85
     - mood match: chill (+1.00)
     - energy 0.28 vs target 0.35 (+1.40)
     - acoustic feel 0.92 (+0.46)
5. Coffee Shop Stories by Slow Stereo [jazz, relaxed]  score 1.92
     - energy 0.37 vs target 0.35 (+1.47)
     - acoustic feel 0.89 (+0.45)

```
```
Profile: deep_intense_rock
Prefs:   genre=rock, mood=intense, energy=0.92, likes_acoustic=False
------------------------------------------------------------------------
1. Storm Runner by Voltline [rock, intense]  score 4.93
     - genre match: rock (+2.00)
     - mood match: intense (+1.00)
     - energy 0.91 vs target 0.92 (+1.48)
     - produced/electronic feel 0.90 (+0.45)
2. Gym Hero by Max Pulse [pop, intense]  score 2.96
     - mood match: intense (+1.00)
     - energy 0.93 vs target 0.92 (+1.48)
     - produced/electronic feel 0.95 (+0.47)
3. Laser Bloom by Pulse Garden [edm, euphoric]  score 1.94
     - energy 0.95 vs target 0.92 (+1.46)
     - produced/electronic feel 0.96 (+0.48)
4. Iron Cathedral by Black Anvil [metal, angry]  score 1.91
     - energy 0.97 vs target 0.92 (+1.43)
     - produced/electronic feel 0.97 (+0.48)
5. Fuego Nocturno by Los Brillantes [latin, energetic]  score 1.81
     - energy 0.86 vs target 0.92 (+1.41)
     - produced/electronic feel 0.80 (+0.40)

```
```
Profile: conflicted_sad_but_hyped
Prefs:   genre=folk, mood=sad, energy=0.9
------------------------------------------------------------------------
1. Cabin Letters by Willow & Pine [folk, sad]  score 3.60
     - genre match: folk (+2.00)
     - mood match: sad (+1.00)
     - energy 0.30 vs target 0.90 (+0.60)
2. Rainy Day Blues by Delta Mae [blues, sad]  score 1.81
     - mood match: sad (+1.00)
     - energy 0.44 vs target 0.90 (+0.81)
3. Storm Runner by Voltline [rock, intense]  score 1.49
     - energy 0.91 vs target 0.90 (+1.48)
4. Gym Hero by Max Pulse [pop, intense]  score 1.46
     - energy 0.93 vs target 0.90 (+1.46)
5. Fuego Nocturno by Los Brillantes [latin, energetic]  score 1.44
     - energy 0.86 vs target 0.90 (+1.44)

```
```
Profile: genre_not_in_catalog
Prefs:   genre=k-pop, mood=happy, energy=0.7
------------------------------------------------------------------------
1. Rooftop Lights by Indigo Parade [indie pop, happy]  score 2.41
     - mood match: happy (+1.00)
     - energy 0.76 vs target 0.70 (+1.41)
2. Sunrise City by Neon Echo [pop, happy]  score 2.32
     - mood match: happy (+1.00)
     - energy 0.82 vs target 0.70 (+1.32)
3. Night Drive Loop by Neon Echo [synthwave, moody]  score 1.43
     - energy 0.75 vs target 0.70 (+1.42)
4. Concrete Crown by Block Theory [hip hop, confident]  score 1.38
     - energy 0.78 vs target 0.70 (+1.38)
5. Island Time by Sunset Sound System [reggae, relaxed]  score 1.32
     - energy 0.58 vs target 0.70 (+1.32)

```
```
Profile: middle_of_everything
Prefs:   energy=0.5
------------------------------------------------------------------------
1. Velvet Hours by Amara Lux [r&b, romantic]  score 1.47
     - energy 0.52 vs target 0.50 (+1.47)
2. Dusty Back Roads by Tumbleweed Kings [country, nostalgic]  score 1.43
     - energy 0.55 vs target 0.50 (+1.42)
3. Rainy Day Blues by Delta Mae [blues, sad]  score 1.41
     - energy 0.44 vs target 0.50 (+1.41)
4. Island Time by Sunset Sound System [reggae, relaxed]  score 1.38
     - energy 0.58 vs target 0.50 (+1.38)
5. Midnight Coding by LoRoom [lofi, chill]  score 1.38
     - energy 0.42 vs target 0.50 (+1.38)

```

### Comparing profiles

* **Default pop/happy vs high energy pop:** both start with pop songs, but swapping the mood from happy to intense and raising energy to 0.9 flips the top two: Gym Hero takes #1 and Sunrise City drops to #2. Storm Runner (rock) appears only for the intense version, because it matches the mood. This makes sense; the mood is the only thing that changed between them.
* **High energy pop vs chill lofi:** there is zero overlap. Pop picks all sit at 0.8 to 0.97 energy with low acousticness, while lofi picks sit at 0.28 to 0.42 energy with high acousticness. The energy closeness and acoustic preference pull them to opposite ends of the catalog, which is exactly what should happen.
* **Chill lofi vs deep intense rock:** again no overlap. The rock fan's list after Storm Runner is filled with loud songs from other genres (edm, metal, latin) because rock only has one song. This shows the catalog size problem: a rock fan gets 1 rock song and then "loud stuff".
* **High energy pop vs deep intense rock:** these overlap heavily (Gym Hero, Storm Runner, Laser Bloom, Iron Cathedral). Both want intense, loud, non acoustic music, so the only real difference is which genre gets the 2 point bonus. In plain language: to this system, a gym playlist and a rock playlist are basically the same playlist.
* **Default pop/happy vs genre not in catalog (k-pop/happy):** without the genre bonus the k-pop listener's list is ranked almost entirely by mood and energy, so Rooftop Lights (indie pop) actually beats Sunrise City (pop). The happy songs still float to the top, which is reasonable, but the scores are about half as high.
* **Conflicted sad but hyped vs chill lofi:** the conflicted listener asked for sad folk at 0.9 energy. The system gave them Cabin Letters (folk, sad, energy 0.30) at #1 because genre plus mood (3 points) beats any energy fit. It completely ignored the energy request, while for the lofi listener, energy and genre agree so nothing is ignored. This is the clearest "trick" result: when preferences conflict, genre and mood always win.
* **Middle of everything (energy 0.5 only):** with no genre or mood, every song scores between 0 and 1.5 and the top 5 are separated by less than 0.1 point. The list is basically random mid tempo songs, which shows the system has nothing to say about a user who does not state a genre.

### Why does Gym Hero keep showing up for "Happy Pop" listeners?

Gym Hero is one of only two songs labeled "pop", so it collects the 2 point genre bonus that most of the catalog cannot get. Its energy (0.93) is a little high for a 0.8 target but still close enough to earn 1.3 of the 1.5 energy points. That 3.31 total beats Rooftop Lights (2.44), which is happier and closer in energy but is labeled "indie pop" instead of "pop". In everyday words: the system trusts the genre label more than how the song actually feels.

### Experiment: weight shift (energy x2, genre x0.5)

Running `python -m src.main --all --experiment` doubled energy to 3.0 and halved genre to 1.0.

* **Default pop/happy:** Rooftop Lights moved up to #2 and Gym Hero dropped to #3. This was **more accurate**, because the happy song now outranks the workout song for a happy listener.
* **High energy pop:** Storm Runner (rock) passed Sunrise City (pop). Different but not clearly better.
* **Conflicted sad but hyped:** Cabin Letters stayed #1, but its lead over the loud high energy songs shrank from 2.11 points to 0.23 points, so the loud songs nearly caught up. The system started to respect the energy request.
* **Chill lofi:** nearly unchanged, since lofi songs already match on every feature.

**Takeaway:** the change made results more accurate for cross genre cases and just different for others. I kept the original weights as the default because genre is still the strongest single signal for most listeners, but the experiment proves genre is over weighted.

### Automated tests

`pytest` runs 7 tests: the two starter OOP tests plus tests for numeric type conversion when loading the CSV, the exact score and reasons for a perfect match, energy rewarding closeness instead of magnitude, sorted top k output, and custom weights changing the ranking. All 7 pass.

---

## 8. Future Work

1. **Partial genre and mood similarity.** Give "indie pop" partial credit for a "pop" fan, and group moods into families (intense, energetic, euphoric) so near matches still score.
2. **Use the unused features.** Add tempo and valence closeness so two songs with the same genre and energy can still be told apart.
3. **Diversity in the top 5.** Limit each genre or artist to two slots so one label cannot take over a list, and so niche genre fans still see variety.
4. Support multiple favorite genres or weighted preferences instead of one label.

---

## 9. Personal Reflection

**Biggest learning moment:** realizing that the "personality" of a recommender lives in its weights. When I halved the genre weight, the exact same code went from acting like a genre purist to acting like someone who cares about vibe. Seeing Rooftop Lights jump over Gym Hero made it click that a recommender is not smart, it just follows the priorities someone chose.

**How AI tools helped, and when I double checked them:** AI was useful for quickly generating diverse songs in valid CSV format, drafting the scoring and ranking functions, and suggesting adversarial profiles I would not have thought of, like the "sad but hyped" listener. I still had to check its work. The starter `main.py` used an import that breaks under `python -m src.main`, so I had to fix that before anything ran. I also noticed some totals looked a hundredth off from their listed reasons (for example 1.43 vs +1.42), and confirmed it was only display rounding, not a math bug. And I had to verify by reading the output that "indie pop" really earns no genre points, since the AI described the matching as working on "pop" songs without flagging that edge case.

**What surprised me:** how much a few lines of arithmetic can "feel" like a real recommendation. The chill lofi list genuinely looks like a study playlist. But the edge cases showed how fake that feeling is: the system confidently gave a slow folk song to someone who asked for 0.9 energy, and it had nothing useful to say to someone who only gave an energy level.

**What I would try next:** add partial genre similarity and a diversity rule, then build a tiny collaborative filtering layer with a few fake users' likes, to compare how "people like you also liked" changes the results compared with pure content matching.
