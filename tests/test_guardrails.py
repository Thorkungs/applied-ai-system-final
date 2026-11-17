"""Tests for input, data and output guardrails."""

import copy

import pytest

from src.guardrails import (
    MAX_REQUEST_CHARS,
    check_request,
    clamp_k,
    validate_catalog,
    verify_output,
)
from src.knowledge import Passage
from src.rag_scoring import Reason, Recommendation

SONG = {"id": 1, "title": "Sunrise City", "artist": "Neon Echo", "genre": "pop", "mood": "happy",
        "energy": 0.82, "acousticness": 0.18}
NOTE = Passage("song_notes.md#sunrise-city", "song_notes", "Sunrise City", "Bright synth hooks. Made for commutes.", {"song_id": "1"})


def good_rec():
    return Recommendation(dict(SONG), 3.0, [Reason("liner notes match", NOTE.doc_id, "Bright synth hooks.")])


@pytest.mark.parametrize("raw, code", [
    ("", "empty"),
    ("   \n\t ", "empty"),
    (None, "empty"),
    ("?!?!?! 12345", "no_words"),
    ("x" * (MAX_REQUEST_CHARS + 1), "too_long"),
    ("I want to die, play something sad", "crisis"),
    ("chill lofi for studying", "ok"),
])
def test_check_request_codes(raw, code):
    check = check_request(raw)
    assert check.code == code
    assert check.ok == (code == "ok")
    assert check.ok or check.message


def test_check_request_strips_control_characters():
    check = check_request("happy\x00 pop\n\n2026-01-01 ERROR fake log line")
    assert check.ok
    assert "\n" not in check.cleaned and "\x00" not in check.cleaned


def test_clamp_k():
    assert clamp_k(0) == 1
    assert clamp_k(500) == 10
    assert clamp_k(4) == 4
    assert clamp_k("abc") == 3


def test_validate_catalog_drops_bad_rows_and_reports_them():
    songs = [
        dict(SONG),
        {**SONG, "id": 2, "title": "Too Loud", "energy": 1.7},
        {**SONG, "id": 3, "title": ""},
        {**SONG, "title": "Copy"},  # duplicate id 1
    ]
    valid, problems = validate_catalog(songs)
    assert [s["id"] for s in valid] == [1]
    assert len(problems) == 3
    assert "energy" in problems[0]


def test_verify_output_accepts_a_grounded_answer():
    assert verify_output([good_rec()], [SONG], [NOTE], k=3) == []


def test_verify_output_catches_a_song_that_is_not_in_the_catalog():
    fake = good_rec()
    fake.song.update(id=99, title="Totally Real Song")
    problems = verify_output([fake], [SONG], [NOTE], k=3)
    assert any("not a song in the catalog" in p for p in problems)


def test_verify_output_catches_a_source_that_was_never_retrieved():
    rec = good_rec()
    rec.reasons[0].citation = "genres.md#made-up"
    assert any("was not retrieved" in p for p in verify_output([rec], [SONG], [NOTE], k=3))


def test_verify_output_catches_a_quote_that_is_not_in_the_source():
    rec = good_rec()
    rec.reasons[0].quote = "Critics call it the best song ever written."
    assert any("quotes text that is not in" in p for p in verify_output([rec], [SONG], [NOTE], k=3))


def test_verify_output_catches_avoided_genre_duplicates_and_bad_scores():
    rec = good_rec()
    assert any("asked to avoid" in p for p in verify_output([rec], [SONG], [NOTE], k=3, avoid_genres=["pop"]))
    assert any("more than once" in p for p in verify_output([rec, copy.deepcopy(rec)], [SONG], [NOTE], k=3))
    assert any("only 1 were requested" in p for p in verify_output([rec, copy.deepcopy(rec)], [SONG], [NOTE], k=1))
    rec.score = float("nan")
    assert any("invalid score" in p for p in verify_output([rec], [SONG], [NOTE], k=3))
    rec = good_rec()
    rec.reasons = []
    assert any("no explanation" in p for p in verify_output([rec], [SONG], [NOTE], k=3))
