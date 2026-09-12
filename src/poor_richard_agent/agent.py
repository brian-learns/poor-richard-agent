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

import poor_richard  # noqa: F401
from nooa import Agent, strategy
from nooa.strategies import CodeActStrategy
from nooa.unifiedllm.registry import get_llm_client

from poor_richard_agent.models import ResearchReport

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
    with these libraries — never from memory or the web.

    poor_richard.pra holds available reference libraries

    poor_richard.search() provides a keword search of the reference libraries

    If the topic uses relative dates ("next NYSE session", "today"), resolve
       them against self.today.

    Return a ResearchReport: discovered (the search hits, if you searched),
       answers (Answer objects: the question asked, the verified-or-computed
       expected, notes), offline=True, and a note giving the import + API
       shape used. If no library can answer, return empty answers and explain
       in note. Never invent an answer."""

    today: str

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.today = datetime.now().astimezone().strftime("%A %Y-%m-%d %H:%M %z")

    # --- Agentic method: ellipsis body, run by the LLM (CodeAct loop) ---

    @strategy(CodeActStrategy())
    async def research(self, topic: str) -> ResearchReport:  # ty: ignore[empty-body]
        """Answer {topic}"""
        ...
