"""Offline tests for PoorRichardAgent: construction, skill wiring, state, contracts.

No real LLM and no network: construction is offline-safe, and the LLM is
injected as a no-op FakeLLMClient where a client is needed.
"""

import re
import sys
from typing import get_type_hints
from types import SimpleNamespace

import pytest
import poor_richard
from nooa.unifiedllm import FakeLLMClient

from nooa.events import BeforeTurn

from poor_richard_agent import Answer, PoorRichardAgent, _TurnTracker, main
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


def test_turn_tracker_counts_research_turns():
    tracker = _TurnTracker()
    tracker(BeforeTurn(method_name="research", strategy="codeact", generation_id="g", turn_number=1))
    tracker(BeforeTurn(method_name="research", strategy="codeact", generation_id="g", turn_number=2))
    tracker(BeforeTurn(method_name="other", strategy="codeact", generation_id="g", turn_number=9))
    tracker(object())  # unrelated events are ignored
    assert tracker.turns == 2


def test_library_catalog_rendered_once():
    # The system-prompt placeholder invokes library_catalog() every turn; the
    # catalog must be the string rendered once in __init__, not rebuilt.
    agent = PoorRichardAgent()
    assert agent.library_catalog() is agent._library_catalog
    assert agent.library_catalog() is agent.library_catalog()


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


def test_main_usage_exits_2_without_flags(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["poor-richard-agent"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "usage" in capsys.readouterr().err


def _stub_run(monkeypatch, answered: bool):
    """Replace the agent run and tracing setup with no-LLM stubs.

    Returns a namespace with ``.calls`` (topics run, in order) and
    ``.sessions`` (session IDs set, in order).
    """
    calls: list[str] = []
    sessions: list[str] = []

    async def fake_run(topic: str) -> tuple[ResearchReport, int, int]:
        calls.append(topic)
        answers = []
        if answered:
            answers = [
                Answer(
                    card_id="fake", import_name="fake", pypi="fake",
                    question=topic, expected="42",
                )
            ]
        # (report, turns, spans) — fixed 3/12 so the stderr lines are assertable
        return ResearchReport(topic=topic, answers=answers, offline=True), 3, 12

    monkeypatch.setattr("poor_richard_agent._run", fake_run)
    monkeypatch.setattr("poor_richard_agent.enable_tracing", lambda: None)
    monkeypatch.setattr(
        "poor_richard_agent.set_session",
        lambda session_id: sessions.append(session_id),
    )
    return SimpleNamespace(calls=calls, sessions=sessions)


def test_main_prompt_mode(monkeypatch, capsys):
    stub = _stub_run(monkeypatch, answered=True)
    monkeypatch.setattr(sys, "argv", ["poor-richard-agent", "--prompt", "What is 1+1?"])
    assert main() == 0
    assert stub.calls == ["What is 1+1?"]
    captured = capsys.readouterr()
    # session ID (for deep-linking into the dashboard) + per-run stats
    lines = captured.err.strip().splitlines()
    assert re.fullmatch(r"session \d{8}_\d{6}_[0-9a-f]{8}", lines[0])
    assert lines[1] == "3 turns, 12 spans (answered)"
    assert stub.sessions == [lines[0].split()[1]]
    assert '"topic": "What is 1+1?"' in captured.out


def test_main_batch_mode_runs_one_per_line(monkeypatch, capsys, tmp_path):
    batch = tmp_path / "questions.txt"
    batch.write_text("Q one\n\n  Q two  \nQ three\n", encoding="utf-8")
    stub = _stub_run(monkeypatch, answered=True)
    monkeypatch.setattr(sys, "argv", ["poor-richard-agent", "--batch", str(batch)])
    assert main() == 0
    assert stub.calls == ["Q one", "Q two", "Q three"]
    captured = capsys.readouterr()
    # one progress line per question on stderr, one JSON report per question on stdout
    for number, session_id in enumerate(stub.sessions, start=1):
        assert f"[{number}/3] " in captured.err
        assert f"(session {session_id})" in captured.err
        assert "      3 turns, 12 spans (answered)" in captured.err
    assert captured.err.count("3 turns, 12 spans") == 3
    assert "3/3 answered — 9 turns, 36 spans total" in captured.err
    assert captured.out.count('"topic":') == 3


def test_main_batch_mode_fresh_session_per_question(monkeypatch, tmp_path):
    batch = tmp_path / "questions.txt"
    batch.write_text("Q one\nQ two\n", encoding="utf-8")
    stub = _stub_run(monkeypatch, answered=True)
    monkeypatch.setattr(sys, "argv", ["poor-richard-agent", "--batch", str(batch)])
    assert main() == 0
    # each question runs under its own trace session (hooks + session are
    # re-established in the main thread before every asyncio.run)
    assert len(stub.sessions) == 2
    assert len(set(stub.sessions)) == 2
    assert all(re.fullmatch(r"\d{8}_\d{6}_[0-9a-f]{8}", s) for s in stub.sessions)


def test_main_batch_mode_exit_1_when_unanswered(monkeypatch, capsys, tmp_path):
    batch = tmp_path / "questions.txt"
    batch.write_text("Q one\nQ two\n", encoding="utf-8")
    stub = _stub_run(monkeypatch, answered=False)
    monkeypatch.setattr(sys, "argv", ["poor-richard-agent", "--batch", str(batch)])
    assert main() == 1
    assert stub.calls == ["Q one", "Q two"]
    err = capsys.readouterr().err
    assert "3 turns, 12 spans (no answer)" in err
    assert "0/2 answered — 6 turns, 24 spans total" in err


def test_main_batch_mode_continues_after_error(monkeypatch, capsys, tmp_path):
    batch = tmp_path / "questions.txt"
    batch.write_text("Q one\nQ two\n", encoding="utf-8")
    calls: list[str] = []

    async def flaky_run(topic: str) -> tuple[ResearchReport, int, int]:
        calls.append(topic)
        if "one" in topic:
            raise RuntimeError("LLM server down")
        return ResearchReport(topic=topic, offline=True), 3, 12

    monkeypatch.setattr("poor_richard_agent._run", flaky_run)
    monkeypatch.setattr("poor_richard_agent.enable_tracing", lambda: None)
    monkeypatch.setattr("poor_richard_agent.set_session", lambda session_id: None)
    monkeypatch.setattr(sys, "argv", ["poor-richard-agent", "--batch", str(batch)])
    assert main() == 1
    assert calls == ["Q one", "Q two"]  # second question still ran
    captured = capsys.readouterr()
    assert "LLM server down" in captured.err
    assert "3 turns, 12 spans (no answer)" in captured.err
    assert "0/2 answered — 3 turns, 12 spans total" in captured.err


def test_main_empty_batch_file_exits_2(monkeypatch, capsys, tmp_path):
    batch = tmp_path / "empty.txt"
    batch.write_text("\n  \n", encoding="utf-8")
    _stub_run(monkeypatch, answered=True)
    monkeypatch.setattr(sys, "argv", ["poor-richard-agent", "--batch", str(batch)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "usage" in capsys.readouterr().err


def test_main_missing_batch_file_exits_2(monkeypatch, capsys, tmp_path):
    missing = tmp_path / "nope.txt"
    _stub_run(monkeypatch, answered=True)
    monkeypatch.setattr(sys, "argv", ["poor-richard-agent", "--batch", str(missing)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "usage" in capsys.readouterr().err


def test_main_prompt_and_batch_mutually_exclusive(monkeypatch, capsys, tmp_path):
    batch = tmp_path / "questions.txt"
    batch.write_text("Q one\n", encoding="utf-8")
    _stub_run(monkeypatch, answered=True)
    monkeypatch.setattr(
        sys, "argv", ["poor-richard-agent", "--prompt", "Q one", "--batch", str(batch)]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
