"""poor-richard-agent: a NOOA agent backed by the Poor Richard almanack.

Turns a factual question into an authoritative, offline answer by discovering
the right curated library from the almanack, calling it conventionally, and
returning a validated :class:`ResearchReport`.
"""

from poor_richard_agent.models import Answer, ResearchReport, SearchHit

__all__ = ["Answer", "ResearchReport", "SearchHit", "main"]


def main() -> None:
    print("Hello from poor-richard-agent!")
