"""poor-richard-agent: a NOOA agent backed by the Poor Richard almanack.

Turns a factual question into an authoritative, offline answer by discovering
the right curated library from the almanack, calling it conventionally, and
returning a validated :class:`ResearchReport`.
"""

from __future__ import annotations

import asyncio
import sys

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

USAGE = "usage: poor-richard-agent <factual question>"


async def _run(topic: str) -> ResearchReport:
    """Construct the agent and run the agentic research loop on *topic*."""
    agent = PoorRichardAgent()
    return await agent.research(topic)


def main() -> int:
    """Run the agent on a topic from argv and print the validated report.

    Exit codes: 0 ok (answers found), 1 no match / research error, 2 usage.
    """
    topic = " ".join(sys.argv[1:]).strip()
    if not topic:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        report = asyncio.run(_run(topic))
    except Exception as exc:  # no LLM server reachable, research failure, etc.
        print(f"poor-richard-agent: {exc}", file=sys.stderr)
        return 1
    try:
        print(report.model_dump_json(indent=2))
    except BrokenPipeError:  # e.g. `poor-richard-agent "..." | head`
        return 0
    return 0 if report.answers else 1


if __name__ == "__main__":
    raise SystemExit(main())
