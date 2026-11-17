"""Guardrails: checks on what goes into the agent and on what comes out.

Input side: reject requests that are empty, too long, or contain no words, and
answer crisis language with a support message instead of a playlist.
Data side: drop malformed catalog rows instead of crashing on them.
Output side: verify every recommendation against the catalog and every citation
and quote against the passages that were actually retrieved.
"""

import math
import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from .knowledge import Passage
from .rag_scoring import Recommendation

MAX_REQUEST_CHARS = 300
MIN_K, MAX_K = 1, 10

REQUIRED_SONG_FIELDS = ("id", "title", "artist", "genre", "mood", "energy", "acousticness")
UNIT_FIELDS = ("energy", "acousticness")  # must be between 0 and 1

# Phrases that suggest the person may be in crisis. A keyword list is a blunt
# tool (see model_card.md), but it is better than answering with sad songs.
CRISIS_PATTERNS = (
    r"\bkill myself\b", r"\bsuicid", r"\bend my life\b", r"\bwant to die\b",
    r"\bself[\s-]?harm\b", r"\bhurt myself\b",
)
SUPPORT_MESSAGE = (
    "It sounds like you might be going through something really painful. I'm only a music "
    "recommender and can't help with this the way a person can. If you are in the US you can "
    "call or text 988 (Suicide & Crisis Lifeline) at any time. Anywhere else, please reach out "
    "to a local crisis line or someone you trust. If you would just like some calm music, ask "
    "me for that and I'll find some."
)


@dataclass
class InputCheck:
    """Result of checking one request."""

    ok: bool
    code: str      # "ok" | "empty" | "too_long" | "no_words" | "crisis"
    cleaned: str   # request with control characters removed and whitespace collapsed
    message: str = ""


def check_request(raw) -> InputCheck:
    """Validate and clean a request before the agent sees it."""
    if not isinstance(raw, str):
        return InputCheck(False, "empty", "", "Please type what you feel like listening to.")
    # Control characters are stripped so a request cannot break the log file layout.
    cleaned = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", raw)).strip()
    if not cleaned:
        return InputCheck(False, "empty", cleaned, "Please type what you feel like listening to.")
    if len(cleaned) > MAX_REQUEST_CHARS:
        return InputCheck(
            False, "too_long", cleaned[:MAX_REQUEST_CHARS],
            f"That request is {len(cleaned)} characters. Please keep it under {MAX_REQUEST_CHARS}.",
        )
    if not re.search(r"[A-Za-z]{2,}", cleaned):
        return InputCheck(False, "no_words", cleaned, "I couldn't find any words in that. Try something like 'chill lofi for studying'.")
    if any(re.search(pattern, cleaned.lower()) for pattern in CRISIS_PATTERNS):
        return InputCheck(False, "crisis", cleaned, SUPPORT_MESSAGE)
    return InputCheck(True, "ok", cleaned)


def clamp_k(k) -> int:
    """Keep the number of recommendations inside a sensible range."""
    try:
        return max(MIN_K, min(MAX_K, int(k)))
    except (TypeError, ValueError):
        return 3


def validate_catalog(songs: Sequence[Dict]) -> Tuple[List[Dict], List[str]]:
    """Return (usable songs, problems). Rows with missing or out-of-range values are dropped."""
    valid: List[Dict] = []
    problems: List[str] = []
    seen_ids = set()
    for row_number, song in enumerate(songs, start=1):
        missing = [f for f in REQUIRED_SONG_FIELDS if song.get(f) in (None, "")]
        if missing:
            problems.append(f"row {row_number}: missing {', '.join(missing)}")
            continue
        bad = [f for f in UNIT_FIELDS if not isinstance(song[f], (int, float)) or not 0.0 <= song[f] <= 1.0]
        if bad:
            problems.append(f"row {row_number} ({song['title']}): {', '.join(bad)} must be between 0 and 1")
            continue
        if song["id"] in seen_ids:
            problems.append(f"row {row_number} ({song['title']}): duplicate id {song['id']}")
            continue
        seen_ids.add(song["id"])
        valid.append(song)
    return valid, problems


def verify_output(
    recommendations: Sequence[Recommendation],
    catalog: Sequence[Dict],
    retrieved: Sequence[Passage],
    k: int,
    avoid_genres: Sequence[str] = (),
    avoid_moods: Sequence[str] = (),
) -> List[str]:
    """Check the final answer. Returns a list of problems; an empty list means it is safe to show."""
    problems: List[str] = []
    by_id = {song["id"]: song for song in catalog}
    passages = {p.doc_id: p for p in retrieved}

    if len(recommendations) > k:
        problems.append(f"returned {len(recommendations)} songs but only {k} were requested")
    ids = [r.song.get("id") for r in recommendations]
    if len(ids) != len(set(ids)):
        problems.append("the same song appears more than once")

    for rec in recommendations:
        title = rec.song.get("title", "?")
        real = by_id.get(rec.song.get("id"))
        if real is None or real["title"] != title or real["artist"] != rec.song.get("artist"):
            problems.append(f"'{title}' is not a song in the catalog")
            continue
        if not isinstance(rec.score, (int, float)) or not math.isfinite(rec.score) or rec.score < 0:
            problems.append(f"'{title}' has an invalid score: {rec.score}")
        if not rec.reasons:
            problems.append(f"'{title}' has no explanation")
        if real["genre"] in avoid_genres or real["mood"] in avoid_moods:
            problems.append(f"'{title}' is in a genre or mood the listener asked to avoid")
        for reason in rec.reasons:
            if reason.citation is None:
                continue
            source = passages.get(reason.citation)
            if source is None:
                problems.append(f"'{title}' cites {reason.citation}, which was not retrieved")
            elif reason.quote and reason.quote not in source.text:
                problems.append(f"'{title}' quotes text that is not in {reason.citation}")
    return problems
