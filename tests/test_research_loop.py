"""Offline agentic-loop integration tests for research().

Drives the CodeAct loop with a scripted ``FakeLLMClient`` (NOOA's
capability-test pattern): the fake LLM emits ``execute_python`` tool calls that
call the almanack skill and submit a ``ResearchReport`` via ``return_result``.
No network, no real LLM — this validates the loop wiring, the validated return,
discovery, and the no-match path.
"""

import asyncio
import json

import poor_richard
from nooa.unifiedllm import FakeLLMClient, LLMResponse, ToolCall

from poor_richard_agent import PoorRichardAgent
from poor_richard_agent.models import ResearchReport


def _exec_python_resp(code: str) -> LLMResponse:
    """A CodeAct LLM response that calls ``execute_python(code=...)``."""
    return LLMResponse(
        raw_response=None,
        content="",
        tool_calls=[ToolCall(id="c1", name="execute_python", arguments=json.dumps({"code": code}))],
        finish_reason="tool_calls",
        assistant_message={"role": "assistant", "content": ""},
    )


def test_research_loop_discovers_and_answers():
    llm = FakeLLMClient(
        scripted_responses=[
            # turn 1: discover the right library
            _exec_python_resp("hits = await self.almanack.search('ISO 3166 France', top=3)"),
            # turn 2: verify against the card and submit the validated report
            _exec_python_resp(
                "from poor_richard_agent.models import Answer, ResearchReport\n"
                "card = await self.almanack.get('pycountry')\n"
                "q = card.questions[0]\n"
                "report = ResearchReport(\n"
                "    topic='ISO 3166 France',\n"
                "    discovered=list(hits),\n"
                "    answers=[Answer(card_id=card.card_id, import_name=card.import_name, pypi=card.pypi,\n"
                "               question=q.question, expected=q.expected, notes=card.notes)],\n"
                "    offline=True,\n"
                ")\n"
                "return_result(report)"
            ),
        ]
    )
    agent = PoorRichardAgent(llm=llm)
    report = asyncio.run(agent.research("ISO 3166 France"))
    assert isinstance(report, ResearchReport)
    assert report.offline is True
    assert report.discovered[0].card_id == "pycountry"
    assert report.answers[0].card_id == "pycountry"
    # Cross-check against live almanack data (the golden answer is data, not
    # a constant): the report's expected must match the card's first question.
    assert report.answers[0].expected == poor_richard.get("pycountry").questions[0].expected


def test_research_loop_no_match_returns_empty_answers():
    llm = FakeLLMClient(
        scripted_responses=[
            _exec_python_resp(
                "from poor_richard_agent.models import ResearchReport\n"
                "hits = await self.almanack.search('zzz qqq xyzzy flurble')\n"
                "return_result(ResearchReport(topic='zzz qqq xyzzy flurble', discovered=list(hits),\n"
                "    answers=[], offline=True, note='no card matched'))"
            )
        ]
    )
    agent = PoorRichardAgent(llm=llm)
    report = asyncio.run(agent.research("zzz qqq xyzzy flurble"))
    assert isinstance(report, ResearchReport)
    assert report.answers == []
    assert report.offline is True
