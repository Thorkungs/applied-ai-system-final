"""Evaluation harness: run VibeFinder on predefined inputs and print a pass/fail summary.

    python -m src.evaluate            # full report
    python -m src.evaluate --strict   # exit with code 1 if any agent case fails

Three things are measured:

1. Agent cases (data/eval/agent_cases.json): each request has expectations about
   the status, the top pick, guardrail behavior and confidence.
2. The same cases with retrieval and few-shot switched off, to show what those
   two components add.
3. Interpreter accuracy (keyword baseline vs few-shot) on a development set that
   was used for tuning and on a held-out test set that was not.
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Sequence, Tuple

from .agent import ROOT, AgentResult, VibeAgent, setup_logging
from .interpreter import Interpretation, keyword_interpret

EVAL_DIR = os.path.join(ROOT, "data", "eval")
ENERGY_TOLERANCE = 0.15  # a predicted energy this close to the gold value counts as correct


def load_json(name: str) -> List[Dict]:
    """Load one evaluation file from data/eval."""
    with open(os.path.join(EVAL_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def check_case(result: AgentResult, expect: Dict, skip: Sequence[str] = ()) -> List[str]:
    """Compare one agent result with its expectations. Returns the list of failed checks."""
    failures: List[str] = []
    expect = {key: want for key, want in expect.items() if key not in skip}
    recs = result.recommendations
    titles = [r.song["title"] for r in recs]
    top = recs[0].song if recs else None

    def need_top(check: str) -> bool:
        if top is None:
            failures.append(f"{check}: no songs returned (status {result.status})")
            return False
        return True

    for key, want in expect.items():
        if key == "status":
            if result.status != want:
                failures.append(f"status {result.status}, expected {want}")
        elif key == "top1":
            if need_top(key) and top["title"] != want:
                failures.append(f"top pick {top['title']}, expected {want}")
        elif key == "top1_in":
            if need_top(key) and top["title"] not in want:
                failures.append(f"top pick {top['title']}, expected one of {want}")
        elif key == "top1_genre":
            if need_top(key) and top["genre"] != want:
                failures.append(f"top genre {top['genre']}, expected {want}")
        elif key == "top1_mood":
            if need_top(key) and top["mood"] != want:
                failures.append(f"top mood {top['mood']}, expected {want}")
        elif key == "top1_max_energy":
            if need_top(key) and top["energy"] > want:
                failures.append(f"top energy {top['energy']:.2f}, expected at most {want}")
        elif key == "top1_min_energy":
            if need_top(key) and top["energy"] < want:
                failures.append(f"top energy {top['energy']:.2f}, expected at least {want}")
        elif key == "top_contains":
            missing = [t for t in want if t not in titles]
            if missing:
                failures.append(f"missing from results: {missing}")
        elif key == "ranks_above":
            higher, lower = want
            if higher not in titles or (lower in titles and titles.index(lower) < titles.index(higher)):
                failures.append(f"{higher} should rank above {lower}")
        elif key == "excludes_genre":
            if not recs or any(r.song["genre"] == want for r in recs):
                failures.append(f"results should exist and contain no {want}")
        elif key == "min_confidence":
            if result.confidence < want:
                failures.append(f"confidence {result.confidence:.2f}, expected at least {want}")
        elif key == "max_confidence":
            if result.confidence > want:
                failures.append(f"confidence {result.confidence:.2f}, expected at most {want}")
        elif key == "cites":
            if bool(result.citations) != want:
                failures.append("expected at least one cited source" if want else "expected no citations")
        elif key == "issue":
            if want not in result.issues:
                failures.append(f"self-check did not report {want}")
        elif key == "revised":
            if result.revised != want:
                failures.append(f"revised={result.revised}, expected {want}")
        else:
            failures.append(f"unknown expectation '{key}'")
    return failures


def run_agent_cases(
    agent: VibeAgent, cases: List[Dict], skip: Sequence[str] = ()
) -> List[Tuple[Dict, AgentResult, List[str]]]:
    """Run every case through an agent and check it."""
    rows = []
    for case in cases:
        result = agent.run(case["request"], k=case.get("k", 3))
        rows.append((case, result, check_case(result, case["expect"], skip)))
    return rows


def slots_correct(interp: Interpretation, gold: Dict) -> bool:
    """True when every gold slot is right and no genre was invented."""
    prefs = interp.prefs
    for slot, want in gold.items():
        got = prefs[slot]
        if slot == "energy":
            if got is None or abs(got - want) > ENERGY_TOLERANCE:
                return False
        elif got != want:
            return False
    return "genre" in gold or prefs["genre"] is None


def interpreter_accuracy(agent: VibeAgent, cases: List[Dict]) -> Dict[str, Tuple[int, int, int]]:
    """Per group: (keyword baseline correct, few-shot correct, total)."""
    by_group: Dict[str, List[int]] = {}
    for case in cases:
        counts = by_group.setdefault(case["group"], [0, 0, 0])
        counts[0] += slots_correct(keyword_interpret(case["text"], agent.vocab), case["gold"])
        counts[1] += slots_correct(agent.interpret(case["text"]), case["gold"])
        counts[2] += 1
    return {group: tuple(counts) for group, counts in by_group.items()}


def print_agent_table(rows) -> None:
    """One line per case: verdict, status, confidence, top pick, and what failed."""
    print(f"{'case':<22}{'group':<20}{'result':<8}{'status':<14}{'conf':<6}top pick")
    print("-" * 96)
    for case, result, failures in rows:
        top = result.recommendations[0].song["title"] if result.recommendations else "-"
        verdict = "PASS" if not failures else "FAIL"
        print(f"{case['id']:<22}{case['group']:<20}{verdict:<8}{result.status:<14}{result.confidence:<6.2f}{top}")
        for failure in failures:
            print(f"{'':<22}  x {failure}")


def print_interpreter_table(title: str, accuracy: Dict[str, Tuple[int, int, int]]) -> Tuple[int, int, int]:
    """Print keyword vs few-shot accuracy per group and return the totals."""
    print(f"\n{title}")
    print(f"  {'group':<20}{'keyword only':<16}{'with few-shot':<16}")
    totals = [0, 0, 0]
    for group, (keyword, few_shot, total) in accuracy.items():
        print(f"  {group:<20}{f'{keyword}/{total}':<16}{f'{few_shot}/{total}':<16}")
        totals = [totals[0] + keyword, totals[1] + few_shot, totals[2] + total]
    keyword, few_shot, total = totals
    print(f"  {'TOTAL':<20}{f'{keyword}/{total} ({keyword / total:.0%})':<16}{f'{few_shot}/{total} ({few_shot / total:.0%})':<16}")
    return keyword, few_shot, total


def main() -> None:
    """Run all evaluations and print the report."""
    parser = argparse.ArgumentParser(description="VibeFinder evaluation harness")
    parser.add_argument("--strict", action="store_true", help="exit with code 1 if any agent case fails")
    args = parser.parse_args()

    setup_logging()
    cases = load_json("agent_cases.json")
    agent = VibeAgent.from_files()
    baseline = VibeAgent.from_files(use_rag=False, use_few_shot=False)

    print("VIBEFINDER 2.0 EVALUATION")
    print("=" * 96)
    print(f"1. Agent cases (full system), {len(cases)} predefined requests\n")
    rows = run_agent_cases(agent, cases)
    print_agent_table(rows)

    passed = sum(1 for _, _, failures in rows if not failures)
    groups: Dict[str, List[int]] = {}
    for case, _, failures in rows:
        counts = groups.setdefault(case["group"], [0, 0])
        counts[0] += not failures
        counts[1] += 1
    scored = [(r.confidence, not f) for _, r, f in rows if r.recommendations]
    conf_all = sum(c for c, _ in scored) / len(scored)
    conf_pass = [c for c, ok in scored if ok]
    conf_fail = [c for c, ok in scored if not ok]
    citations = sum(len(r.citations) for _, r, _ in rows)
    failed_verification = sum(1 for _, r, _ in rows if r.status == "degraded")

    print("\nBy group: " + ", ".join(f"{g} {p}/{t}" for g, (p, t) in groups.items()))
    print(f"Average confidence when songs were returned: {conf_all:.2f}"
          + (f" (passing cases {sum(conf_pass) / len(conf_pass):.2f}" if conf_pass else " (")
          + (f", failing cases {sum(conf_fail) / len(conf_fail):.2f})" if conf_fail else ", no failing cases)"))
    print(f"Output guardrail: {citations} cited sources across all answers, {failed_verification} answers failed verification")

    print("\n" + "=" * 96)
    print("2. Same cases with retrieval and few-shot switched off (1.0 style exact matching)")
    print("   (the baseline cannot cite sources, so 'must cite a source' checks are skipped for it)\n")
    baseline_rows = run_agent_cases(baseline, cases, skip=("cites",))
    baseline_passed = sum(1 for _, _, failures in baseline_rows if not failures)
    print(f"{'case':<22}{'full system':<14}{'baseline':<12}baseline top pick")
    print("-" * 96)
    for (case, _, failures), (_, base_result, base_failures) in zip(rows, baseline_rows):
        top = base_result.recommendations[0].song["title"] if base_result.recommendations else f"({base_result.status})"
        print(f"{case['id']:<22}{'PASS' if not failures else 'FAIL':<14}{'PASS' if not base_failures else 'FAIL':<12}{top}")

    print("\n" + "=" * 96)
    print("3. Interpreter accuracy: keyword baseline vs few-shot specialization")
    print("   (a request counts as correct only if every expected slot is right and no genre is invented)")
    dev = print_interpreter_table("Development set (used while tuning thresholds)", interpreter_accuracy(agent, load_json("interpreter_dev.json")))
    test = print_interpreter_table("Held-out test set (written after tuning, never tuned against)", interpreter_accuracy(agent, load_json("interpreter_test.json")))

    print("\n" + "=" * 96)
    print("SUMMARY")
    print(f"  Agent cases passed, full system:        {passed}/{len(cases)} ({passed / len(cases):.0%})")
    print(f"  Agent cases passed, baseline:           {baseline_passed}/{len(cases)} ({baseline_passed / len(cases):.0%})")
    print(f"  Interpreter accuracy, development set:  keyword {dev[0]}/{dev[2]} ({dev[0] / dev[2]:.0%})  ->  few-shot {dev[1]}/{dev[2]} ({dev[1] / dev[2]:.0%})")
    print(f"  Interpreter accuracy, held-out set:     keyword {test[0]}/{test[2]} ({test[0] / test[2]:.0%})  ->  few-shot {test[1]}/{test[2]} ({test[1] / test[2]:.0%})")
    print(f"  Average confidence:                     {conf_all:.2f}")

    if args.strict and passed < len(cases):
        sys.exit(1)


if __name__ == "__main__":
    main()
