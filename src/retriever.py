"""Retriever: finds the knowledge passages most relevant to a query."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .knowledge import Passage
from .textutil import TfidfIndex

# Passages scoring below this cosine similarity are treated as "nothing found".
MIN_SCORE = 0.08


@dataclass
class Hit:
    """One retrieved passage and how similar it was to the query."""

    passage: Passage
    score: float


class Retriever:
    """TF-IDF search over knowledge passages, optionally limited to one source file."""

    def __init__(self, passages: Sequence[Passage]):
        self.passages = list(passages)
        self._by_id: Dict[str, Passage] = {p.doc_id: p for p in self.passages}
        # The title is repeated so a query naming the heading ranks that passage first.
        self._index = TfidfIndex([f"{p.title}. {p.title}. {p.text}" for p in self.passages])

    def search(
        self, query: str, k: int = 3, source: Optional[str] = None, min_score: float = MIN_SCORE
    ) -> List[Hit]:
        """Return up to k passages with similarity >= min_score, best first."""
        hits: List[Hit] = []
        for index, score in self._index.search(query):
            passage = self.passages[index]
            if score < min_score:
                break
            if source is None or passage.source == source:
                hits.append(Hit(passage, score))
                if len(hits) == k:
                    break
        return hits

    def get(self, doc_id: str) -> Optional[Passage]:
        """Look up a passage by its citation id."""
        return self._by_id.get(doc_id)
