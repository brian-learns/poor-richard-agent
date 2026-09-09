"""Offline tests for PoorRichardAgent: construction, skill wiring, state, contracts.

No real LLM and no network: construction is offline-safe, and the LLM is
injected as a no-op FakeLLMClient where a client is needed.
"""

import re
import sys
from typing import get_type_hints

import poor_richard
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


def test_library_catalog_lists_all_cards():
    agent = PoorRichardAgent()
    catalog = agent.library_catalog()
    lines = catalog.splitlines()
    # one line per card, each headed by its card_id (with "(import X)" when it differs)
    assert len(lines) == len(poor_richard.CARDS)
    ids = [line.split(" [")[0].split(" (import")[0] for line in lines]
    assert sorted(ids) == sorted(c.id for c in poor_richard.CARDS)
    # import name is shown only when it differs from the card_id
    assert "pysweph (import swisseph)" in catalog
    assert "pycountry (import" not in catalog


def test_system_prompt_contains_full_catalog():
    # the model must see every installed library, not just top search hits
    agent = PoorRichardAgent()
    prompt = agent._resolve_system_prompt()
    assert "{self.library_catalog()}" not in prompt  # placeholder resolved
    assert "skyfield [compute, temporal]: NASA JPL DE ephemerides" in prompt
    assert "pysweph (import swisseph) [compute]" in prompt


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
