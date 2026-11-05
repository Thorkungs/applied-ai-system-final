"""Core logic for the VibeFinder music recommender simulation.

The recommender is content based: it compares the attributes of each song
(genre, mood, energy, acousticness) against a user's taste profile, gives
every song a numeric score using a weighted "Algorithm Recipe", and then
ranks the catalog from best to worst match.
"""

import csv
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple


@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float


@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool


# The Algorithm Recipe. Points awarded for each kind of match.
DEFAULT_WEIGHTS: Dict[str, float] = {
    "genre": 2.0,     # exact genre match
    "mood": 1.0,      # exact mood match
    "energy": 1.5,    # max points for a perfect energy match (scaled by closeness)
    "acoustic": 0.5,  # max points for matching the user's acoustic preference
}

# Columns in songs.csv that must be converted from text to numbers.
INT_FIELDS = ("id",)
FLOAT_FIELDS = ("energy", "tempo_bpm", "valence", "danceability", "acousticness")


def load_songs(csv_path: str) -> List[Dict]:
    """Read songs.csv with the csv module and return a list of dicts with numeric fields converted."""
    songs: List[Dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for key in INT_FIELDS:
                row[key] = int(row[key])
            for key in FLOAT_FIELDS:
                row[key] = float(row[key])
            row["genre"] = row["genre"].strip().lower()
            row["mood"] = row["mood"].strip().lower()
            songs.append(row)
    return songs


def _normalize_prefs(user_prefs: Dict) -> Dict:
    """Accept either short keys (genre/mood/energy) or UserProfile style keys and return short keys."""
    return {
        "genre": (user_prefs.get("genre") or user_prefs.get("favorite_genre") or "").strip().lower(),
        "mood": (user_prefs.get("mood") or user_prefs.get("favorite_mood") or "").strip().lower(),
        "energy": user_prefs.get("energy", user_prefs.get("target_energy")),
        "likes_acoustic": user_prefs.get("likes_acoustic"),
    }


def score_song(
    user_prefs: Dict, song: Dict, weights: Optional[Dict[str, float]] = None
) -> Tuple[float, List[str]]:
    """Judge one song against the user's prefs and return (score, list of reasons)."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    prefs = _normalize_prefs(user_prefs)
    score = 0.0
    reasons: List[str] = []

    # 1. Genre: all or nothing match.
    if w["genre"] and prefs["genre"] and song["genre"] == prefs["genre"]:
        score += w["genre"]
        reasons.append(f"genre match: {song['genre']} (+{w['genre']:.2f})")

    # 2. Mood: all or nothing match.
    if w["mood"] and prefs["mood"] and song["mood"] == prefs["mood"]:
        score += w["mood"]
        reasons.append(f"mood match: {song['mood']} (+{w['mood']:.2f})")

    # 3. Energy: reward closeness to the target, not just "higher" or "lower".
    #    closeness = 1 - |song energy - target energy|, so a perfect match earns the full weight.
    if w["energy"] and prefs["energy"] is not None:
        gap = abs(song["energy"] - float(prefs["energy"]))
        points = w["energy"] * max(0.0, 1.0 - gap)
        score += points
        reasons.append(
            f"energy {song['energy']:.2f} vs target {float(prefs['energy']):.2f} (+{points:.2f})"
        )

    # 4. Acousticness: optional, only used when the profile says how it feels about acoustic sound.
    if w["acoustic"] and prefs["likes_acoustic"] is not None:
        a = song["acousticness"]
        fit = a if prefs["likes_acoustic"] else 1.0 - a
        points = w["acoustic"] * fit
        score += points
        label = "acoustic" if prefs["likes_acoustic"] else "produced/electronic"
        reasons.append(f"{label} feel {fit:.2f} (+{points:.2f})")

    return round(score, 4), reasons


def recommend_songs(
    user_prefs: Dict,
    songs: List[Dict],
    k: int = 5,
    weights: Optional[Dict[str, float]] = None,
) -> List[Tuple[Dict, float, str]]:
    """Score every song with score_song, sort highest first (ties by title), and return the top k."""
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song, weights)
        scored.append((song, score, "; ".join(reasons) if reasons else "no matching features"))
    # sorted() returns a new list and leaves the original catalog order untouched.
    ranked = sorted(scored, key=lambda item: (-item[1], item[0]["title"]))
    return ranked[:k]


class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """

    def __init__(self, songs: List[Song], weights: Optional[Dict[str, float]] = None):
        """Store the catalog of Song objects and optional custom weights."""
        self.songs = songs
        self.weights = weights

    @staticmethod
    def _prefs(user: UserProfile) -> Dict:
        """Convert a UserProfile into the prefs dict used by score_song."""
        return {
            "genre": user.favorite_genre,
            "mood": user.favorite_mood,
            "energy": user.target_energy,
            "likes_acoustic": user.likes_acoustic,
        }

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Return the top k Song objects for this user, best match first."""
        prefs = self._prefs(user)
        ranked = sorted(
            self.songs,
            key=lambda s: (-score_song(prefs, asdict(s), self.weights)[0], s.title),
        )
        return ranked[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Return a readable sentence explaining why this song got its score."""
        score, reasons = score_song(self._prefs(user), asdict(song), self.weights)
        detail = "; ".join(reasons) if reasons else "no matching features"
        return f"{song.title} scored {score:.2f} because: {detail}"
