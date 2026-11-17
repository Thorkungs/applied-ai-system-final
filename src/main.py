"""
Command line runner for VibeFinder.

VibeFinder 2.0 (plain English requests, answered by the agent):
    python -m src.main "chill lofi for studying"
    python -m src.main "music for the gym" --trace         # also print every agent step
    python -m src.main "happy k-pop" --baseline            # same request with retrieval and few-shot off
    python -m src.main "sad folk songs" --confirm          # review what was understood before ranking
    python -m src.main --interactive                       # keep asking until you type quit

VibeFinder 1.0 (the original fixed taste profiles, kept for comparison):
    python -m src.main --profile chill_lofi
    python -m src.main --all
    python -m src.main --all --experiment                  # energy x2, genre x0.5
"""

import argparse
import sys

from .agent import SONGS_PATH, VibeAgent, setup_logging
from .interpreter import parse_overrides
from .recommender import DEFAULT_WEIGHTS, load_songs, recommend_songs
from .report import format_result, trace_to_markdown

DATA_PATH = SONGS_PATH

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


def run_profiles(args: argparse.Namespace) -> None:
    """VibeFinder 1.0 mode: print recommendations for the fixed taste profiles."""
    songs = load_songs(DATA_PATH)
    print(f"Loaded songs: {len(songs)}")
    weights = EXPERIMENT_WEIGHTS if args.experiment else DEFAULT_WEIGHTS
    print(f"Weights: {weights}\n")
    names = PROFILES.keys() if args.all else [args.profile or "default_pop_happy"]
    for name in names:
        print_recommendations(name, PROFILES[name], songs, args.k or 5, weights)


def ask_for_corrections(agent: VibeAgent, request: str) -> dict:
    """Human-in-the-loop step: show what was understood and let the person correct it."""
    interp = agent.interpret(request)
    print(f"I understood: {interp.describe()}")
    print("Press Enter to accept, or type corrections such as: genre=jazz energy=0.4 acoustic=yes")
    try:
        answer = input("> ").strip()
    except EOFError:
        answer = ""
    if not answer:
        return {}
    try:
        overrides = parse_overrides(answer, agent.vocab)
    except ValueError as error:
        print(f"Ignoring that correction: {error}")
        return {}
    print(f"Using your corrections: {describe_profile(overrides)}")
    return overrides


def answer(agent: VibeAgent, request: str, args: argparse.Namespace) -> None:
    """Run one request through the agent and print the result."""
    overrides = ask_for_corrections(agent, request) if args.confirm else {}
    result = agent.run(request, k=args.k or 3, overrides=overrides)
    print(format_result(result, show_trace=args.trace))
    if args.save_trace:
        with open(args.save_trace, "a", encoding="utf-8") as f:
            f.write(trace_to_markdown(result) + "\n")
        print(f"Trace appended to {args.save_trace}")


def main() -> None:
    """Parse arguments and run either the agent (2.0) or the fixed profiles (1.0)."""
    parser = argparse.ArgumentParser(description="VibeFinder: an explainable music recommender agent")
    parser.add_argument("request", nargs="?", help="what you feel like listening to, in plain English")
    parser.add_argument("-k", type=int, default=None, help="how many songs to return (default 3, or 5 for profiles)")
    parser.add_argument("--trace", action="store_true", help="print every step the agent took")
    parser.add_argument("--save-trace", metavar="FILE", help="append the trace as markdown to FILE")
    parser.add_argument("--baseline", action="store_true", help="turn off retrieval and few-shot (1.0 style matching)")
    parser.add_argument("--confirm", action="store_true", help="review and correct what was understood before ranking")
    parser.add_argument("--interactive", action="store_true", help="keep asking for requests until you type quit")
    parser.add_argument("--profile", choices=PROFILES.keys(), help="1.0 mode: run one fixed taste profile")
    parser.add_argument("--all", action="store_true", help="1.0 mode: run every fixed profile")
    parser.add_argument("--experiment", action="store_true", help="1.0 mode: energy x2, genre x0.5")
    args = parser.parse_args()

    if args.profile or args.all or args.experiment:
        run_profiles(args)
        return
    if args.request is None and not args.interactive:
        parser.print_help()
        sys.exit(2)

    setup_logging()
    agent = VibeAgent.from_files(use_rag=not args.baseline, use_few_shot=not args.baseline)
    if args.request is not None:
        answer(agent, args.request, args)
    if args.interactive:
        print("Type what you feel like listening to, or 'quit' to stop.")
        while True:
            try:
                request = input("vibe> ")
            except EOFError:
                break
            if request.strip().lower() in ("quit", "exit", "q"):
                break
            answer(agent, request, args)


if __name__ == "__main__":
    main()
