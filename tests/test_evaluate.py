"""Tests for the evaluation harness itself."""

from src.agent import VibeAgent
from src.evaluate import check_case, interpreter_accuracy, load_json, run_agent_cases


def test_check_case_reports_each_failed_expectation():
    agent = VibeAgent.from_files()
    result = agent.run("happy pop songs")
    assert check_case(result, {"status": "ok", "top1": "Sunrise City", "cites": True}) == []
    failures = check_case(result, {"top1": "Gym Hero", "max_confidence": 0.1, "top1_genre": "rock"})
    assert len(failures) == 3
    assert check_case(result, {"cites": False}, skip=("cites",)) == []
    assert check_case(result, {"made_up_check": 1}) == ["unknown expectation 'made_up_check'"]


def test_check_case_handles_requests_with_no_songs():
    result = VibeAgent.from_files().run("")
    assert check_case(result, {"status": "rejected"}) == []
    assert check_case(result, {"top1": "Sunrise City"})


def test_full_system_beats_the_baseline_on_the_predefined_cases():
    cases = load_json("agent_cases.json")
    full = run_agent_cases(VibeAgent.from_files(), cases)
    base = run_agent_cases(VibeAgent.from_files(use_rag=False, use_few_shot=False), cases, skip=("cites",))
    full_passed = sum(1 for _, _, failures in full if not failures)
    base_passed = sum(1 for _, _, failures in base if not failures)
    assert full_passed > base_passed
    assert full_passed / len(cases) >= 0.9
    # Every guardrail case must pass: these are the ones that protect people.
    assert all(not failures for case, _, failures in full if case["group"] == "guardrails")


def test_few_shot_improves_on_keywords_for_held_out_requests():
    agent = VibeAgent.from_files()
    accuracy = interpreter_accuracy(agent, load_json("interpreter_test.json"))
    keyword = sum(k for k, _, _ in accuracy.values())
    few_shot = sum(f for _, f, _ in accuracy.values())
    assert few_shot > keyword
