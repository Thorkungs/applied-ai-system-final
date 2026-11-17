"""Tests for the knowledge base loader and the TF-IDF retriever."""

import pytest

from src.agent import KNOWLEDGE_DIR, SONGS_PATH
from src.knowledge import load_knowledge
from src.recommender import load_songs
from src.retriever import Retriever
from src.textutil import TfidfIndex, normalize, tokens


@pytest.fixture(scope="module")
def passages():
    return load_knowledge(KNOWLEDGE_DIR)


@pytest.fixture(scope="module")
def retriever(passages):
    return Retriever(passages)


def test_knowledge_loads_three_sources_with_fields(passages):
    assert {p.source for p in passages} == {"genres", "moods", "song_notes"}
    pop = next(p for p in passages if p.doc_id == "genres.md#pop")
    assert pop.related == ["indie pop", "r&b", "synthwave"]
    assert pop.typical_energy == 0.80
    assert pop.text.startswith("Pop is hook driven")


def test_every_song_has_exactly_one_liner_note(passages):
    song_ids = sorted(s["id"] for s in load_songs(SONGS_PATH))
    note_ids = sorted(p.song_id for p in passages if p.source == "song_notes")
    assert note_ids == song_ids


def test_guides_only_point_at_labels_that_exist(passages):
    """A `related:` label with a typo would silently never match, so check them all."""
    songs = load_songs(SONGS_PATH)
    genres = {s["genre"] for s in songs}
    moods = {s["mood"] for s in songs}
    for p in passages:
        known = genres if p.source == "genres" else moods if p.source == "moods" else None
        if known is not None:
            assert set(p.related) <= known, f"{p.doc_id} lists an unknown label"
            assert p.typical_energy is not None, f"{p.doc_id} has no typical_energy"


def test_normalize_merges_genre_spellings():
    assert normalize("Hip-Hop and R&B, K-pop, lo-fi") == "hiphop and rnb kpop lofi"
    assert tokens("studying") == tokens("study") == tokens("studies")
    assert tokens("running") == tokens("run")


def test_search_finds_the_matching_guide(retriever):
    assert retriever.search("k-pop", k=1, source="genres")[0].passage.doc_id == "genres.md#k-pop"
    assert retriever.search("r&b", k=1, source="genres")[0].passage.doc_id == "genres.md#r-b"
    assert retriever.search("sad", k=1, source="moods")[0].passage.doc_id == "moods.md#sad"


def test_search_matches_liner_notes_by_meaning_of_the_request(retriever):
    hits = retriever.search("rainy afternoon reading", k=3, source="song_notes")
    assert hits[0].passage.title == "Library Rain"
    assert hits[0].score > hits[1].score


def test_search_respects_source_filter_and_k(retriever):
    hits = retriever.search("guitar", k=2, source="song_notes")
    assert len(hits) <= 2
    assert all(h.passage.source == "song_notes" for h in hits)


def test_off_topic_query_retrieves_nothing(retriever):
    assert retriever.search("what is the capital of France") == []


def test_unknown_words_lower_similarity():
    index = TfidfIndex(["music for the gym", "songs to cry to"])
    exact = index.search("gym")[0][1]
    diluted = index.search("gym zebra quantum")[0][1]
    assert diluted < exact
