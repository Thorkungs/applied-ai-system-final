"""End-to-end tests for the agent: request text in, checked recommendations out."""

import pytest

import src.agent as agent_module
from src.agent import VibeAgent
from src.rag_scoring import Reason, Recommendation
from src.report import format_result, trace_to_markdown


@pytest.fixture(scope="module")
def agent():
    return VibeAgent.from_files()


@pytest.fixture(scope="module")
def baseline():
    return VibeAgent.from_files(use_rag=False, use_few_shot=False)


def titles(result):
    return [r.song["title"] for r in result.recommendations]


def test_explicit_request_end_to_end(agent):
    result = agent.run("happy pop songs")
    assert result.status == "ok"
    assert titles(result)[0] == "Sunrise City"
    assert result.confidence_label == "high"
    assert [s.tool for s in result.trace][:2] == ["check_request", "interpret_request"]
    assert result.trace[-1].tool == "estimate_confidence"


def test_retrieval_changes_the_ranking(agent, baseline):
    """The 1.0 label bias: Gym Hero (pop, intense) used to beat Rooftop Lights (indie pop, happy)."""
    with_rag = titles(agent.run("happy pop songs"))
    without = titles(baseline.run("happy pop songs"))
    assert with_rag.index("Rooftop Lights") < with_rag.index("Gym Hero")
    assert "Rooftop Lights" not in without or without.index("Gym Hero") < without.index("Rooftop Lights")


def test_every_citation_points_at_a_retrieved_passage(agent):
    for request in ("happy k-pop", "rainy afternoon reading", "jazz for sunday morning coffee"):
        result = agent.run(request)
        retrieved = {p.doc_id for p in result.context.passages()}
        assert result.citations, request
        assert set(result.citations) <= retrieved, request


def test_genre_missing_from_catalog_uses_neighbors_from_the_guide(agent, baseline):
    result = agent.run("happy k-pop")
    assert "genre_unavailable" in result.issues
    assert result.recommendations[0].song["genre"] == "pop"
    assert any("k-pop" in note for note in result.notes)
    assert agent.run("happy k-pop").confidence < agent.run("happy pop songs").confidence
    assert not baseline.run("happy k-pop").citations


def test_situational_request_needs_few_shot(agent, baseline):
    assert titles(agent.run("heading to the gym for leg day"))[0] == "Gym Hero"
    assert baseline.run("heading to the gym for leg day").status == "clarify"


def test_unresolvable_conflict_is_flagged_for_review(agent):
    result = agent.run("sad folk songs but high energy")
    assert result.status == "needs_review"
    assert result.needs_review
    assert "energy_conflict" in result.issues
    assert result.confidence <= 0.5
    assert any("Storm Runner" in note for note in result.notes)
    assert "revise" in [s.phase for s in result.trace]


def test_resolvable_conflict_is_revised(agent):
    result = agent.run("pop but really calm and low energy")
    assert result.revised
    top = result.recommendations[0].song
    assert abs(top["energy"] - 0.3) <= 0.3
    assert top["genre"] in ("pop", "indie pop", "r&b", "synthwave")
    assert "energy_conflict" not in result.issues


def test_revision_never_trades_a_stated_genre_for_a_guessed_mood(agent):
    """Regression: "upbeat country" used to be revised into a pop song because of a few-shot mood guess."""
    result = agent.run("upbeat country for a road trip")
    assert result.interpretation.sources["genre"] == "keyword"
    assert result.interpretation.sources["mood"] == "few-shot"
    assert result.recommendations[0].song["genre"] == "country"
    assert not result.revised
    assert result.needs_review
    assert any("Nothing in the catalog is both" in note for note in result.notes)


def test_avoided_genre_never_appears(agent):
    result = agent.run("upbeat music, anything but pop", k=10)
    assert result.recommendations
    assert all(r.song["genre"] != "pop" for r in result.recommendations)


@pytest.mark.parametrize("request_text, status", [
    ("", "rejected"),
    ("?!?!?! 12345", "rejected"),
    ("x" * 400, "rejected"),
    ("what is the capital of France", "clarify"),
    ("I want to die, play something sad", "support"),
])
def test_blocked_requests_return_no_songs(agent, request_text, status):
    result = agent.run(request_text)
    assert result.status == status
    assert result.recommendations == []
    assert result.message


def test_k_is_clamped(agent):
    assert len(agent.run("happy pop songs", k=999).recommendations) <= 10
    assert len(agent.run("happy pop songs", k=-5).recommendations) == 1


def test_human_override_wins_over_interpretation(agent):
    result = agent.run("something for the gym", overrides={"genre": "rock"})
    assert result.interpretation.sources["genre"] == "human"
    assert titles(result)[0] == "Storm Runner"


def test_results_are_deterministic(agent):
    first, second = agent.run("studying for finals all night"), agent.run("studying for finals all night")
    assert titles(first) == titles(second)
    assert first.confidence == second.confidence


def test_confidence_is_always_between_0_and_1(agent):
    for request in ("happy pop songs", "punk", "pumping iron", "sad folk songs but high energy", "slow"):
        assert 0.0 <= agent.run(request).confidence <= 1.0


def test_failed_verification_falls_back_instead_of_showing_bad_output(agent, monkeypatch):
    """If the ranking step ever invents a song, the output guardrail must catch it."""
    def invented(*args, **kwargs):
        fake = {"id": 999, "title": "Made Up Hit", "artist": "Nobody", "genre": "pop", "mood": "happy", "energy": 0.8}
        return [Recommendation(fake, 9.9, [Reason("trust me")])]

    monkeypatch.setattr(agent_module, "rank_with_knowledge", invented)
    result = agent.run("happy pop songs")
    assert result.status == "degraded"
    assert "Made Up Hit" not in titles(result)
    assert titles(result)[0] == "Sunrise City"
    assert result.confidence <= 0.4
    assert result.needs_review


def test_unexpected_error_is_caught_and_reported(agent, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("retriever exploded")

    monkeypatch.setattr(agent, "_retrieve", boom)
    result = agent.run("happy pop songs")
    assert result.status == "error"
    assert result.recommendations == []
    assert "logged" in result.message


def test_malformed_catalog_row_is_dropped_not_fatal():
    songs = [
        {"id": 1, "title": "Good", "artist": "A", "genre": "pop", "mood": "happy", "energy": 0.8, "acousticness": 0.2},
        {"id": 2, "title": "Broken", "artist": "B", "genre": "pop", "mood": "happy", "energy": 8.0, "acousticness": 0.2},
    ]
    agent = VibeAgent(songs)
    result = agent.run("happy pop")
    assert result.catalog_size == 1
    assert titles(result) == ["Good"]


def test_report_shows_sources_and_trace(agent):
    result = agent.run("happy k-pop")
    text = format_result(result, show_trace=True)
    assert "[genres.md#k-pop]" in text
    assert "Confidence:" in text and "Agent trace" in text
    markdown = trace_to_markdown(result)
    assert "| guardrail | `verify_output` |" in markdown
