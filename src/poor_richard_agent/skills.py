"""Almanack skills: offline registry tools + shared library-usage memory.

Registered under the ``nooa.skills`` entry-point group (see pyproject.toml),
so any NOOA agent can opt in without importing this module::

    from nooa.skill_registry import SkillRegistry

    self.skills = SkillRegistry(self)
    self.skills.activate(["poor-richard.almanack"])  # loads self.almanack

``PoorRichardSkill`` is a plain tool belt (no ``Agent`` inheritance) wrapping
the offline ``poor_richard`` API. It holds no shared resources, so there is
nothing to tear down. Every tool is deterministic and network-free.

``PoorRichardMemorySkill`` (opt-in via ``NOOA_MEMORY=1``) mounts nooa-memory's
long-term memory as ``self.memory``: a shared SQLite store of how-to insights
about the almanack's libraries, with local embeddings and per-turn hint
injection.
"""

from __future__ import annotations

import asyncio
import os
from typing import Literal

import poor_richard
from nooa import Skill
from nooa_memory import EmbeddingConfig, MemoryConfig
from nooa_memory.memory_skill import MemorySkill

from poor_richard_agent.models import BrowseCard, CardDetail, CardQuestion, SearchHit


class PoorRichardSkill(Skill):
    """Offline Poor Richard almanack tools. The flow is two stages: classify
    with ``browse(archetype)`` (one ``BrowseCard`` per card — the *shape* of
    its golden questions, never the answers) to map a topic to the right
    library, then retrieve with ``get(card_id)`` to read every golden question
    and verified answer, the pinned example, and the notes that guard against
    API drift. ``search(query)`` is the keyword fallback (up to *top* ranked
    hits, each carrying the card's best-matched golden question and its
    verified answer) for topics that map to no clear class."""

    # --- Deterministic tools: ordinary Python, callable by the model ---

    async def browse(self, archetype: str | None = None) -> list[BrowseCard]:
        """Stage 1 — classify: survey the catalog before retrieving.

        One ``BrowseCard`` per card — all cards when *archetype* is None, only
        the cards of that question class otherwise — each carrying the *shape*
        of its golden questions (question text only, never the answers). Read
        the shapes to pick the card whose questions fit the topic, then move
        to stage 2 with ``get(card_id)``. Prefer one archetype (the valid
        values are the bracketed tags in the system-prompt catalog): the full
        catalog is large.
        """
        arch = None
        if archetype is not None:
            try:
                arch = poor_richard.Archetype(archetype)
            except ValueError as exc:
                valid = ", ".join(a.value for a in poor_richard.Archetype)
                raise ValueError(f"unknown archetype: {archetype!r} (choose from: {valid})") from exc
        cards = await asyncio.to_thread(poor_richard.browse, arch)
        return [
            BrowseCard(
                card_id=c.id,
                pypi=c.pypi,
                import_name=c.import_name,
                archetypes=[a.value for a in c.archetypes],
                questions=[q.question for q in c.questions],
            )
            for c in cards
        ]

    async def search(self, query: str, top: int = 3) -> list[SearchHit]:
        """Rank the almanack's offline libraries against *query*.

        Returns up to *top* :class:`SearchHit`, best first, each with the
        card's id, PyPI name, import name, and (when a golden question
        matched) the question text and its verified expected answer. Empty
        list when nothing clears the relevance threshold.
        """
        hits = await asyncio.to_thread(poor_richard.search, query, top=top)
        return [
            SearchHit(
                score=score,
                card_id=card.id,
                pypi=card.pypi,
                import_name=card.import_name,
                question=question.question if question is not None else None,
                expected=question.expected if question is not None else None,
            )
            for score, card, question in hits
        ]

    async def get(self, card_id: str) -> CardDetail:
        """Fetch the full authoritative card for *card_id* (a SearchHit's
        ``card_id``).

        Returns a ``CardDetail`` with these exact, stable fields (use these
        names — do not guess):
          ``card_id``, ``name``, ``pypi``, ``import_name``,
          ``questions`` (a list; each item has ``question``, ``expected``,
          ``status``), ``notes`` (API-shape guardrails, on the card — not per
          question), ``example`` (canonical snippet), ``offline``.
        Read ``card.questions`` to find the golden question matching the topic
        and use its ``expected`` as the verified answer. Raises for an unknown
        id.
        """
        card = await asyncio.to_thread(poor_richard.get, card_id)
        return CardDetail(
            card_id=card.id,
            name=card.name,
            pypi=card.pypi,
            import_name=card.import_name,
            questions=[CardQuestion(question=q.question, expected=q.expected, status=q.status) for q in card.questions],
            notes=card.notes,
            example=card.example,
            offline=card.offline,
        )


def _memory_config_from_env() -> MemoryConfig:
    """Build the memory config from the environment (registry-safe defaults).

    The llama-server router already required for the LLM serves the embedding
    model, so the litellm backend points at ``NOOA_LLM_BASE`` by default.
    Tests set ``NOOA_EMBED_BACKEND=hashing`` to stay socket-blocked.
    """
    backend: Literal["hashing", "litellm"] = (
        "hashing" if os.environ.get("NOOA_EMBED_BACKEND") == "hashing" else "litellm"
    )
    return MemoryConfig(
        enabled=True,
        path=os.environ.get("NOOA_MEMORY_PATH", ".nooa/memory/memory.sqlite"),
        owner="",
        embedding=EmbeddingConfig(
            backend=backend,
            model=os.environ.get("NOOA_EMBED_MODEL", "openai/nomic-embed-text-v1.5"),
            endpoint=os.environ.get("NOOA_LLM_BASE", "http://127.0.0.1:8080/v1"),
            api_key="local",
        ),
    )


class PoorRichardMemorySkill(MemorySkill):
    """Shared almanack library-usage memory (opt-in via ``NOOA_MEMORY=1``).

    Persists how-to insights about the almanack's libraries — import names,
    call shapes, keyword-only pitfalls, "X is not Y" corrections — in a shared
    SQLite store (unowned namespace), so every agent surface learns from every
    run. Usage knowledge only: never computed answer values. Config comes from
    the environment (zero-arg, as the skill registry requires); pass an
    explicit ``config`` in tests.
    """

    def __init__(self, config: MemoryConfig | None = None) -> None:
        super().__init__(config or _memory_config_from_env())
