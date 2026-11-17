"""The VibeFinder agent: plan, act, check its own work, and revise.

One request flows through these steps, and every step is recorded in a trace:

    guardrail  check_request       reject bad input before doing any work
    act        interpret_request   free text -> taste profile (keyword + few-shot)
    plan       make_plan           decide which lookups this request needs
    act        retrieve_knowledge  genre guide, mood guide, song liner notes
    act        score_catalog       knowledge-augmented scoring of every song
    check      self_check          look for conflicts and weak matches
    revise     rerank              re-rank among energy-compatible songs when energy was ignored
    guardrail  verify_output       songs exist, citations and quotes are real
    act        estimate_confidence 0 to 1 score; low scores are flagged for human review
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .guardrails import check_request, clamp_k, validate_catalog, verify_output
from .interpreter import FewShotInterpreter, Interpretation, Vocabulary, keyword_interpret, load_examples
from .knowledge import Passage, load_knowledge
from .rag_scoring import (
    Reason,
    Recommendation,
    RetrievedContext,
    max_possible_score,
    rank_with_knowledge,
)
from .recommender import load_songs, recommend_songs
from .retriever import Retriever

log = logging.getLogger("vibefinder")
log.addHandler(logging.NullHandler())  # stay quiet unless setup_logging() is called

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONGS_PATH = os.path.join(ROOT, "data", "songs.csv")
KNOWLEDGE_DIR = os.path.join(ROOT, "data", "knowledge")
EXAMPLES_PATH = os.path.join(ROOT, "data", "few_shot_examples.json")

ENERGY_CONFLICT_GAP = 0.30   # top pick this far from the requested energy counts as a conflict
WEAK_FIT = 0.5               # top pick earning under half the possible points is a weak match
FLAT_SPREAD = 0.10           # top k scores this close together means the ranking says little
GUIDE_HITS = 3               # guide passages considered when looking up a genre or mood
NOTE_HITS = 5                # liner notes retrieved per request
NOTE_MIN_SIM = 0.10          # liner notes below this similarity are ignored
NOTES_ONLY_MIN_SIM = 0.2     # with no stated taste, notes must match at least this well

HIGH_CONFIDENCE, MEDIUM_CONFIDENCE = 0.8, 0.5
UNRESOLVED_CAP = 0.45        # confidence ceiling when a self-check issue could not be fixed
# How much of the request counts as understood when 0, 1, or 2+ of genre/mood/energy were found.
COVERAGE = (0.25, 0.6, 1.0)
DEGRADED_CAP = 0.4           # confidence ceiling when output verification failed


def setup_logging(path: Optional[str] = None) -> str:
    """Write the agent's step-by-step log to a file (logs/vibefinder.log by default)."""
    path = path or os.path.join(ROOT, "logs", "vibefinder.log")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not any(isinstance(h, logging.FileHandler) for h in log.handlers):
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
    log.setLevel(logging.INFO)
    return path


@dataclass
class TraceStep:
    """One recorded step of the agent's reasoning."""

    number: int
    phase: str   # "guardrail" | "plan" | "act" | "check" | "revise"
    tool: str
    detail: str
    items: List[str] = field(default_factory=list)  # sub-items, used for the plan


@dataclass
class AgentResult:
    """Everything the agent produced for one request."""

    request: str
    status: str = "ok"   # "ok" | "needs_review" | "clarify" | "rejected" | "support" | "degraded" | "error"
    message: str = ""
    interpretation: Optional[Interpretation] = None
    plan: List[str] = field(default_factory=list)
    context: RetrievedContext = field(default_factory=RetrievedContext)
    recommendations: List[Recommendation] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)   # codes found by the self-check
    notes: List[str] = field(default_factory=list)    # plain language caveats shown to the user
    revised: bool = False
    confidence: float = 0.0
    confidence_label: str = "none"
    needs_review: bool = False
    catalog_size: int = 0
    trace: List[TraceStep] = field(default_factory=list)

    def step(self, phase: str, tool: str, detail: str, items: Sequence[str] = ()) -> None:
        """Record a trace step and mirror it to the log file."""
        self.trace.append(TraceStep(len(self.trace) + 1, phase, tool, detail, list(items)))
        log.info("%s | %s | %s", phase, tool, detail)

    @property
    def citations(self) -> List[str]:
        """Every source cited in the answer, in first-use order."""
        seen: List[str] = []
        for rec in self.recommendations:
            for reason in rec.reasons:
                if reason.citation and reason.citation not in seen:
                    seen.append(reason.citation)
        return seen


class VibeAgent:
    """Answers free text music requests over a song catalog and a knowledge base."""

    def __init__(
        self,
        songs: Sequence[Dict],
        passages: Sequence[Passage] = (),
        examples: Sequence[Dict] = (),
        use_rag: bool = True,
        use_few_shot: bool = True,
    ):
        self.songs, problems = validate_catalog(songs)
        for problem in problems:
            log.warning("catalog | dropped %s", problem)
        self.use_rag = use_rag and bool(passages)
        self.vocab = Vocabulary.build(self.songs, passages)
        self.retriever = Retriever(passages) if self.use_rag else None
        self.interpreter = FewShotInterpreter(examples, self.vocab) if (use_few_shot and examples) else None

    @classmethod
    def from_files(cls, use_rag: bool = True, use_few_shot: bool = True) -> "VibeAgent":
        """Build an agent from the project's data folder."""
        return cls(
            load_songs(SONGS_PATH),
            load_knowledge(KNOWLEDGE_DIR),
            load_examples(EXAMPLES_PATH),
            use_rag=use_rag,
            use_few_shot=use_few_shot,
        )

    # ------------------------------------------------------------------ steps

    def interpret(self, text: str) -> Interpretation:
        """Turn request text into a taste profile."""
        if self.interpreter is not None:
            return self.interpreter.interpret(text)
        return keyword_interpret(text, self.vocab)

    def _make_plan(self, interp: Interpretation) -> List[str]:
        """List the steps this particular request needs."""
        prefs = interp.prefs
        plan: List[str] = []
        if self.use_rag:
            if prefs["genre"]:
                plan.append(f"look up the genre guide for '{prefs['genre']}' (neighbors, typical energy)")
            if prefs["mood"]:
                plan.append(f"look up the mood guide for '{prefs['mood']}' (neighbors, typical energy)")
            plan.append("search the song liner notes for the wording of the request")
            if prefs["energy"] is None and (prefs["genre"] or prefs["mood"]):
                plan.append("no energy level stated, so take a typical energy from the guides")
        else:
            plan.append("knowledge retrieval is off, so use exact label matching only")
        plan.append(f"score all {len(self.songs)} songs and rank them")
        plan.append("self-check the top results and re-rank if a stated preference was ignored")
        plan.append("verify songs, citations and quotes before answering")
        return plan

    def _guide_for(self, label: str, source: str) -> Optional[Passage]:
        """Retrieve the guide passage for one genre or mood label, or None if there is none."""
        for hit in self.retriever.search(label, k=GUIDE_HITS, source=source):
            if hit.passage.title.lower() == label:
                return hit.passage
        return None

    def _retrieve(self, request: str, interp: Interpretation) -> RetrievedContext:
        """Fetch the guide passages and liner notes that apply to this request."""
        context = RetrievedContext()
        if not self.use_rag:
            return context
        prefs = interp.prefs
        # Search each guide by the label, and only trust a passage whose heading
        # is the label that was asked for (so "pop" never borrows from "indie pop").
        if prefs["genre"]:
            context.genre_passage = self._guide_for(prefs["genre"], "genres")
        if prefs["mood"]:
            context.mood_passage = self._guide_for(prefs["mood"], "moods")
        for hit in self.retriever.search(request, k=NOTE_HITS, source="song_notes", min_score=NOTE_MIN_SIM):
            if hit.passage.song_id is not None:
                context.note_hits[hit.passage.song_id] = hit
        if prefs["energy"] is None:
            for passage in (context.mood_passage, context.genre_passage):
                if passage is not None and passage.typical_energy is not None:
                    context.inferred_energy = passage.typical_energy
                    context.inferred_energy_source = passage.doc_id
                    break
        return context

    def _rank(
        self, interp: Interpretation, context: RetrievedContext, k: int, songs: Optional[Sequence[Dict]] = None
    ) -> List[Recommendation]:
        """Rank the catalog (or a subset of it) for this request."""
        return rank_with_knowledge(
            interp.prefs, self.songs if songs is None else songs, context, k=k,
            avoid_genres=interp.avoid_genres, avoid_moods=interp.avoid_moods,
        )

    def _self_check(self, recs: List[Recommendation], interp: Interpretation, context: RetrievedContext) -> List[str]:
        """Return issue codes for the current ranking."""
        issues: List[str] = []
        if not recs:
            return ["no_results"]
        prefs = interp.prefs
        top = recs[0]
        if prefs["energy"] is not None and abs(top.song["energy"] - prefs["energy"]) > ENERGY_CONFLICT_GAP:
            issues.append("energy_conflict")
        if prefs["genre"] and not any(s["genre"] == prefs["genre"] for s in self.songs):
            issues.append("genre_unavailable")
        possible = max_possible_score(prefs, context)
        if possible and top.score / possible < WEAK_FIT:
            issues.append("weak_match")
        if len(recs) >= 3 and recs[0].score - recs[-1].score < FLAT_SPREAD:
            issues.append("flat_ranking")
        return issues

    @staticmethod
    def _keeps_stated_labels(song: Dict, interp: Interpretation, context: RetrievedContext) -> bool:
        """True if the song has every genre/mood the listener stated outright, or a related one.

        Labels that were only guessed by the few-shot stage do not count, so a
        revision can never trade a stated genre away for a guessed mood.
        """
        for slot, passage in (("genre", context.genre_passage), ("mood", context.mood_passage)):
            wanted = interp.prefs[slot]
            if wanted and interp.sources.get(slot) in ("keyword", "human"):
                related = passage.related if passage is not None else []
                if song[slot] != wanted and song[slot] not in related:
                    return False
        return True

    def _confidence(self, result: AgentResult, unresolved: bool) -> float:
        """Combine how well the request was understood, how well the top song fits, and the self-check.

        confidence = 0.4 * understood + 0.4 * fit + 0.2 * agreement
        """
        interp = result.interpretation
        core = [s for s in ("genre", "mood", "energy") if interp.prefs[s] is not None]
        filled = interp.filled
        if filled:
            understood = sum(interp.confidence[s] for s in filled) / len(filled) * COVERAGE[min(len(core), 2)]
        else:
            understood = 0.0
        possible = max_possible_score(interp.prefs, result.context)
        top_score = result.recommendations[0].score if result.recommendations else 0.0
        fit = min(1.0, top_score / possible) if possible else min(1.0, top_score)
        agreement = 0.0 if unresolved else 0.5 if (result.revised or result.issues) else 1.0
        confidence = 0.4 * understood + 0.4 * fit + 0.2 * agreement
        if unresolved:
            confidence = min(confidence, UNRESOLVED_CAP)
        return round(confidence, 2)

    # -------------------------------------------------------------------- run

    def run(self, request, k: int = 3, overrides: Optional[Dict] = None) -> AgentResult:
        """Answer one request. Never raises: unexpected errors become status "error"."""
        result = AgentResult(request=request if isinstance(request, str) else "", catalog_size=len(self.songs))
        try:
            self._run(result, request, clamp_k(k), overrides or {})
        except Exception:  # last line of defence so the CLI never shows a traceback
            log.exception("agent | unexpected failure for request %r", result.request[:80])
            result.status = "error"
            result.message = "Something went wrong while handling that request. The error was logged."
            result.recommendations = []
        return result

    def _run(self, result: AgentResult, request, k: int, overrides: Dict) -> None:
        check = check_request(request)
        result.request = check.cleaned
        log.info("request | %r", check.cleaned)
        result.step("guardrail", "check_request", f"{check.code} ({len(check.cleaned)} chars)")
        if not check.ok:
            result.status = "support" if check.code == "crisis" else "rejected"
            result.message = check.message
            log.warning("guardrail | request blocked: %s", check.code)
            return

        interp = self.interpret(check.cleaned)
        for slot, value in overrides.items():
            interp.set(slot, value, "human", 1.0)
        result.interpretation = interp
        detail = interp.describe()
        if interp.neighbors:
            nearest, sim = interp.neighbors[0]
            detail += f" | nearest example: \"{nearest}\" ({sim:.2f})"
        result.step("act", "interpret_request", detail)

        result.plan = self._make_plan(interp)
        result.step("plan", "make_plan", f"{len(result.plan)} steps", result.plan)

        context = self._retrieve(check.cleaned, interp)
        result.context = context
        if self.use_rag:
            found = [p.doc_id for p in (context.genre_passage, context.mood_passage) if p is not None]
            notes = sorted(context.note_hits.values(), key=lambda h: -h.score)
            found += [f"{h.passage.doc_id} ({h.score:.2f})" for h in notes]
            result.step("act", "retrieve_knowledge", ", ".join(found) if found else "nothing relevant found")

        best_note = max((h.score for h in context.note_hits.values()), default=0.0)
        if not interp.filled and best_note < NOTES_ONLY_MIN_SIM:
            result.status = "clarify"
            result.message = (
                "I couldn't find a music preference in that. Tell me a genre, a mood, an energy level, "
                "or what you're doing, for example: 'chill lofi for studying' or 'something for the gym'."
            )
            result.needs_review = True
            result.step("check", "self_check", "no preference understood and no liner notes matched, asking the user")
            return

        recs = self._rank(interp, context, k)
        result.step("act", "score_catalog", self._summarize(recs))
        issues = self._self_check(recs, interp, context)
        result.step("check", "self_check", ", ".join(issues) if issues else "no issues")

        unresolved = False
        if "energy_conflict" in issues:
            # The top pick ignored the energy that was asked for. Try again using only
            # songs near that energy, and keep the new ranking only if its top pick still
            # fits the rest of the request and keeps the labels the listener stated.
            target = interp.prefs["energy"]
            nearby = [s for s in self.songs if abs(s["energy"] - target) <= ENERGY_CONFLICT_GAP]
            revised = self._rank(interp, context, k, songs=nearby)
            possible = max_possible_score(interp.prefs, context)
            acceptable = (
                bool(revised) and possible > 0
                and revised[0].score / possible >= WEAK_FIT
                and self._keeps_stated_labels(revised[0].song, interp, context)
            )
            if acceptable:
                result.step("revise", "rerank", f"only songs within {ENERGY_CONFLICT_GAP:.2f} of energy {target:.2f}: {self._summarize(revised)}")
                result.notes.append(
                    f"My first ranking put {recs[0].song['title']} (energy {recs[0].song['energy']:.2f}) on top "
                    f"although you asked for about {target:.2f}, so I re-ranked using only songs near that energy."
                )
                recs, result.revised = revised, True
                issues = self._self_check(recs, interp, context)
                result.step("check", "self_check", ", ".join(issues) if issues else "no issues after revision")
            else:
                unresolved = True
                best = f"best was {revised[0].song['title']} {revised[0].score:.2f}" if revised else "none found"
                result.step("revise", "rerank", f"no song near energy {target:.2f} fits the rest of the request and its stated labels ({best}), keeping the first ranking")
                allowed = [s for s in self.songs if s["genre"] not in interp.avoid_genres and s["mood"] not in interp.avoid_moods]
                closest = min(allowed or self.songs, key=lambda s: (abs(s["energy"] - target), s["title"]))
                wanted = " ".join(x for x in (interp.prefs["mood"], interp.prefs["genre"]) if x) or "that kind of song"
                result.notes.append(
                    f"Nothing in the catalog is both {wanted} and near energy {target:.2f}. The top pick matches "
                    f"your labels but not the energy; the closest song by energy alone is {closest['title']} "
                    f"({closest['genre']}, {closest['mood']}, energy {closest['energy']:.2f})."
                )

        if "genre_unavailable" in issues:
            genre = interp.prefs["genre"]
            if context.genre_passage is not None and context.genre_passage.related:
                result.notes.append(
                    f"The catalog has no {genre} songs. Using the closest genres from the guide instead: "
                    f"{', '.join(context.genre_passage.related)}."
                )
            else:
                unresolved = True
                result.notes.append(f"The catalog has no {genre} songs, so the genre could not be matched at all.")
        if "weak_match" in issues:
            unresolved = True
            result.notes.append("Even the best song is a weak match for what you asked, so treat these as rough suggestions.")
        if "flat_ranking" in issues:
            result.notes.append("These songs scored almost the same. Adding a genre or mood would sharpen the ranking.")
        if "no_results" in issues:
            unresolved = True
            result.notes.append("No songs were left after removing what you asked to avoid.")
        result.issues = issues

        problems = verify_output(recs, self.songs, context.passages(), k, interp.avoid_genres, interp.avoid_moods)
        if problems:
            # Fall back to the original exact-match recommender rather than show unverified output.
            log.error("guardrail | output failed verification: %s", "; ".join(problems))
            result.step("guardrail", "verify_output", f"FAILED ({'; '.join(problems)}), falling back to exact-match ranking")
            allowed = [s for s in self.songs if s["genre"] not in interp.avoid_genres and s["mood"] not in interp.avoid_moods]
            recs = [
                Recommendation(song, score, [Reason(text) for text in explanation.split("; ")])
                for song, score, explanation in recommend_songs(interp.prefs, allowed, k=k)
                if score > 0
            ]
            result.status = "degraded"
            result.notes.append("Part of the answer failed verification, so this is the basic exact-match ranking without sources.")
        else:
            cited = sum(1 for r in recs for reason in r.reasons if reason.citation)
            result.step("guardrail", "verify_output", f"ok ({len(recs)} songs in catalog, {cited} citations checked)")
        result.recommendations = recs

        result.confidence = self._confidence(result, unresolved)
        if result.status == "degraded":
            result.confidence = min(result.confidence, DEGRADED_CAP)
        result.confidence_label = (
            "high" if result.confidence >= HIGH_CONFIDENCE else "medium" if result.confidence >= MEDIUM_CONFIDENCE else "low"
        )
        result.needs_review = result.confidence_label == "low" or unresolved or result.status == "degraded"
        if result.status == "ok" and result.needs_review:
            result.status = "needs_review"
        result.step("act", "estimate_confidence", f"{result.confidence:.2f} ({result.confidence_label})"
                    + (", flagged for human review" if result.needs_review else ""))

    @staticmethod
    def _summarize(recs: List[Recommendation]) -> str:
        """Short "Title 4.47, Title 3.31" summary for the trace."""
        return ", ".join(f"{r.song['title']} {r.score:.2f}" for r in recs) if recs else "no songs"
