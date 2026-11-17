"""Shared text helpers: normalization, tokenizing, and a small TF-IDF index.

Everything here uses only the standard library so the project runs without
downloading a model or calling an API.
"""

import math
import re
from collections import Counter
from typing import Dict, List, Sequence, Tuple

# Spellings that should be treated as one word before punctuation is removed.
_ALIASES = (
    (r"\bhip[\s-]?hop\b", "hiphop"),
    (r"\br\s?(?:&|and|n)\s?b\b", "rnb"),
    (r"\bk[\s-]?pop\b", "kpop"),
    (r"\blo[\s-]?fi\b", "lofi"),
)

# Words that appear in almost every request and carry no preference.
STOPWORDS = frozenset(
    """
    a an the and or of to for in on at with by from into about as
    i im me my we our you your it its is are am be been was this that these those
    some something anything any music song songs track tracks playlist tune tunes
    want need give play find like please can could would have has got get just
    really very so too lot kind mood feel feeling listen listening recommend
    while when up all each after before during through then there here now right
    than both own same out off over under again once how why what which who
    s t m re ll d
    """.split()
)

# Letters that stay doubled after a suffix is removed ("chilling" -> "chill").
_KEEP_DOUBLE = frozenset("lszf")


def normalize(text: str) -> str:
    """Lowercase text, merge known aliases, and replace punctuation with spaces."""
    text = text.lower()
    for pattern, replacement in _ALIASES:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)  # keep decimals such as 0.8
    text = re.sub(r"[^a-z0-9.\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _undouble(word: str) -> str:
    """Drop a doubled final consonant left behind by a suffix ("runn" -> "run")."""
    if len(word) >= 3 and word[-1] == word[-2] and word[-1] not in _KEEP_DOUBLE and word[-1] not in "aeiou":
        return word[:-1]
    return word


def stem(word: str) -> str:
    """Very light stemmer so "studying", "studies" and "study" land on the same token."""
    if word.endswith("ing") and len(word) >= 6:
        word = _undouble(word[:-3])
    elif word.endswith("ies") and len(word) >= 5:
        word = word[:-3] + "y"
    elif word.endswith("ed") and len(word) >= 5:
        word = _undouble(word[:-2])
    elif word.endswith("s") and len(word) >= 4 and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    if len(word) >= 4 and word[-1] in "ey":
        word = _undouble(word[:-1])
    return word


def tokens(text: str) -> List[str]:
    """Split text into stemmed tokens with stopwords removed."""
    return [stem(w) for w in normalize(text).split() if w not in STOPWORDS]


class TfidfIndex:
    """TF-IDF vectors with cosine similarity over a fixed list of documents."""

    def __init__(self, documents: Sequence[str]):
        doc_tokens = [tokens(d) for d in documents]
        n = len(doc_tokens)
        df = Counter(t for toks in doc_tokens for t in set(toks))
        self._idf: Dict[str, float] = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        # Words the index has never seen still count toward the length of a
        # query, so an off topic query cannot look like a strong match.
        self._unknown_idf = math.log(n + 1) + 1.0
        self._vectors = [self._vector(toks) for toks in doc_tokens]

    def _vector(self, toks: List[str]) -> Dict[str, float]:
        """Return a unit length TF-IDF vector for a list of tokens."""
        counts = Counter(toks)
        vec = {t: (1.0 + math.log(c)) * self._idf.get(t, self._unknown_idf) for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values()))
        return {t: v / norm for t, v in vec.items()} if norm else {}

    def search(self, query: str) -> List[Tuple[int, float]]:
        """Return (document index, similarity) for every document that shares a word with the query."""
        q = self._vector(tokens(query))
        scored = ((i, sum(w * d.get(t, 0.0) for t, w in q.items())) for i, d in enumerate(self._vectors))
        return sorted(((i, round(s, 4)) for i, s in scored if s > 0), key=lambda pair: (-pair[1], pair[0]))
