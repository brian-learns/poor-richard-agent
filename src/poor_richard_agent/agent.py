"""Poor Richard NOOA agent: an offline almanack research agent.

Builds the LLM client (``nooa_llm``) and the :class:`PoorRichardAgent` class.
The agent is a single ``nooa.Agent`` subclass: its docstring is the system
prompt, ``today`` is a model-visible state field, and ``research`` is the one
agentic (CodeAct) method, which returns a validated
:class:`poor_richard_agent.models.ResearchReport`.
"""

from __future__ import annotations

import os
from datetime import datetime

from nooa import Agent, strategy
from nooa.skill_registry import SkillRegistry
from nooa.strategies import CodeActStrategy
from nooa.unifiedllm.registry import get_llm_client

from poor_richard_agent.models import ResearchReport
from poor_richard_agent.skills import PoorRichardSkill

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
    questions using a curated set of 43 offline Python reference libraries
    (ISO codes, constants, unit conversions, calendars, market holidays,
    ephemerides, checksum validation, ...). You have NO network: every answer
    comes from the almanack's verified data, never from memory or the web.

    Workflow for research(topic):
    1. If the topic uses relative dates ("next NYSE session", "today"),
       resolve them against self.today before searching.
    2. Discover: await self.almanack.search(topic) ranks the right libraries
       (up to 3 SearchHit, each carrying the card's best-matched golden
       question and its verified answer).
    3. Verify: for the best hit, await self.almanack.get(card_id) to read the
       full card; pick the golden question that matches the topic and take its
       verified expected answer plus the card's notes/example (the pinned API
       shape to call).
    4. Return a ResearchReport: discovered (the hits), answers (verified
       Answer objects), offline=True, and a note with the recommended import
       and API shape. If nothing matches, return empty answers and explain in
       note. Never invent an answer: only report the almanack's verified
       expected values."""

    today: str

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Model-visible state: the model has no clock, so relative dates in the
        # topic are resolved against this. Weekday first (relative-date
        # resolution needs it). astimezone() so %z formats the UTC offset.
        self.today = datetime.now().astimezone().strftime("%A %Y-%m-%d %H:%M %z")
        # Opt in to the almanack skill: the entry point maps
        # "poor-richard.almanack" to PoorRichardSkill; activate() loads it and
        # exposes it to the model as self.almanack.
        self.skills = SkillRegistry(self)
        self.almanack: PoorRichardSkill
        self.skills.activate(["poor-richard.almanack"])

    # --- Agentic method: ellipsis body, run by the LLM (CodeAct loop) ---

    @strategy(CodeActStrategy())
    async def research(self, topic: str) -> ResearchReport:  # ty: ignore[empty-body]
        """Answer {topic} from the Poor Richard almanack, fully offline.
        Discover the right library with await self.almanack.search(topic), then
        fetch the full card with await self.almanack.get(card_id) and pick the
        golden question that matches. Resolve any relative date in the topic
        against self.today. Return a ResearchReport with the discovered hits,
        the verified answer(s) (question + expected + notes), offline=True, and
        a note giving the recommended import and API shape. If nothing matches,
        return no answers and explain why in note."""
        ...
