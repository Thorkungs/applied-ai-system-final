"""Turn a plain English request into the taste profile the recommender scores.

Two stages:

1. Keyword stage (the baseline). Finds genre and mood labels that literally
   appear in the request, plus explicit energy and acoustic words. It also
   notices negation ("anything but pop") and records labels to avoid.
2. Few-shot stage (the specialization). For requests that describe a situation
   instead of naming labels ("heading to the gym"), it finds the most similar
   labeled examples in data/few_shot_examples.json and fills the missing slots
   from them. It abstains when the nearest examples disagree.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .knowledge import Passage
from .textutil import TfidfIndex, normalize

SLOTS = ("genre", "mood", "energy", "likes_acoustic")

# Other names people use for genres in the catalog or knowledge base.
GENRE_ALIASES = {
    "rap": "hip hop",
    "heavy metal": "metal",
    "orchestral": "classical",
    "reggaeton": "latin",
    "salsa": "latin",
    "techno": "edm",
    "electronic dance music": "edm",
}

# Explicit energy phrases and the 0 to 1 target each one means.
HIGH_ENERGY, MID_ENERGY, LOW_ENERGY = 0.9, 0.55, 0.3
ENERGY_PHRASES = {
    "high energy": HIGH_ENERGY, "upbeat": HIGH_ENERGY, "fast": HIGH_ENERGY, "hype": HIGH_ENERGY,
    "hyped": HIGH_ENERGY, "loud": HIGH_ENERGY, "lively": HIGH_ENERGY,
    "medium energy": MID_ENERGY, "mid tempo": MID_ENERGY, "moderate": MID_ENERGY,
    "low energy": LOW_ENERGY, "slow": LOW_ENERGY, "calm": LOW_ENERGY, "quiet": LOW_ENERGY,
    "mellow": LOW_ENERGY, "soft": LOW_ENERGY, "gentle": LOW_ENERGY, "peaceful": LOW_ENERGY,
}
# "not too loud" means fairly low, "not too slow" means fairly high.
NEGATED_HIGH_ENERGY, NEGATED_LOW_ENERGY = 0.4, 0.7

ACOUSTIC_PHRASES = {"acoustic": True, "unplugged": True, "electronic": False, "synth": False, "synths": False}

NEGATORS = frozenset("no not without except never avoid hate nothing non don dont isn aren doesn".split())
NEGATION_WINDOW = 3  # how many words before a label can negate it

FEW_SHOT_NEIGHBORS = 3
FEW_SHOT_MIN_SIM = 0.25    # neighbors below this similarity are ignored
FEW_SHOT_RELATIVE_SIM = 0.5  # ...and so are neighbors less than half as similar as the best one
FEW_SHOT_MIN_SHARE = 0.6   # the winning mood needs this share of the vote, else abstain
FEW_SHOT_GENRE_MIN_SIM = 0.45
FEW_SHOT_FULL_SIM = 0.6    # similarity that counts as full confidence


@dataclass
class Vocabulary:
    """The genre and mood labels the system knows, keyed by their normalized spelling."""

    genres: Dict[str, str]
    moods: Dict[str, str]

    @classmethod
    def build(cls, songs: Sequence[Dict], passages: Sequence[Passage] = ()) -> "Vocabulary":
        """Collect labels from the catalog and from genre/mood knowledge headings."""
        genres = {normalize(s["genre"]): s["genre"] for s in songs}
        moods = {normalize(s["mood"]): s["mood"] for s in songs}
        for p in passages:
            if p.source == "genres":
                genres.setdefault(normalize(p.title), p.title.lower())
            elif p.source == "moods":
                moods.setdefault(normalize(p.title), p.title.lower())
        for alias, label in GENRE_ALIASES.items():
            genres.setdefault(normalize(alias), label)
        return cls(genres, moods)


@dataclass
class Interpretation:
    """What the system understood, and how sure it is about each slot."""

    prefs: Dict = field(default_factory=lambda: {s: None for s in SLOTS})
    avoid_genres: List[str] = field(default_factory=list)
    avoid_moods: List[str] = field(default_factory=list)
    sources: Dict[str, str] = field(default_factory=dict)       # slot -> "keyword" | "few-shot" | "human"
    confidence: Dict[str, float] = field(default_factory=dict)  # slot -> 0..1
    neighbors: List[Tuple[str, float]] = field(default_factory=list)  # few-shot examples used

    def set(self, slot: str, value, source: str, confidence: float) -> None:
        """Fill one slot and record where the value came from."""
        self.prefs[slot] = value
        self.sources[slot] = source
        self.confidence[slot] = round(confidence, 2)

    @property
    def filled(self) -> List[str]:
        """Names of the slots that have a value."""
        return [s for s in SLOTS if self.prefs[s] is not None]

    def describe(self) -> str:
        """One line summary such as "genre=pop (keyword) | energy=0.90 (few-shot 0.71)"."""
        parts = []
        for slot in self.filled:
            value = self.prefs[slot]
            shown = f"{value:.2f}" if isinstance(value, float) else str(value)
            source = self.sources[slot]
            if source == "few-shot":
                source += f" {self.confidence[slot]:.2f}"
            parts.append(f"{slot}={shown} ({source})")
        for label in self.avoid_genres:
            parts.append(f"avoid genre={label}")
        for label in self.avoid_moods:
            parts.append(f"avoid mood={label}")
        return " | ".join(parts) if parts else "nothing I can score"


def _find_phrases(norm: str, phrases: Sequence[str]) -> Tuple[List[Tuple[str, bool]], str]:
    """Find whole-word phrases, longest first. Returns [(phrase, negated)] and the text with matches removed."""
    found: List[Tuple[int, str, bool]] = []
    for phrase in sorted(phrases, key=len, reverse=True):
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])")
        while True:
            match = pattern.search(norm)
            if not match:
                break
            before = norm[: match.start()].split()
            window = before[-NEGATION_WINDOW:]
            negated = any(w in NEGATORS for w in window) or before[-2:] == ["anything", "but"]
            found.append((match.start(), phrase, negated))
            norm = norm[: match.start()] + " " * len(phrase) + norm[match.end():]
    return [(phrase, negated) for _, phrase, negated in sorted(found)], norm


def keyword_interpret(text: str, vocab: Vocabulary) -> Interpretation:
    """Baseline interpreter: only understands labels and energy words that literally appear."""
    result = Interpretation()
    norm = normalize(text)

    matches, norm = _find_phrases(norm, list(vocab.genres))
    for phrase, negated in matches:
        label = vocab.genres[phrase]
        if negated:
            if label not in result.avoid_genres:
                result.avoid_genres.append(label)
        elif result.prefs["genre"] is None:
            result.set("genre", label, "keyword", 1.0)

    matches, norm = _find_phrases(norm, list(vocab.moods))
    for phrase, negated in matches:
        label = vocab.moods[phrase]
        if negated:
            if label not in result.avoid_moods:
                result.avoid_moods.append(label)
        elif result.prefs["mood"] is None:
            result.set("mood", label, "keyword", 1.0)

    number = re.search(r"energy\s*(?:of|at|around|about|level)?\s*((?:0?\.\d+)|1\.0|[01])(?![0-9.])", norm) or re.search(
        r"(?<![0-9.])((?:0?\.\d+)|1\.0)\s*energy", norm
    )
    if number:
        result.set("energy", float(number.group(1)), "keyword", 1.0)
    else:
        matches, norm = _find_phrases(norm, list(ENERGY_PHRASES))
        if matches:
            phrase, negated = matches[0]
            value = ENERGY_PHRASES[phrase]
            if negated:
                value = NEGATED_HIGH_ENERGY if value == HIGH_ENERGY else NEGATED_LOW_ENERGY if value == LOW_ENERGY else value
            result.set("energy", value, "keyword", 1.0)

    matches, norm = _find_phrases(norm, list(ACOUSTIC_PHRASES))
    if matches:
        phrase, negated = matches[0]
        result.set("likes_acoustic", ACOUSTIC_PHRASES[phrase] != negated, "keyword", 1.0)

    return result


def load_examples(path: str) -> List[Dict]:
    """Load the labeled few-shot examples from a JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class FewShotInterpreter:
    """Keyword interpreter plus nearest-example matching for situational requests."""

    def __init__(self, examples: Sequence[Dict], vocab: Vocabulary):
        self.examples = list(examples)
        self.vocab = vocab
        self._index = TfidfIndex([e["text"] for e in self.examples])

    def interpret(self, text: str) -> Interpretation:
        """Run the keyword stage, then fill any missing slots from similar examples."""
        result = keyword_interpret(text, self.vocab)
        nearest = self._index.search(text)[:FEW_SHOT_NEIGHBORS]
        floor = max(FEW_SHOT_MIN_SIM, FEW_SHOT_RELATIVE_SIM * nearest[0][1]) if nearest else 0.0
        neighbors = [(self.examples[i], sim) for i, sim in nearest if sim >= floor]
        if not neighbors:
            return result

        # Decide which mood the neighbors agree on. A mood the user stated
        # outright always wins, and only neighbors with that mood may add detail.
        stated_mood = result.prefs["mood"]
        if stated_mood is not None:
            mood = stated_mood
        else:
            votes: Dict[str, float] = {}
            for example, sim in neighbors:
                label = example["prefs"].get("mood")
                if label and label not in result.avoid_moods:
                    votes[label] = votes.get(label, 0.0) + sim * sim  # squared so close matches count more
            mood = max(votes, key=votes.get) if votes else None
            if mood is not None and votes[mood] / sum(votes.values()) < FEW_SHOT_MIN_SHARE:
                return result  # the examples disagree, so do not guess

        if mood is None:
            agreeing = neighbors  # examples that only describe energy or sound
        else:
            agreeing = [(e, sim) for e, sim in neighbors if e["prefs"].get("mood") == mood]
        if not agreeing:
            return result

        top_sim = agreeing[0][1]
        confidence = min(1.0, top_sim / FEW_SHOT_FULL_SIM)
        result.neighbors = [(e["text"], sim) for e, sim in agreeing]

        if stated_mood is None and mood is not None:
            result.set("mood", mood, "few-shot", confidence)
        if result.prefs["energy"] is None:
            weighted = [(e["prefs"]["energy"], sim) for e, sim in agreeing if e["prefs"].get("energy") is not None]
            if weighted:
                energy = sum(v * w for v, w in weighted) / sum(w for _, w in weighted)
                result.set("energy", round(energy, 2), "few-shot", confidence)
        if result.prefs["likes_acoustic"] is None:
            acoustic = agreeing[0][0]["prefs"].get("likes_acoustic")
            if acoustic is not None:
                result.set("likes_acoustic", acoustic, "few-shot", confidence)
        if result.prefs["genre"] is None and top_sim >= FEW_SHOT_GENRE_MIN_SIM:
            genre = agreeing[0][0]["prefs"].get("genre")
            if genre and genre not in result.avoid_genres:
                result.set("genre", genre, "few-shot", confidence)
        return result


def parse_overrides(text: str, vocab: Vocabulary) -> Dict:
    """Parse a human correction such as "genre=jazz energy=0.4 acoustic=yes" into prefs.

    Raises ValueError with a readable message when a value is not valid.
    """
    overrides: Dict = {}
    for key, value in re.findall(r"(\w+)\s*=\s*([^=]+?)(?=\s+\w+\s*=|$)", text.strip().lower()):
        value = value.strip()
        if key == "genre":
            overrides["genre"] = vocab.genres.get(normalize(value), value)
        elif key == "mood":
            if normalize(value) not in vocab.moods:
                raise ValueError(f"unknown mood '{value}'. Known moods: {', '.join(sorted(vocab.moods.values()))}")
            overrides["mood"] = vocab.moods[normalize(value)]
        elif key == "energy":
            try:
                energy = float(value)
            except ValueError:
                raise ValueError(f"energy must be a number from 0 to 1, got '{value}'") from None
            if not 0.0 <= energy <= 1.0:
                raise ValueError(f"energy must be between 0 and 1, got {energy}")
            overrides["energy"] = energy
        elif key in ("acoustic", "likes_acoustic"):
            if value not in ("yes", "no", "true", "false"):
                raise ValueError(f"acoustic must be yes or no, got '{value}'")
            overrides["likes_acoustic"] = value in ("yes", "true")
        else:
            raise ValueError(f"unknown setting '{key}'. Use genre, mood, energy or acoustic")
    if not overrides:
        raise ValueError("no corrections found. Example: genre=jazz energy=0.4")
    return overrides
