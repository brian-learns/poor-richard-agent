"""Offline tests for the opt-in shared memory skill (nooa-memory).

All tests run with the network blocked (tests/conftest.py), so the memory
paths under test use the deterministic HashingEmbedder
(``NOOA_EMBED_BACKEND=hashing``) — a PASS means correct *and* offline. The
litellm config is asserted without any network call.
"""

from __future__ import annotations

import pytest
from nooa.events import BeforeTurn, Task
from nooa_memory import ForgetPolicy, Memory, MemoryStore, MemoryType
from nooa_memory.forgetting import ForgettingEngine

from poor_richard_agent import PoorRichardAgent
from poor_richard_agent.skills import PoorRichardMemorySkill, _memory_config_from_env

TOOLS = ("remember", "recall", "search", "update_memory", "forget", "associate", "deref")


@pytest.fixture
def memory_env(monkeypatch, tmp_path):
    """Memory on, hashing embedder, store in a temp dir (offline-safe)."""
    monkeypatch.setenv("NOOA_MEMORY", "1")
    monkeypatch.setenv("NOOA_EMBED_BACKEND", "hashing")
    monkeypatch.setenv("NOOA_MEMORY_PATH", str(tmp_path / "memory.sqlite"))
    return tmp_path


def test_memory_off_by_default(monkeypatch):
    monkeypatch.delenv("NOOA_MEMORY", raising=False)
    agent = PoorRichardAgent()
    assert not hasattr(agent, "memory")
    assert agent.skills.activated() == ["poor-richard.almanack"]
    prompt = agent._resolve_system_prompt()
    assert "Shared library-usage memory" not in prompt
    assert "{self.memory_block()}" not in prompt  # placeholder resolved to ""
    assert "memory_system" not in agent.context_manager


def test_memory_skill_activation(memory_env):
    agent = PoorRichardAgent()
    assert hasattr(agent, "memory")
    assert "poor-richard.memory" in agent.skills.activated()
    for tool in TOOLS:
        assert callable(getattr(agent.memory, tool, None)), tool
    # schema guide injected with the self.memory. prefix (not self.)
    guide = agent.context_manager["memory_system"]
    assert "self.memory.remember" in guide
    assert "self.remember(" not in guide
    # discipline paragraph rendered into the system prompt
    prompt = agent._resolve_system_prompt()
    assert "Shared library-usage memory is active" in prompt
    assert "never computed answer values" in prompt
    # store created at the configured path
    assert (memory_env / "memory.sqlite").exists()


def test_remember_recall_roundtrip(memory_env):
    agent = PoorRichardAgent()
    agent.memory.remember(
        "pycountry: lookup by code is pycountry.countries.get(alpha_3='FRA'), not get_name",
        type="skill",
        tags=["pycountry", "iso3166"],
    )
    hits = agent.memory.recall("pycountry alpha-3 code", k=3)
    assert any("pycountry" in m.content for m in hits)


def test_shared_namespace_visibility(memory_env):
    # owner="" writes are visible to every reader scope
    agent = PoorRichardAgent()
    agent.memory.remember("iso639: import iso639, not python_iso639", type="skill", tags=["iso639"])
    assert agent.memory.recall("iso639 import name", k=3, owner=None)
    assert agent.memory.recall("iso639 import name", k=3, owner="*")


def test_config_defaults(monkeypatch):
    for var in ("NOOA_MEMORY_PATH", "NOOA_EMBED_BACKEND", "NOOA_EMBED_MODEL", "NOOA_LLM_BASE"):
        monkeypatch.delenv(var, raising=False)
    cfg = _memory_config_from_env()
    assert cfg.enabled is True
    assert cfg.owner == ""  # shared namespace
    assert cfg.path == ".nooa/memory/memory.sqlite"
    assert cfg.embedding.backend == "litellm"
    assert cfg.embedding.model == "openai/nomic-embed-text-v1.5"
    assert cfg.embedding.endpoint == "http://127.0.0.1:8080/v1"
    assert cfg.embedding.api_key == "local"


def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("NOOA_EMBED_BACKEND", "hashing")
    monkeypatch.setenv("NOOA_MEMORY_PATH", "/tmp/elsewhere/memory.sqlite")
    monkeypatch.setenv("NOOA_EMBED_MODEL", "openai/other-embedder")
    monkeypatch.setenv("NOOA_LLM_BASE", "http://127.0.0.1:9999/v1")
    cfg = _memory_config_from_env()
    assert cfg.embedding.backend == "hashing"
    assert cfg.path == "/tmp/elsewhere/memory.sqlite"
    assert cfg.embedding.model == "openai/other-embedder"
    assert cfg.embedding.endpoint == "http://127.0.0.1:9999/v1"


def test_skill_instantiation_zero_arg(monkeypatch):
    # SkillRegistry.load() instantiates with no args; that must be offline-safe
    # (config only — the manager/embedder are built at attach, not construction)
    monkeypatch.delenv("NOOA_EMBED_BACKEND", raising=False)
    skill = PoorRichardMemorySkill()
    # mounting as a skill rewrites the tool prefix so the guide is accurate
    assert skill._config.api_prefix == "self.memory."


def test_skill_type_is_decay_protected(tmp_path):
    store = MemoryStore(str(tmp_path / "m.sqlite"), embedding_dim=256)
    engine = ForgettingEngine(store, ForgetPolicy())
    assert engine.is_protected(Memory(content="how-to", type=MemoryType.SKILL))
    assert not engine.is_protected(Memory(content="fact", type=MemoryType.INFO, importance=5.0))
    # high-importance memories are also protected
    assert engine.is_protected(Memory(content="fact", type=MemoryType.INFO, importance=8.0))


def test_dead_embedder_cannot_break_turn(memory_env):
    # Invariant: a dead embedder degrades spontaneous injection for a turn;
    # it never breaks the agent loop (event-handler exceptions are swallowed).
    agent = PoorRichardAgent()

    class _BrokenEmbedder:
        dim = 256

        def embed(self, text: str):
            raise RuntimeError("embedder down")

        def embed_batch(self, texts: list[str]):
            raise RuntimeError("embedder down")

    agent.memory._memory_or_raise().embedder = _BrokenEmbedder()
    # a Task event gives the 'last_message' query strategy something to embed —
    # without it the hook returns early and the broken embedder is never reached
    agent.event_manager.add(Task(prompt="ISO 3166-1 alpha-3 code for France"))
    agent.event_manager.add(
        BeforeTurn(method_name="research", strategy="codeact", generation_id="g1", turn_number=1)
    )  # must not raise
    assert "recalled_memories" not in agent.context_manager  # injection just missing
