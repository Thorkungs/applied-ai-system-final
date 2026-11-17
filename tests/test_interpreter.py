"""Tests for turning request text into a taste profile."""

import pytest

from src.agent import EXAMPLES_PATH, KNOWLEDGE_DIR, SONGS_PATH
from src.interpreter import (
    FewShotInterpreter,
    Vocabulary,
    keyword_interpret,
    load_examples,
    parse_overrides,
)
from src.knowledge import load_knowledge
from src.recommender import load_songs


@pytest.fixture(scope="module")
def vocab():
    return Vocabulary.build(load_songs(SONGS_PATH), load_knowledge(KNOWLEDGE_DIR))


@pytest.fixture(scope="module")
def few_shot(vocab):
    return FewShotInterpreter(load_examples(EXAMPLES_PATH), vocab)


def test_keyword_finds_explicit_labels(vocab):
    interp = keyword_interpret("happy pop songs", vocab)
    assert interp.prefs["genre"] == "pop"
    assert interp.prefs["mood"] == "happy"
    assert interp.sources == {"genre": "keyword", "mood": "keyword"}


def test_keyword_prefers_the_longest_genre_name(vocab):
    assert keyword_interpret("indie pop please", vocab).prefs["genre"] == "indie pop"


def test_keyword_understands_other_spellings(vocab):
    assert keyword_interpret("some hip-hop", vocab).prefs["genre"] == "hip hop"
    assert keyword_interpret("R&B tonight", vocab).prefs["genre"] == "r&b"
    assert keyword_interpret("rap music", vocab).prefs["genre"] == "hip hop"
    assert keyword_interpret("K-Pop", vocab).prefs["genre"] == "k-pop"


def test_keyword_reads_energy_words_and_numbers(vocab):
    assert keyword_interpret("something upbeat", vocab).prefs["energy"] == 0.9
    assert keyword_interpret("slow songs", vocab).prefs["energy"] == 0.3
    assert keyword_interpret("rock at energy 0.75", vocab).prefs["energy"] == 0.75
    assert keyword_interpret("not too loud", vocab).prefs["energy"] == 0.4


def test_negated_labels_are_avoided_not_preferred(vocab):
    interp = keyword_interpret("upbeat music, anything but pop", vocab)
    assert interp.prefs["genre"] is None
    assert interp.avoid_genres == ["pop"]
    interp = keyword_interpret("no jazz and nothing sad", vocab)
    assert interp.avoid_genres == ["jazz"]
    assert interp.avoid_moods == ["sad"]


def test_acoustic_preference(vocab):
    assert keyword_interpret("acoustic folk", vocab).prefs["likes_acoustic"] is True
    assert keyword_interpret("nothing acoustic", vocab).prefs["likes_acoustic"] is False


def test_keyword_baseline_cannot_read_situations(vocab):
    assert keyword_interpret("heading to the gym for leg day", vocab).filled == []


def test_few_shot_reads_situations(few_shot):
    interp = few_shot.interpret("heading to the gym for leg day")
    assert interp.prefs["mood"] == "intense"
    assert interp.prefs["energy"] >= 0.85
    assert interp.sources["mood"] == "few-shot"
    assert 0 < interp.confidence["mood"] <= 1
    assert interp.neighbors, "the examples that were used should be recorded"


def test_few_shot_does_not_override_a_stated_mood(few_shot):
    # "tonight" appears in a party example, but the user said "moody".
    interp = few_shot.interpret("moody synthwave for tonight")
    assert interp.prefs["mood"] == "moody"
    assert interp.sources["mood"] == "keyword"
    assert interp.prefs["energy"] is None


def test_few_shot_abstains_when_examples_disagree(vocab):
    examples = [
        {"text": "morning run", "prefs": {"mood": "intense", "energy": 0.9}},
        {"text": "morning coffee", "prefs": {"mood": "relaxed", "energy": 0.4}},
    ]
    interp = FewShotInterpreter(examples, vocab).interpret("morning")
    assert interp.filled == []


def test_few_shot_abstains_on_unfamiliar_words(few_shot):
    assert few_shot.interpret("pumping iron").filled == []


def test_parse_overrides_accepts_valid_corrections(vocab):
    assert parse_overrides("genre=hip hop energy=0.4 acoustic=yes", vocab) == {
        "genre": "hip hop", "energy": 0.4, "likes_acoustic": True,
    }


@pytest.mark.parametrize("text", ["energy=7", "energy=loud", "mood=spicy", "tempo=fast", "hello"])
def test_parse_overrides_rejects_bad_values(vocab, text):
    with pytest.raises(ValueError):
        parse_overrides(text, vocab)
