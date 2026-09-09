"""Offline tests for PoorRichardAgent: construction, skill wiring, state, contracts.

No real LLM and no network: construction is offline-safe, and the LLM is
injected as a no-op FakeLLMClient where a client is needed.
"""

import re
import sys
from typing import get_type_hints

from nooa.unifiedllm import FakeLLMClient

from poor_richard_agent import PoorRichardAgent, main
from poor_richard_agent.models import ResearchReport
from poor_richard_agent.skills import PoorRichardSkill


def test_agent_constructs_offline():
    agent = PoorRichardAgent()
    assert isinstance(agent, PoorRichardAgent)


def test_almanack_skill_is_activated():
    agent = PoorRichardAgent()
    assert isinstance(agent.almanack, PoorRichardSkill)
    assert "poor-richard.almanack" in agent.skills.activated()


def test_today_state_field():
    agent = PoorRichardAgent()
    # weekday first, then date, time, and UTC offset (e.g. "Tuesday 2026-09-08 18:06 -0700")
    assert re.match(r"^[A-Z][a-z]+ \d{4}-\d{2}-\d{2} \d{2}:\d{2} [+-]\d{4}$", agent.today)


def test_research_return_annotation_is_researchreport():
    hints = get_type_hints(PoorRichardAgent.research)
    assert hints["return"] is ResearchReport


def test_instance_llm_injection():
    # a client can be injected per-instance, overriding the class-level nooa_llm
    agent = PoorRichardAgent(llm=FakeLLMClient())
    assert isinstance(agent, PoorRichardAgent)
    assert isinstance(agent.almanack, PoorRichardSkill)


def test_main_usage_returns_2(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["poor-richard-agent"])
    assert main() == 2
    assert "usage" in capsys.readouterr().err
