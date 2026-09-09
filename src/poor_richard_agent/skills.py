"""Deterministic almanack skill: offline access to the Poor Richard registry.

Registered under the ``nooa.skills`` entry-point group (see pyproject.toml),
so any NOOA agent can opt in without importing this module::

    from nooa.skill_registry import SkillRegistry

    self.skills = SkillRegistry(self)
    self.skills.activate(["poor-richard.almanack"])  # loads self.almanack

``PoorRichardSkill`` is a plain tool belt (no ``Agent`` inheritance) wrapping
the offline ``poor_richard`` API. It holds no shared resources, so there is
nothing to tear down. Every tool is deterministic and network-free.
"""

from __future__ import annotations

import asyncio

import poor_richard
from nooa import Skill

from poor_richard_agent.models import SearchHit


class PoorRichardSkill(Skill):
    """Offline Poor Richard almanack tools. Discover the right library for a
    factual question with ``search(query)`` (up to *top* ranked hits, each
    carrying the card's best-matched golden question and its verified answer);
    fetch the full authoritative card with ``get(card_id)`` to read every
    golden question, the pinned example, and the notes that guard against API
    drift."""

    # --- Deterministic tools: ordinary Python, callable by the model ---

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

    async def get(self, card_id: str) -> poor_richard.ReferenceCard:
        """Fetch the full authoritative card for *card_id* (a SearchHit's
        ``card_id``).

        Returns the almanack ``ReferenceCard``: its name, PyPI/import names,
        all golden questions (each with a verified expected answer), the
        pinned example snippet, and the notes recording the exact API shape to
        call. The model reads ``card.questions`` to pick the one matching the
        topic. Raises for an unknown id.
        """
        return await asyncio.to_thread(poor_richard.get, card_id)
