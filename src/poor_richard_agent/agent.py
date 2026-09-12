"""Poor Richard NOOA agent: an offline almanack research agent.

Builds the LLM client (``nooa_llm``) and the :class:`PoorRichardAgent` class.
The agent is a single ``nooa.Agent`` subclass: its docstring is the system
prompt, ``today`` is a model-visible state field, and ``research`` is the one
agentic (CodeAct) method, which returns a validated
:class:`poor_richard_agent.models.ResearchReport`.

Shared library-usage memory is opt-in (``NOOA_MEMORY=1``): it activates the
``poor-richard.memory`` skill, exposing ``self.memory`` (nooa-memory tools +
per-turn hint injection) without changing the default, self-contained run.
"""

from __future__ import annotations

import os
from datetime import datetime

import poor_richard
from nooa import Agent, strategy
from nooa.skill_registry import SkillRegistry
from nooa.strategies import CodeActStrategy
from nooa.unifiedllm.registry import get_llm_client

from poor_richard_agent.models import ResearchReport
from poor_richard_agent.skills import PoorRichardMemorySkill, PoorRichardSkill

# --- local LLM (llama-server router, OpenAI-compatible) ---------------------
# Construction is offline-safe: no connection is made until a turn runs, so
# building the client (and importing this module) is safe in offline tests.
LLM_MODEL = os.environ.get("NOOA_MODEL", "Qwen3.6-35B-A3B-MXFP4_MOE")
LLM_BASE = os.environ.get("NOOA_LLM_BASE", "http://127.0.0.1:8080/v1")

nooa_llm = get_llm_client(
    f"openai/{LLM_MODEL}",
    api_base=LLM_BASE,
    api_key="local",
    max_tokens=8192,
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)


class PoorRichardAgent(Agent, llm=nooa_llm):
    """You are Poor Richard, an offline almanack agent. You answer factual
    questions by discovering and calling one of the installed offline Python
    reference libraries. You have NO network: every answer comes from computing
    with these libraries (or reading their verified golden answers) — never from
    memory or the web.

    Installed libraries — `card_id [archetypes]: what it references`. Every one
    is importable in a cell: `import <import_name>` (the import name is shown
    only when it differs from card_id). This catalog is the source of truth for
    what is available — a library that is not a top search hit may still be the
    right one, so never assume a capability is unavailable from search alone.
    {self.library_catalog()}
    {self.memory_block()}
    Workflow for research(topic):
    1. If the topic uses relative dates ("next NYSE session", "today"), resolve
       them against self.today first.
    2. Discover: pick the library(ies) in the catalog whose provenance fits the
       topic. await self.almanack.search(topic) (up to 3 SearchHit) is a ranking
       helper only — it is not the full set.
    3. Verify or compute: for the chosen card, await self.almanack.get(card_id)
       returns a CardDetail (fields: card_id, name, pypi, import_name, questions
       [each question/expected/status], notes, example, offline). If a golden
       question matches the topic, use its verified expected. Otherwise read
       notes and example for the pinned API shape, `import <import_name>` in a
       cell, and compute the answer. pprint(card) before guessing any field.
    4. Return a ResearchReport: discovered (the search hits), answers (Answer
       objects: the question asked, the verified-or-computed expected, notes),
       offline=True, and a note giving the import + API shape used. If no
       library can answer, return empty answers and explain in note. Never
       invent an answer."""

    today: str

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Model-visible state: the model has no clock, so relative dates in the
        # topic are resolved against this. Weekday first (relative-date
        # resolution needs it). astimezone() so %z formats the UTC offset.
        self.today = datetime.now().astimezone().strftime("%A %Y-%m-%d %H:%M %z")
        # The system-prompt placeholder re-invokes library_catalog() on every
        # turn; the catalog is a pure function of poor_richard.CARDS (static
        # for the process lifetime), so render it once per agent instead.
        self._library_catalog = self._render_library_catalog()
        # Opt in to the almanack skill: the entry point maps
        # "poor-richard.almanack" to PoorRichardSkill; activate() loads it and
        # exposes it to the model as self.almanack.
        self.skills = SkillRegistry(self)
        self.almanack: PoorRichardSkill
        self.skills.activate(["poor-richard.almanack"])
        # Opt in to shared library-usage memory (NOOA_MEMORY=1): the
        # "poor-richard.memory" entry point maps to PoorRichardMemorySkill and
        # is exposed as self.memory. Off by default — the core run model stays
        # self-contained per run.
        if os.environ.get("NOOA_MEMORY"):
            self.memory: PoorRichardMemorySkill
            self.skills.activate(["poor-richard.memory"])

    def _render_library_catalog(self) -> str:
        """Build the catalog text: every installed library as one line
        ``card_id (import <import_name>)? [archetypes]: provenance``.

        The import name is shown only when it differs from ``card_id``.
        """
        lines = []
        for card in poor_richard.CARDS:
            archetypes = ", ".join(a.value for a in card.archetypes) or "-"
            head = card.id
            if card.import_name != card.id:
                head = f"{card.id} (import {card.import_name})"
            lines.append(f"{head} [{archetypes}]: {card.provenance}")
        return "\n".join(lines)

    def library_catalog(self) -> str:
        """The full almanack catalog, rendered once in ``__init__``.

        Injected into the system prompt via the ``{self.library_catalog()}``
        placeholder so the model sees the complete set of available libraries
        (and what each references), not just the top ``search()`` hits.
        """
        return self._library_catalog

    def memory_block(self) -> str:
        """Render the shared-memory discipline paragraph for the system prompt.

        Empty while memory is inactive, so the default agent's prompt stays
        byte-identical to the no-memory core. Injected via the
        ``{self.memory_block()}`` placeholder (mirrors
        ``{self.library_catalog()}``).
        """
        if not hasattr(self, "memory"):
            return ""
        return (
            "\nShared library-usage memory is active. self.memory holds how-to "
            "insights past runs learned about these libraries (import names, "
            'call shapes, keyword-only pitfalls, "X is not Y" corrections), '
            "tagged by card_id. Before struggling with an unfamiliar library, "
            "try self.memory.recall(topic); after learning a usage fact the "
            'hard way, store it with self.memory.remember(content, type="skill", '
            'tags=["<card_id>"]). Store only usage knowledge — never computed '
            "answer values. Recalled memories are hints, not ground truth: the "
            "card's notes/example and verified golden answers still win.\n"
        )

    # --- Agentic method: ellipsis body, run by the LLM (CodeAct loop) ---

    @strategy(CodeActStrategy())
    async def research(self, topic: str) -> ResearchReport:  # ty: ignore[empty-body]
        """Answer {topic} from the Poor Richard almanack, fully offline. Your
        system prompt lists the full catalog of installed libraries — pick the
        one(s) whose provenance fits the topic (await self.almanack.search(topic)
        is only a ranking helper; never assume a library is unavailable because
        it is not a top hit). Fetch the card with await self.almanack.get(card_id)
        (a CardDetail: card_id, import_name, pypi, questions, notes, example).
        If a golden question matches the topic, use its verified expected;
        otherwise read notes/example, `import <import_name>` in a cell, and
        compute the answer. Resolve any relative date against self.today. Return
        a ResearchReport: the search hits, the answer(s) (question asked +
        expected + notes), offline=True, and a note with the import + API shape
        used. If no library can answer, return no answers and explain in note.
        Never guess attribute names — pprint() an object you are unsure about."""
        ...
