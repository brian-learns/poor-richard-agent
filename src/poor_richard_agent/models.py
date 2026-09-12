"""Validated output models for the Poor Richard almanack agent.

These pydantic models are the agent's validated-return contract. The NOOA
harness validates the object returned by ``research()`` against the
``ResearchReport`` annotation before accepting it, and ``main()`` prints it as
scriptable JSON. They are deliberately flat (plain ``str``/``float`` fields)
so the agent's output schema is not coupled to the almanack's internal
``ReferenceCard``/``Question`` dataclasses.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Answer(BaseModel):
    """An answer resolved from an almanack card: either a verified golden
    question/expected pair, or a value computed by calling the library."""

    import_name: str = Field(description="Top-level Python module to import.")
    question: str = Field(description="The question this answer resolves")
    answer: str = Field(description="answer to the researched question")
    notes: str = Field(
        default="",
        description="Card gotchas / pinned API-shape guardrails to call the library correctly.",
    )


class ResearchReport(BaseModel):
    """Validated result of a ``research()`` run."""

    topic: str = Field(description="The factual question that was researched.")
    answers: list[Answer] = Field(
        default_factory=list,
        description="Verified answers assembled from the discovered cards.",
    )
    note: str | None = Field(
        default=None,
        description="Free-form note: recommended API shape, or why no answer was found.",
    )
