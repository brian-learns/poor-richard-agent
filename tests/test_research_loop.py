"""Offline agentic-loop integration tests for research().

Drives the CodeAct loop with a scripted ``FakeLLMClient`` (NOOA's
capability-test pattern): the fake LLM emits ``execute_python`` tool calls that
call the ``poor_richard`` library directly and submit a ``ResearchReport`` via
``return_result``.
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
            _exec_python_resp(
                "import poor_richard\n"
                "hits = poor_richard.search('ISO 3166 France', top=3)"
            ),
            # turn 2: verify against the card and submit the validated report
            _exec_python_resp(
                "from poor_richard_agent.models import Answer, ResearchReport\n"
                "card = poor_richard.get('pycountry')\n"
                "q = card.questions[0]\n"
                "report = ResearchReport(\n"
                "    topic='ISO 3166 France',\n"
                "    answers=[Answer(import_name=card.import_name, question=q.question,\n"
                "               answer=q.expected, notes=card.notes)],\n"
                ")\n"
                "return_result(report)"
            ),
        ]
    )
    agent = PoorRichardAgent(llm=llm)
    report = asyncio.run(agent.research("ISO 3166 France"))
    assert isinstance(report, ResearchReport)
    assert report.answers[0].import_name == "pycountry"
    # Cross-check against live almanack data (the golden answer is data, not
    # a constant): the report's answer must match the card's first question.
    assert report.answers[0].answer == poor_richard.get("pycountry").questions[0].expected


def test_research_loop_two_stage_browse_then_get():
    # the encouraged path: classify via browse (shapes, no answers), retrieve
    # via get
    llm = FakeLLMClient(
        scripted_responses=[
            _exec_python_resp(
                "import poor_richard\n"
                "cards = poor_richard.browse(poor_richard.Archetype.LOOKUP)"
            ),
            _exec_python_resp(
                "from poor_richard_agent.models import Answer, ResearchReport\n"
                "card = poor_richard.get('pycountry')\n"
                "q = card.questions[0]\n"
                "report = ResearchReport(\n"
                "    topic='ISO 3166 France',\n"
                "    answers=[Answer(import_name=card.import_name, question=q.question,\n"
                "               answer=q.expected, notes=card.notes)],\n"
                ")\n"
                "return_result(report)"
            ),
        ]
    )
    agent = PoorRichardAgent(llm=llm)
    report = asyncio.run(agent.research("ISO 3166 France"))
    assert report.answers[0].import_name == "pycountry"
    assert report.answers[0].answer == poor_richard.get("pycountry").questions[0].expected


def test_research_loop_no_match_returns_empty_answers():
    llm = FakeLLMClient(
        scripted_responses=[
            _exec_python_resp(
                "import poor_richard\n"
                "from poor_richard_agent.models import ResearchReport\n"
                "hits = poor_richard.search('zzz qqq xyzzy flurble')\n"
                "return_result(ResearchReport(topic='zzz qqq xyzzy flurble',\n"
                "    answers=[], note='no card matched'))"
            )
        ]
    )
    agent = PoorRichardAgent(llm=llm)
    report = asyncio.run(agent.research("zzz qqq xyzzy flurble"))
    assert isinstance(report, ResearchReport)
    assert report.answers == []
    assert report.note == "no card matched"
