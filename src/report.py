"""Turn an AgentResult into readable text for the terminal and for saved traces."""

from typing import List

from .agent import AgentResult

WIDTH = 72

STATUS_HEADLINES = {
    "rejected": "Request not accepted",
    "support": "A note before any music",
    "clarify": "I need a little more to go on",
    "error": "Something went wrong",
}


def format_trace(result: AgentResult) -> str:
    """Numbered list of every step the agent took."""
    lines = ["Agent trace"]
    for step in result.trace:
        lines.append(f"  [{step.number}] {step.phase:<9} {step.tool:<19} {step.detail}")
        for item in step.items:
            lines.append(f"{'':<36}- {item}")
    return "\n".join(lines)


def format_result(result: AgentResult, show_trace: bool = False) -> str:
    """Full answer: what was understood, the ranked songs with sources, checks, and confidence."""
    lines: List[str] = ["=" * WIDTH, f"Request:    {result.request or '(empty)'}"]

    if result.status in STATUS_HEADLINES:
        lines.append(f"Status:     {result.status}")
        lines.append("-" * WIDTH)
        lines.append(f"{STATUS_HEADLINES[result.status]}: {result.message}")
    else:
        lines.append(f"Understood: {result.interpretation.describe()}")
        lines.append("Plan:")
        for number, step in enumerate(result.plan, 1):
            lines.append(f"  {number}. {step}")
        lines.append("-" * WIDTH)
        lines.append(f"Top {len(result.recommendations)} of {result.catalog_size} songs")
        for rank, rec in enumerate(result.recommendations, 1):
            song = rec.song
            lines.append(f"{rank}. {song['title']} by {song['artist']} [{song['genre']}, {song['mood']}]  score {rec.score:.2f}")
            for reason in rec.reasons:
                cite = f" [{reason.citation}]" if reason.citation else ""
                lines.append(f"     - {reason.text}{cite}")
                if reason.quote:
                    lines.append(f"       \"{reason.quote}\"")
        lines.append("-" * WIDTH)
        if result.revised:
            lines.append("Self-check: found a problem with the first ranking and revised it")
        elif result.issues:
            lines.append(f"Self-check: {', '.join(result.issues)}")
        else:
            lines.append("Self-check: no issues")
        for note in result.notes:
            lines.append(f"Note:       {note}")
        review = "  ->  please review, I am not sure about this one" if result.needs_review else ""
        lines.append(f"Confidence: {result.confidence:.2f} ({result.confidence_label}){review}")
        if result.citations:
            lines.append(f"Sources:    {', '.join(result.citations)}")

    if show_trace:
        lines.append("-" * WIDTH)
        lines.append(format_trace(result))
    return "\n".join(lines)


def trace_to_markdown(result: AgentResult) -> str:
    """Markdown version of one run, used for the saved traces in ai_interactions.md."""
    lines = [f"### Request: \"{result.request}\"", "", "| # | Phase | Tool | What happened |", "| --- | --- | --- | --- |"]
    for step in result.trace:
        detail = step.detail + (": " + "; ".join(step.items) if step.items else "")
        lines.append(f"| {step.number} | {step.phase} | `{step.tool}` | {detail.replace('|', '/')} |")
    lines.append("")
    if result.recommendations:
        picks = ", ".join(f"{r.song['title']} ({r.score:.2f})" for r in result.recommendations)
        lines.append(f"**Final answer:** {picks}. Confidence {result.confidence:.2f} ({result.confidence_label}).")
    else:
        lines.append(f"**Final answer:** status `{result.status}`. {result.message}")
    for note in result.notes:
        lines.append(f"\n> {note}")
    return "\n".join(lines) + "\n"
