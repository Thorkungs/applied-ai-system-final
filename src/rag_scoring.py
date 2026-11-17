"""Knowledge-augmented scoring: the VibeFinder 1.0 recipe plus retrieved knowledge.

The original `score_song` only rewards exact label matches. Here the retrieved
passages change the score in three ways, each with a citation:

* a song in a genre or mood that the retrieved guide lists as related earns
  half credit instead of nothing,
* when the listener gave no energy level, the retrieved guide's typical energy
  is used as a lower-weight target,
* a song whose liner notes match the wording of the request earns a bonus.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .knowledge import Passage
from .recommender import DEFAULT_WEIGHTS, score_song
from .retriever import Hit

RELATED_SHARE = 0.5            # a related genre or mood earns this share of the exact-match points
INFERRED_ENERGY_SHARE = 0.5    # an energy target taken from the guide counts half as much as a stated one
NOTES_WEIGHT = 1.0             # max points for liner notes that match the request
NOTES_FULL_SIM = 0.5           # similarity that earns the full notes bonus


@dataclass
class RetrievedContext:
    """Everything the retriever found for one request."""

    genre_passage: Optional[Passage] = None
    mood_passage: Optional[Passage] = None
    note_hits: Dict[int, Hit] = field(default_factory=dict)  # song id -> liner note hit
    inferred_energy: Optional[float] = None
    inferred_energy_source: Optional[str] = None  # doc_id the energy came from

    def passages(self) -> List[Passage]:
        """Every retrieved passage, used to check citations."""
        found = [p for p in (self.genre_passage, self.mood_passage) if p is not None]
        return found + [hit.passage for hit in self.note_hits.values()]


@dataclass
class Reason:
    """One line of explanation, with the knowledge passage that supports it (if any)."""

    text: str
    citation: Optional[str] = None
    quote: Optional[str] = None


@dataclass
class Recommendation:
    """A ranked song with its score and reasons."""

    song: Dict
    score: float
    reasons: List[Reason]


def first_sentence(text: str) -> str:
    """Return the first sentence of a passage, used as the quoted evidence."""
    end = text.find(". ")
    return text if end == -1 else text[: end + 1]


def score_with_knowledge(
    prefs: Dict, song: Dict, context: RetrievedContext, weights: Optional[Dict[str, float]] = None
) -> Recommendation:
    """Score one song with the original recipe, then add the knowledge-based parts."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    score, base_reasons = score_song(prefs, song, w)
    reasons = [Reason(text) for text in base_reasons]

    genre_doc = context.genre_passage
    if genre_doc and prefs.get("genre") and song["genre"] != prefs["genre"] and song["genre"] in genre_doc.related:
        points = w["genre"] * RELATED_SHARE
        score += points
        reasons.append(
            Reason(f"related genre: {song['genre']} is close to {prefs['genre']} (+{points:.2f})",
                   genre_doc.doc_id, first_sentence(genre_doc.text))
        )

    mood_doc = context.mood_passage
    if mood_doc and prefs.get("mood") and song["mood"] != prefs["mood"] and song["mood"] in mood_doc.related:
        points = w["mood"] * RELATED_SHARE
        score += points
        reasons.append(
            Reason(f"related mood: {song['mood']} is close to {prefs['mood']} (+{points:.2f})",
                   mood_doc.doc_id, first_sentence(mood_doc.text))
        )

    if prefs.get("energy") is None and context.inferred_energy is not None:
        gap = abs(song["energy"] - context.inferred_energy)
        points = w["energy"] * INFERRED_ENERGY_SHARE * max(0.0, 1.0 - gap)
        score += points
        reasons.append(
            Reason(f"energy {song['energy']:.2f} vs typical {context.inferred_energy:.2f} from the guide (+{points:.2f})",
                   context.inferred_energy_source)
        )

    hit = context.note_hits.get(song["id"])
    if hit is not None:
        points = NOTES_WEIGHT * min(1.0, hit.score / NOTES_FULL_SIM)
        score += points
        reasons.append(
            Reason(f"liner notes match your request (+{points:.2f})", hit.passage.doc_id, first_sentence(hit.passage.text))
        )

    return Recommendation(song, round(score, 4), reasons)


def rank_with_knowledge(
    prefs: Dict,
    songs: Sequence[Dict],
    context: RetrievedContext,
    k: int = 3,
    weights: Optional[Dict[str, float]] = None,
    avoid_genres: Sequence[str] = (),
    avoid_moods: Sequence[str] = (),
) -> List[Recommendation]:
    """Score every allowed song and return the top k (ties broken by title, as in 1.0).

    Songs that earned no points have no reason to be recommended, so they are
    left out even if that means returning fewer than k songs.
    """
    allowed = [s for s in songs if s["genre"] not in avoid_genres and s["mood"] not in avoid_moods]
    scored = [score_with_knowledge(prefs, song, context, weights) for song in allowed]
    supported = [rec for rec in scored if rec.reasons and rec.score > 0]
    return sorted(supported, key=lambda r: (-r.score, r.song["title"]))[:k]


def max_possible_score(prefs: Dict, context: RetrievedContext, weights: Optional[Dict[str, float]] = None) -> float:
    """Highest score a perfect label match could earn for these prefs (the notes bonus is not counted)."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    total = 0.0
    if prefs.get("genre"):
        total += w["genre"]
    if prefs.get("mood"):
        total += w["mood"]
    if prefs.get("energy") is not None:
        total += w["energy"]
    elif context.inferred_energy is not None:
        total += w["energy"] * INFERRED_ENERGY_SHARE
    if prefs.get("likes_acoustic") is not None:
        total += w["acoustic"]
    return total
