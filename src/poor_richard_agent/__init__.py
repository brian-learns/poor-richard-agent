"""poor-richard-agent: a NOOA agent backed by the Poor Richard almanack.

Turns a factual question into an authoritative, offline answer by discovering
the right curated library from the almanack, calling it conventionally, and
returning a validated :class:`ResearchReport`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import override
from uuid import uuid4

from nooa.events import BeforeTurn
from nooa.tracing import enable_tracing, set_session
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider

from poor_richard_agent.agent import PoorRichardAgent
from poor_richard_agent.models import (
    Answer,
    CardDetail,
    CardQuestion,
    ResearchReport,
    SearchHit,
)

__all__ = [
    "Answer",
    "CardDetail",
    "CardQuestion",
    "PoorRichardAgent",
    "ResearchReport",
    "SearchHit",
    "main",
]


class _TurnTracker:
    """Counts the LLM turns of one research() run via BeforeTurn events."""

    def __init__(self) -> None:
        self.turns = 0

    def __call__(self, event: object) -> None:
        """Track BeforeTurn events for the research method; ignore everything else."""
        if isinstance(event, BeforeTurn) and event.method_name == "research":
            self.turns = max(self.turns, event.turn_number)


class _SpanCounter(SpanProcessor):
    """Counts ended spans so the CLI can report per-question span totals."""

    def __init__(self) -> None:
        self.count = 0

    @override
    def on_end(self, span: ReadableSpan) -> None:
        """Count the span; it is never inspected."""
        self.count += 1

    @override
    def shutdown(self) -> None:
        """No resources to release."""

    @override
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Nothing is buffered; always up to date."""
        return True


_span_counter = _SpanCounter()
_span_counter_attached = False


async def _run(topic: str) -> tuple[ResearchReport, int, int]:
    """Construct the agent and run the agentic research loop on *topic*.

    Returns the report plus the run's LLM turn count and ended-span count.
    """
    agent = PoorRichardAgent()
    tracker = _TurnTracker()
    unsubscribe = agent.event_manager.on("*", tracker)
    _span_counter.count = 0  # fresh count per run (the attached processor instance)
    try:
        report = await agent.research(topic)
        return report, tracker.turns, _span_counter.count
    finally:
        unsubscribe()


def _prepare_tracing() -> str:
    """Start a fresh trace session in the main thread and return its ID.

    ``asyncio.run`` copies the main thread's context into each new Task. NOOA's
    auto-probe normally enables tracing *inside the first task* (at agent
    construction), so the instrumentation hooks and session ID never reach the
    main thread — every later run in the same process then loses its agent
    spans, and the viewer files the stray LLM spans as ``unknown_*`` sessions.
    Enabling here (once per run, on the main thread) puts both in the context
    every subsequent ``asyncio.run`` inherits.
    """
    global _span_counter_attached
    enable_tracing()
    if not _span_counter_attached:
        provider = otel_trace.get_tracer_provider()
        if isinstance(provider, TracerProvider):
            provider.add_span_processor(_span_counter)
            _span_counter_attached = True
    session_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    set_session(session_id)
    return session_id


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="poor-richard-agent",
        description="Answer factual questions offline from the Poor Richard almanack.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt", metavar="QUESTION", help="factual question to research")
    group.add_argument(
        "--batch",
        metavar="FILE",
        help="file of questions (one per non-empty line), run in series",
    )
    return parser


def main() -> int:
    """Run the agent on a question (--prompt) or a batch file (--batch).

    Prints the validated report(s) as JSON. Exit codes: 0 ok (every question
    answered), 1 no match / research error, 2 usage (argparse).
    """
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:])
    if args.batch is not None:
        path = Path(args.batch)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            parser.error(f"cannot read {args.batch}: {exc.strerror}")
        questions = [line.strip() for line in text.splitlines() if line.strip()]
        if not questions:
            parser.error("no non-empty lines in batch file")
    else:
        prompt = args.prompt.strip()
        if not prompt:
            parser.error("empty question")
        questions = [prompt]
    batch = len(questions) > 1
    failures = 0
    total_turns = 0
    total_spans = 0
    for number, topic in enumerate(questions, start=1):
        session_id = _prepare_tracing()
        if batch:
            print(f"[{number}/{len(questions)}] {topic} (session {session_id})", file=sys.stderr)
        else:
            print(f"session {session_id}", file=sys.stderr)
        try:
            report, turns, spans = asyncio.run(_run(topic))
        except Exception as exc:  # no LLM server reachable, research failure, etc.
            print(f"poor-richard-agent: {exc}", file=sys.stderr)
            failures += 1
            continue
        try:
            print(report.model_dump_json(indent=2))
        except BrokenPipeError:  # e.g. `poor-richard-agent "..." | head`
            return 0
        status = "answered" if report.answers else "no answer"
        detail = f"{turns} turns, {spans} spans ({status})"
        print(f"      {detail}" if batch else detail, file=sys.stderr)
        total_turns += turns
        total_spans += spans
        if not report.answers:
            failures += 1
    if batch:
        print(
            f"{len(questions) - failures}/{len(questions)} answered — {total_turns} turns, {total_spans} spans total",
            file=sys.stderr,
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
