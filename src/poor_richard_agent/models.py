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


class SearchHit(BaseModel):
    """One ranked card from an almanack search.

    Carries the library identity (card id, PyPI name, import name) plus the
    card's best-matched golden question and its verified answer, flattened to
    plain strings.
    """

    score: float = Field(description="Relevance score from poor_richard.search; higher is better.")
    card_id: str = Field(description="Stable card slug; the key for PoorRichardSkill.get().")
    pypi: str = Field(description="PyPI distribution name of the underlying library.")
    import_name: str = Field(description="Top-level Python module to import.")
    question: str | None = Field(
        default=None,
        description="The card's golden question best matching the query, if one matched.",
    )
    expected: str | None = Field(
        default=None,
        description="Verified expected answer for the matched question, if one matched.",
    )


class BrowseCard(BaseModel):
    """One card from a stage-1 catalog survey: the library identity plus the
    *shape* of its golden questions — the question text only, never the
    answers. This is what ``PoorRichardSkill.browse()`` returns; the answers
    are the retrieve stage (``get(card_id)``)."""

    card_id: str = Field(description="Stable card slug; the key for PoorRichardSkill.get().")
    pypi: str = Field(description="PyPI distribution name of the underlying library.")
    import_name: str = Field(description="Top-level Python module to import.")
    archetypes: list[str] = Field(description="Question classes this card answers (e.g. 'lookup').")
    questions: list[str] = Field(description="The shape of each golden question (text only, no answers).")


class CardQuestion(BaseModel):
    """One golden question from a card: the question and its verified answer."""

    question: str = Field(description="The golden question an agent might ask.")
    expected: str = Field(description="The verified expected answer (source of truth).")
    status: str = Field(default="candidate", description="'verified' or 'candidate'.")


class CardDetail(BaseModel):
    """The full authoritative card for one library, flattened to documented,
    stable field names. This is what ``PoorRichardSkill.get()`` returns;
    ``card_id`` matches ``SearchHit.card_id`` so the model can rely on the names.
    """

    card_id: str = Field(description="Stable card slug (matches SearchHit.card_id).")
    name: str = Field(description="Human-readable library name.")
    pypi: str = Field(description="PyPI distribution name.")
    import_name: str = Field(description="Top-level Python module to import.")
    questions: list[CardQuestion] = Field(description="All golden questions; each item has question, expected, status.")
    notes: str = Field(default="", description="Gotchas / pinned API-shape guardrails for calling the library.")
    example: str = Field(default="", description="Canonical usage snippet at the pinned version.")
    offline: bool = Field(default=True, description="Works with no network.")


class Answer(BaseModel):
    """An answer resolved from an almanack card: either a verified golden
    question/expected pair, or a value computed by calling the library."""

    card_id: str = Field(description="Stable card slug the answer came from.")
    import_name: str = Field(description="Top-level Python module to import.")
    pypi: str = Field(description="PyPI distribution name of the underlying library.")
    question: str = Field(
        description="The question this answer resolves: a matching golden question, or the topic phrased as the question asked of the library."
    )
    expected: str = Field(description="The verified expected answer, or the value computed by calling the library.")
    notes: str = Field(
        default="",
        description="Card gotchas / pinned API-shape guardrails to call the library correctly.",
    )


class ResearchReport(BaseModel):
    """Validated result of a ``research()`` run.

    What the search discovered and the verified answers assembled from the
    almanack. ``offline`` records that the run made no network calls.
    """

    topic: str = Field(description="The factual question that was researched.")
    discovered: list[SearchHit] = Field(
        default_factory=list,
        description="Ranked cards the search surfaced; empty when nothing matched.",
    )
    answers: list[Answer] = Field(
        default_factory=list,
        description="Verified answers assembled from the discovered cards.",
    )
    offline: bool = Field(description="True when the run made no network calls (always expected True).")
    note: str | None = Field(
        default=None,
        description="Free-form note: recommended API shape, or why no answer was found.",
    )
