"""
Command line runner for the VibeFinder music recommender simulation.

Usage:
    python -m src.main                      # default pop/happy profile
    python -m src.main --all                # every profile in PROFILES
    python -m src.main --profile chill_lofi # one named profile
    python -m src.main --all --experiment   # weight shift experiment (energy x2, genre x0.5)
"""

import argparse
import os

try:  # works with `python -m src.main`
    from src.recommender import DEFAULT_WEIGHTS, load_songs, recommend_songs
except ImportError:  # works with `python src/main.py`
    from recommender import DEFAULT_WEIGHTS, load_songs, recommend_songs

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "songs.csv")

PROFILES = {
    # Starter profile
    "default_pop_happy": {"genre": "pop", "mood": "happy", "energy": 0.8},
    # Three distinct "normal" listeners
    "high_energy_pop": {"genre": "pop", "mood": "intense", "energy": 0.9, "likes_acoustic": False},
    "chill_lofi": {"genre": "lofi", "mood": "chill", "energy": 0.35, "likes_acoustic": True},
    "deep_intense_rock": {"genre": "rock", "mood": "intense", "energy": 0.92, "likes_acoustic": False},
    # Adversarial / edge case listeners
    "conflicted_sad_but_hyped": {"genre": "folk", "mood": "sad", "energy": 0.9},
    "genre_not_in_catalog": {"genre": "k-pop", "mood": "happy", "energy": 0.7},
    "middle_of_everything": {"energy": 0.5},
}

# Experiment: double the importance of energy and halve the importance of genre.
EXPERIMENT_WEIGHTS = {**DEFAULT_WEIGHTS, "energy": DEFAULT_WEIGHTS["energy"] * 2, "genre": DEFAULT_WEIGHTS["genre"] / 2}


def describe_profile(prefs: dict) -> str:
    """Return a one line summary of a taste profile."""
    return ", ".join(f"{k}={v}" for k, v in prefs.items())


def print_recommendations(name: str, prefs: dict, songs: list, k: int, weights: dict) -> None:
    """Print a clean, readable block of the top k recommendations for one profile."""
    print("=" * 72)
    print(f"Profile: {name}")
    print(f"Prefs:   {describe_profile(prefs)}")
    print("-" * 72)
    for rank, (song, score, explanation) in enumerate(recommend_songs(prefs, songs, k=k, weights=weights), 1):
        print(f"{rank}. {song['title']} by {song['artist']} [{song['genre']}, {song['mood']}]  score {score:.2f}")
        for reason in explanation.split("; "):
            print(f"     - {reason}")
    print()


def main() -> None:
    """Load the catalog and print recommendations for the chosen profile(s)."""
    parser = argparse.ArgumentParser(description="VibeFinder music recommender simulation")
    parser.add_argument("--profile", choices=PROFILES.keys(), default="default_pop_happy")
    parser.add_argument("--all", action="store_true", help="run every profile")
    parser.add_argument("--experiment", action="store_true", help="energy x2, genre x0.5")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()

    songs = load_songs(DATA_PATH)
    print(f"Loaded songs: {len(songs)}")
    weights = EXPERIMENT_WEIGHTS if args.experiment else DEFAULT_WEIGHTS
    print(f"Weights: {weights}\n")

    names = PROFILES.keys() if args.all else [args.profile]
    for name in names:
        print_recommendations(name, PROFILES[name], songs, args.k, weights)


if __name__ == "__main__":
    main()
