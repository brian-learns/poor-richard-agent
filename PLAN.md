# Plan: `poor-richard-agent` — a NOOA agent backed by the Poor Richard almanack

**Status:** Complete — Phases 0–5 done (scaffold, skill+models, agent, CLI/docs, offline tests, tooling/release)
**Date:** 2026-07-24
**Goal:** Build `poor-richard-agent`, a NVIDIA Object-Oriented Agents (NOOA) agent that turns a factual question into an **authoritative, offline answer** by discovering the right curated Python library from the Poor Richard almanack, calling it conventionally, and returning a validated result.

The plan follows the NOOA design principles and the reference NOOA agents (`ccnget-agent`, `xng-agent`) in this workspace, and is consistent with the Poor Richard almanack's own golden-question test method, personas, and test plan.

---

## 1. Purpose & Objective

`poor-richard-agent` is a NOOA agent that answers factual questions using the **Poor Richard** almanack — a curated set of 43 offline Python libraries (ISO codes, constants, conversions, calendars, ephemerides, checksum validation, etc.).

Its value proposition, distilled:

1. **Discovery** — given a factual question with *no library hint*, the agent finds the right library via the almanack's `search()` API (or the skill's `search` tool).
2. **Conventional, verified calls** — the agent retrieves the card's golden question and verified expected answer, and calls the library's pinned API shape (recorded in the card's `example`/`notes` for API-drift guardrails).
3. **Validated, structured output** — the agentic method returns a pydantic `ResearchReport` that the NOOA harness type-validates; the CLI prints it as clean, scriptable JSON.
4. **Offline-first & sandbox-safe** — the almanack is fully offline; the agent never fetches at runtime (one-time data fetch is handled by the almanack's `scripts/`, documented and skippable in tests).
5. **NOOA-native** — a single Python class extending `nooa.Agent`, deterministic tools as a `Skill` registered under the `nooa.skills` entry point, docstrings-as-prompt-material, async execution with timeout-bounded, cleaned-up resource handling.

---

## 2. Reference Materials Reviewed

### 2.1 NVIDIA OO Agents paper — `./2607.20709.md` (arXiv 2607.20709)

- **Agent-as-a-Python-object model:** an agent is a Python class. Methods are the model-facing actions; fields are model-visible state; docstrings are the prompt; type annotations are contracts. (`agent.py`)
- **Design principles P1–P5** (§2): *Reuse Python abstractions*; *Reframe agentic loops as method calls*; *Move deterministic work out of the agentic loop*; *Unlock the model's existing Python knowledge* (code as action, ordinary Python); *Expose the harness as explicit APIs*.
- **Agent loop** (§3): CodeAct strategy (`...` body = LLM loop) with `@strategy(...)` decorator; Predict strategy for single-shot extraction; context rendering; pass-by-reference (bounded previews, full objects bound locally); executing Python in a Jupyter-like session; typed event/state updates; validated return; long-term memory; harness APIs.
- **Evaluation** (§4): capability tests (interface fluency), agentic benchmarks (SWE-bench, Terminal-Bench, CyberGym, ARC-AGI-3), validated termination, context efficiency.
- **Harness comparison** (§5) and **related work** (§6): the field converges on six harness-interface patterns; NOOA is the reference implementation.

### 2.2 NOOA framework & reference agents

- **NOOA framework** (`./labs-OO-Agents/`, via the `labs-OO-Agents` symlink): `nooa.Agent` base class (`Agent.__init__`/`__init_subclass__` with `llm=` config; class docstring becomes the system prompt via `_resolve_system_prompt`; context blocks, event manager, runtime; `AgentMeta` metaclass), `nooa.strategies.CodeActStrategy` / `PredictStrategy`, `nooa.skill.Skill` base class, `nooa.skill_registry.SkillRegistry` (discover/load/activate entry points; attribute name derived from the entry-point name's last dot-segment, `-`→`_`; `self.skills.activate([...])` exposes skills to the model), `nooa.unifiedllm.registry.get_llm_client`.
- **`ccnget-agent`** (`./ccnget-agent/`, via the symlink) — the canonical minimal NOOA agent: single class `CcngetSkill(Skill)` (plain tool belt, no `Agent` inheritance) with async deterministic tools delegating to `ccnget`, typed return dataclasses (`Capture`, `ArticleNote`), `SkillRegistry(self).activate(["ccnget.archive"])`, `asyncio.to_thread` for blocking calls, timeout-bounded ops, shared resource cleanup in `finally`, `today` state field, validated return models, `nooa.skills` entry point, console script, tooling config (ruff/bandit/ty/vulture/refurb/interrogate).
- **`xng-agent`** (`./xng-agent/`, via the symlink) — async NOOA agent (`XngBrowserAgent(Agent, llm=nooa_llm)`) with `@strategy(CodeActStrategy())` agentic `research` method returning a pydantic `ResearchReport`; `WebResearchSkill(Skill)` with async tools + `asyncio.to_thread` + timeout-bounded browser ops + shared-session lock + `_kill_browser()` cleanup; `SkillRegistry(self).activate(["xng.web"])`; class-level `llm=` + `_run()` via `asyncio.run()` with `finally` cleanup; `today` state field; validated JSON output from `main()`; same tooling/testing config; tests use fakes (no browser/network/LLM).

### 2.3 The Poor Richard almanack project — `./poor-richard/`

- **`src/poor_richard/`** — machine-readable `registry.py` (`ReferenceCard`, `Question`, `Archetype`, `UpdateModel`, `search()`, `get()`, `by_pypi()`, `CARDS` — 43 cards, all offline-verified; schema enforces unique ids, importability, verified-question↔test linkage, pyproject↔card sync); `__init__.py` (`search`, `get`, `CARDS`, `main` CLI: `--help`, `--example`, `--ask`); golden-question tests under `tests/` with an autouse `no_network` fixture (socket-blocked — a PASS = correct *and* offline); `scripts/fetch_financedatabase.py` for the one-time data-dependent card.
- **`docs/reference-cards.md`** — question archetypes, evaluation axes (provenance, update model, offline integrity, coverage, precision, LLM output shape, footprint, license), card schema, golden-question test method, card table, candidates, gotchas.
- **`docs/personas.md`** — Noah (NOOA agent), Hank (shell + skills), Broman (human): three consumption surfaces; feature × persona matrix. **Noah is the NOOA agent** — the primary consumer of the almanack API.
- **`docs/future-directions.md`** — tentative proposals; **§3 (Notebook-style agent harnesses) identifies NOOA as the leading framework** for this almanack; the agent's Python API is the primary interface (CLI secondary), the 43 libraries must be importable, offline-first fits NOOA's sandboxing.
- **`docs/test_plan.md`** — real-agent testing (Noah/Hank/Broman, T1–T8 tasks, scoring grid: Correct / Conventional / Discovered / Offline), known hazards, cold-vs-warm SKILL.md A/B, execution notes.
- **`src/poor_richard/.agents/skills/poor-richard/SKILL.md`** — hax/agents-convention skill (shipped in package): `--ask`→`--example` pipeline, gotchas; the discovery mechanism for session-based consumers.
- **`pyproject.toml`** — `requires-python >=3.14`, `uv_build`, console script, 43 deps, dev group.

### 2.4 `poor-richard/docs/test_plan.md`

- Testers: **Noah** (NOOA CodeAct agent — persistent Python session, `call python` / `return result`; imports found by importing), **Hank** (hax-style terminal agent — commands + files only, `uv run`), **Broman** (human).
- Ground rules: fresh session, no library hint, golden values as source of truth; network noted per run.
- Scoring grid and "why-failed" deliverable feed the keyword field and card-text discipline.

---

## 3. NOOA Best Practices Extracted for This Agent

These principles are the normative constraints for `poor-richard-agent`.

### 3.1 Agent-as-a-Python-object
- One class extending `nooa.Agent` (`class PoorRichardAgent(Agent, llm=nooa_llm)`).
- Methods = model actions; fields = model-visible state; **docstrings = prompt**; **type annotations = contracts**.
- The **class docstring becomes the system prompt** (`_resolve_system_prompt`), so the agent's identity/workflow is self-describing — this is the NOOA-native way to ship agent instructions (no separate prompt file).

### 3.2 Design principles (P1–P5)
- **P1 Reuse Python abstractions** — use classes, methods, fields, type annotations, `asyncio`, exceptions, control flow; no bespoke DSL.
- **P2 Reframe agentic loops as typed method calls** — `research(topic: str) -> ResearchReport` with typed input/output, not text-only exchange; pass-by-reference.
- **P3 Move deterministic work out of the agentic loop** — the skill tools are plain async Python methods (not agentic); only `research` is the LLM loop. The model discovers/calls via code, not tool-call templates.
- **P4 Unlock the model's existing Python knowledge** — the agent's tools are ordinary callable methods the model calls by name; docstrings on the public surface (class, methods, skill) guide the model to use them directly.
- **P5 Expose the harness as explicit APIs** — skills are explicit, documented, registered capabilities (`nooa.skills` entry point); context/state/events are the framework's APIs; we surface our almanack data through typed, documented tool methods.

### 3.3 Strategies, loop, and validated return
- Agentic methods use `@strategy(CodeActStrategy())` with a `...` body; the return annotation is the **validated output contract**.
- Optional `PredictStrategy()` only if a single-shot extraction is ever needed (not for the multi-step `research`).
- The NOOA harness validates the returned pydantic model against the annotation → validated termination (prevents unsupported completion declarations).
- `main()` prints the validated model as JSON (clean, scriptable stdout) with explicit exit codes.

### 3.4 Deterministic tools & skills (entry-point registration)
- Tools live in a `PoorRichardSkill(Skill)` — plain Python, no `Agent` inheritance, mirroring `ccnget.CcngetSkill` / `xng.WebResearchSkill`.
- Registered under the **`nooa.skills`** entry-point group in `pyproject.toml`.
- Agent opts in via `SkillRegistry(self).activate(["poor-richard.almanack"])` → skill exposed to the model as `self.almanack` (attribute name = entry-point name's last dot-segment).
- Skill tools are **deterministic and offline** (wrap the almanack's offline API; `no_network`-safe).

### 3.5 State, context, and docstrings-as-prompt-material
- `today` state field (weekday/date/time + UTC offset) visible to the model for relative-date resolution (e.g. "next NYSE session") — mirrors `xng-agent`'s pattern.
- Rich, model-ready docstrings on the class, methods, and skill (they are prompt material; Noah reads them — see personas.md: "(3) Docstrings on the public surface, because NOOA renders them as prompts").
- Shared mutable state (if any) guarded where concurrent calls occur; per the almanack's design, no persistent memory is needed — each run is self-contained (no memory, no sub-agent) like `ccnget-agent`/`xng-agent`.

### 3.6 Async execution & resource hygiene
- `main()` drives via `asyncio.run()` (NOOA methods are async).
- Blocking calls (e.g. data access) wrapped in `asyncio.to_thread`.
- Every external/resource operation **timeout-bounded** (`asyncio.wait_for`) — no hung sessions.
- Shared resources (any cache/state) **torn down in `finally`** — no orphans.
- **Offline-first:** no network egress at runtime; the one-time `financedatabase` fetch is a documented script + skip in tests.

### 3.7 Testing
- All tests run with network blocked (`no_network` autouse fixture, adapted from `poor-richard`'s `conftest.py`) — a pass means correct *and* offline.
- **Deterministic tool tests** (fakes where needed, no network/LLM) — primary, high-value, mirroring `xng-agent/tests/` style.
- **Agent construction / skill activation / state / return-type** tests.
- **Agentic loop integration tests** with a mocked LLM following NOOA's capability-test pattern — validates discovery, answer retrieval, validated return, no-match, and error handling. (Complexity is noted in §6.)
- Tests ship inside the package so the wheel works (`uv build`).

### 3.8 Tooling & quality standards (mirror `xng-agent`/`ccnget-agent`)
- `pyproject.toml` with `nooa.skills` entry point, `poor-richard-agent` console script, dev dependency group (`bandit`, `nooa-cli`, `nooa[viewer]`, `pytest`, `refurb`, `ruff`, `ty`, `vulture`).
- **ruff** (E/F/B/S/I/N/RUF, line-length 120, ignore S101/E501), **bandit** (security skips), **ty** (type-check, `all = "error"`), **vulture** (dead code), **refurb** (formatting), **interrogate** (docstring coverage ≥90%, exclude tests).
- A **hax/agents-convention SKILL.md** documenting the workflow for session-based consumers (consistent with `poor-richard`'s convention); the NOOA-native mechanism is the entry-point skill + docstrings.

---

## 4. Target Design

### 4.1 Goals & constraints
- **Minimal, NOOA-native:** no shell tools, no todo list, no memory, no sub-agent — a focused factual-answer agent (aligns with the almanack's purpose and NOOA's P3/P4).
- **Offline-first:** the agent leverages the almanack's offline data; no runtime network calls.
- **NOOA-compatible:** must construct and run under the installed `nooa` (0.0.10).
- **Scriptable, validated output:** clean JSON stdout + exit codes.
- **Testable offline:** all tests network-blocked.

### 4.2 Package structure

```
poor-richard-agent/
├── pyproject.toml                 # project, nooa.skills entry point, tooling/quality config
├── README.md                      # usage, personas, prerequisites, offline note
├── .gitignore
├── src/
│   └── poor_richard_agent/
│       ├── __init__.py            # exports: Agent, ResearchReport, Answer, SearchHit, main
│       ├── agent.py               # PoorRichardAgent(Agent): agentic research() + tool wiring + today state
│       ├── skills.py              # PoorRichardSkill(Skill): deterministic search/get/find tools
│       ├── models.py              # pydantic: SearchHit, Answer, ResearchReport
│       └── .agents/skills/poor-richard-agent/
│           └── SKILL.md           # hax-convention workflow doc (session-based consumers)
├── tests/
│   ├── conftest.py                # no_network autouse fixture (socket block)
│   ├── test_skills.py             # offline deterministic tool tests (fakes/almanack data)
│   ├── test_agent.py              # construction, skill activation, today state, return type
│   └── test_research_loop.py      # agentic loop integration (mocked LLM, offline)
└── scripts/                       # (data-dependent fetch scripts if needed; almanack ships its own)
```

> Note: this is a **separate** package from the almanack (`poor_richard`); it depends on `poor-richard` and `nooa`.

### 4.3 Agent class — `PoorRichardAgent(Agent, llm=nooa_llm)` (`src/poor_richard_agent/agent.py`)

- **`nooa_llm`** (module-level, `agent.py`) — the plan references it throughout but it must be defined: build via `nooa.unifiedllm.registry.get_llm_client(f"openai/{LLM_MODEL}", api_base=LLM_BASE, api_key="local", max_tokens=8192)`, with `LLM_MODEL`/`LLM_BASE` from env (`NOOA_MODEL`/`NOOA_LLM_BASE`, defaulting to the local llama-server). Mirrors `ccnget-agent` (`__init__.py:40-50`). Construction is offline-safe (no connection until a turn actually runs), so it is safe to build in tests.
- **Class docstring** = system prompt: describes the agent's role as the Poor Richard almanack agent, the workflow (discover via `self.almanack.search` → verify via `self.almanack.get` → return validated report), the offline guarantee, and the tool surface.
- **`__init__`** (`llm=nooa_llm`, `*`-only):
  - Sets `self.today` (state field, formatted weekday/date/time+offset — mirrors `xng-agent`).
  - `self.skills = SkillRegistry(self)`.
  - `self.skills.activate(["poor-richard.almanack"])` → skill exposed as `self.almanack`.
  - (NOOA `Agent.__init__` sets up context/events/runtime — inherited.)
- **Agentic method:**
  ```python
  @strategy(CodeActStrategy())
  async def research(self, topic: str) -> ResearchReport:
      """..."""
      ...
  ```
  - Docstring describes the workflow: resolve relative dates using `self.today`; call `await self.almanack.search(topic)` to discover cards; for each hit, `await self.almanack.get(card_id)` to obtain the card and its verified questions; match the question to the topic; return a validated `ResearchReport`.
  - Return annotation `ResearchReport` is the validated contract.
  - The `...` body is intentional (NOOA runs it via the LLM); annotate the method `# ty: ignore[empty-body]` so `ty` (`all = "error"`) passes — mirrors `ccnget-agent` (`__init__.py:101-103`).
- **Tool access:** the model calls `await self.almanack.search(...)` / `await self.almanack.get(...)` in code execution (NOOA renders the skill as a Python object on `self`).

### 4.4 Skill class — `PoorRichardSkill(Skill)` (`src/poor_richard_agent/skills.py`)

Plain Python tool belt (mirrors `ccnget.CcngetSkill` / `xng.WebResearchSkill`). Async, deterministic, offline tools. `SkillRegistry.load()` instantiates the class **with no args** (`skill_cls()`, `skill_registry.py:479`) then calls `attach(agent)`; the class holds no shared state, so it needs no `__init__` beyond the inherited `Skill.__init__`.

- `async def search(self, query: str, top: int = 3) -> list[SearchHit]` — wraps `poor_richard.search(query, top=top)` (via `asyncio.to_thread`), mapping each `(score, card, question)` → a flat `SearchHit` (the matched question/expected flattened to strings).
- `async def get(self, card_id: str) -> ReferenceCard` — wraps `poor_richard.get(card_id)` (via `asyncio.to_thread`); returns the almanack `ReferenceCard` (its golden questions, pinned `example`, and `notes`). Deliberately the almanack's own type, like `ccnget.browse` returns its native result — the model reads `card.questions` to pick the matching question.
- **No `find()` tool** (removed): `get()` already returns the card with all its `questions`, and `poor_richard.search` scans *all* cards rather than one, so a per-card `find(card_id, question)` was both redundant and mis-specified (it could not "wrap `poor_richard.search(question)`").
- All tools documented via docstrings (prompt material). No shared state required — keeps it minimal.

### 4.5 Validated models — `models.py` (pydantic)

Mirrors `xng-agent`'s pydantic validated-return pattern. **Flat fields only** — the models never embed the almanack's `ReferenceCard`/`Question` dataclasses, so the validated-return schema isn't coupled to the almanack's internals (the skill's `get()` may still *return* a `ReferenceCard` to the model, but that is a tool result, not the validated return).

- `SearchHit`: `score: float`, `card_id: str`, `pypi: str`, `import_name: str`, `question: str | None = None`, `expected: str | None = None` (the matched golden question, flattened to strings).
- `Answer`: `card_id`, `import_name`, `pypi`, `question: str`, `expected: str` (verified), `notes: str = ""` (gotchas/API-drift guardrails).
- `ResearchReport`: `topic: str`, `discovered: list[SearchHit]`, `answers: list[Answer]`, `offline: bool`, `note: str | None = None`.

### 4.6 Research workflow

1. **Resolve context** — the model resolves relative dates in the topic against `self.today` if needed (e.g. "next NYSE session").
2. **Discover** — `await self.almanack.search(topic)` → `list[SearchHit]` (top 3 by almanack score).
3. **Verify** — for each hit, `await self.almanack.get(card_id)` → `ReferenceCard`; match the card's `Question` to the topic; build `Answer` from the card + question.
4. **Report** — assemble `ResearchReport` (discovered, answers, offline status, note with recommended API shape).
5. **Validate** — harness validates the pydantic `ResearchReport` against the annotation.

The agent's added value over raw library calls: **discovery** (which library), **verified answers** (question/expected pairs from the almanack's golden tests), and **API-drift guardrails** (card `notes`/`example` record the pinned API shape — the exact failure mode of a model writing from stale training knowledge, per `future-directions.md` §3).

### 4.7 `main()` entry point & output (`poor_richard_agent:main`)

- `asyncio.run(_run(topic))` where `_run` constructs `PoorRichardAgent()` (class-level `llm=`), calls `agent.research(topic)`, returns the validated `ResearchReport`.
- Prints `report.model_dump_json(indent=2)` as the report (clean, scriptable).
- Exit codes: `0` ok; `1` no match / cannot import / research error; `2` usage error.
- `BrokenPipeError` handling (piped `| head`) — mirror `poor_richard`'s `__init__.py`.

### 4.8 Entry-point wiring & SKILL.md

- `pyproject.toml`:
  - `[project.entry-points."nooa.skills"]` → `"poor-richard.almanack" = "poor_richard_agent.skills:PoorRichardSkill"`.
  - `[project.scripts]` → `poor-richard-agent = "poor_richard_agent:main"`.
- The NOOA-native skill is the entry-point `PoorRichardSkill` + docstrings (the agent is already self-describing via the class docstring).
- Optional **hax/agents-convention SKILL.md** (`src/poor_richard_agent/.agents/skills/poor-richard-agent/SKILL.md`) documenting the `--ask`→`--example` pipeline translated to the agent's tool calls and gotchas, for session-based consumers — consistent with `poor-richard`'s convention and the test plan's cold-vs-warm A/B.

---

## 5. Implementation Plan (phased)

### Phase 0 — Scaffold & dependency setup ✅ (done)
- Scaffolded with **testafize** (`make init`): `src/poor_richard_agent/`, `pyproject.toml`, `uv_build` backend, console script `poor-richard-agent = "poor_richard_agent:main"`, `requires-python >=3.14`, dev tools (ruff/bandit/vulture/refurb/ty/pytest) + their `[tool.*]` config, `Makefile`.
- **Dependencies:** `poor-richard>=0.1.0`, `nooa>=0.0.9`, `pydantic>=2`.
  - `poor-richard` is **not on PyPI** → resolved via `[tool.uv.sources] poor-richard = { git = "https://github.com/brian-learns/poor-richard.git" }` (same pattern as the reference agents' ccnget/xng git sources).
  - **Dropped testafize's `exclude-newer = "7 days"`** (and the matching `--exclude-newer` flag in the Makefile `check` target): with it, a fresh `uv lock` is unsatisfiable — `nooa 0.0.10` and poor-richard's dep `holidays 0.104` are both published after the 7-day cutoff, so they are filtered out. Without it, `uv lock` resolves 156 packages at **nooa 0.0.10** as intended.
- `uv sync` in the agent venv; confirmed `nooa 0.0.10` + `poor_richard 0.1.0` (git) import and `poor_richard.search()` runs.
- The `nooa.skills` entry point is added in Phase 3 (see §4.8); it is what makes `PoorRichardSkill` discoverable by `SkillRegistry`.

### Phase 1 — Skill & models
- `models.py`: `SearchHit`, `Answer`, `ResearchReport` (pydantic).
- `skills.py`: `PoorRichardSkill(Skill)` with `search`/`get`/`find` tools, delegating to `poor_richard`, typed return dataclasses, docstrings.
- Verify skill methods are async and callable as NOOA tools.

### Phase 2 — Agent class & research method
- `agent.py`: `PoorRichardAgent(Agent, llm=nooa_llm)`, class docstring (system prompt), `__init__` (today state, `SkillRegistry` + `activate(["poor-richard.almanack"])`), `@strategy(CodeActStrategy())` `research(topic) -> ResearchReport` with docstring + `...` body.
- `__init__.py`: exports + `main()`.

### Phase 3 — Entry point, CLI, docs
- Console script `poor-richard-agent = "poor_richard_agent:main"`. ✅
- `README.md`: usage, prerequisites, offline note, gotchas. ✅
- SKILL.md (hax convention). ✅ ships in the wheel.
- `uv build` produces the wheel + sdist carrying the package, SKILL.md, and both entry points. ✅ (The agent's tests are **top-level CI tests, correctly not shipped in the wheel** — unlike the almanack, whose `--example` feature needs its golden tests inside the wheel.)

### Phase 4 — Testing ✅ (14/14 pass, all socket-blocked)
- `tests/conftest.py`: `no_network` autouse fixture (socket block, adapted from `poor-richard`).
- `tests/test_skills.py` (6): offline tests for `search`/`get` (real almanack data + one `monkeypatch`ed mapping case; no `find` — dropped in Phase 1).
- `tests/test_agent.py` (6): offline construction, skill activation (`self.almanack`), `today` state, `ResearchReport` return annotation, per-instance `llm=` injection, `main()` usage → exit 2.
- `tests/test_research_loop.py` (2): agentic loop driven by NOOA's `FakeLLMClient` (scripted `execute_python`/`return_result`): discovery→verified answer (validated return) and no-match→empty answers. The flagged risk resolved cleanly — no fallback needed.

### Phase 5 — Tooling, quality, release ✅ (done)
- **Full tooling gate** (`make check`): ruff, bandit, vulture, refurb, ty, **interrogate** (added to dev deps + uncommented in the Makefile this phase), and `uv audit`. Green.
- **Docstring coverage 100%** (interrogate, `fail-under 90`, excluding tests).
- **Offline test run:** `make test` runs the socket-blocked suite (14/14 offline). `unshare -n` isn't permitted in this environment, but the autouse `no_network` fixture already enforces offline-correctness, so it's a non-issue.
- **Package & verify:** `uv build` produces the wheel + sdist (package + SKILL.md + both entry points). CLI verified end-to-end: no-arg usage → exit 2; a live question → validated `ResearchReport` JSON, exit 0.
- **Release:** the package lives in the workspace; the hax-convention SKILL.md (Phase 3) documents the skill for the test plan's cold-vs-warm A/B.

---

## 6. Test Strategy

### 6.1 Offline & no-network enforcement
- `tests/conftest.py` installs an autouse `no_network` fixture that patches `socket.socket.connect`, `socket.socket.connect_ex`, and `socket.getaddrinfo` to raise — adapted from `poor-richard`'s `conftest.py`. (A PASS therefore means correct **and** offline.)
- Where permitted, `unshare -n uv run pytest` adds kernel-level network blocking.
- A library that fetches at import time must fail loudly; tests import almanack modules **inside functions** so import-time fetches are caught.

### 6.2 Skill & agent unit tests (deterministic, offline)
- **`test_skills.py`** — verify `search` maps almanack `(score, card, question)` → `SearchHit` correctly (scores, card ids, import names, matched question); `get` returns the correct `ReferenceCard`; `find` returns the matching `Question` with `expected`. Use fakes for the wrapped functions where isolation is needed; otherwise rely on bundled almanack data.
- **`test_agent.py`** — construct `PoorRichardAgent()` (class-level `llm=` works; client creation is offline-safe); verify `self.almanack` is the `PoorRichardSkill` and is activated; verify `today` state format; verify `research(topic)` returns a validated `ResearchReport` instance.

### 6.3 Agentic loop integration tests (offline, mocked LLM)
- **`test_research_loop.py`** — exercise the `research` CodeAct loop with a mocked LLM/runtime: a scripted LLM returns code that calls `search` then `get` and builds a `ResearchReport`; assert the validated return, discovery, and answer wiring.
- Cover **no-match** (empty `discovered`) and **error handling** (clean failure / exit code) cases.
- Approach: follow NOOA's capability-test pattern (mock `UnifiedLLM` + runtime, script turns) — this validates the loop wiring and validated return without a real LLM. Complexity is noted in §9.

### 6.4 Almanack test-plan alignment (real agents)
- The `poor-richard-agent` is the **Noah** (NOOA agent) consumer in `docs/test_plan.md`'s experiments. Its own offline tests complement the almanack's golden-question tests.
- The cold-vs-warm SKILL.md A/B from the test plan: install the agent's skill into a test agent's skill directory and run Noah with the task; record misses as the trigger list for card-text/keyword fixes (see `future-directions.md` §1).

---

## 7. Quality & Tooling Standards

Mirror `xng-agent`/`ccnget-agent` config in `pyproject.toml`:

- **ruff** (`E`, `F`, `B`, `S`, `I`, `N`, `RUF`; line-length 120; ignore `S101`, `E501`).
- **bandit** — security skips (mirror reference).
- **ty** — `rules = { all = "error" }` (type-check; catches `...` body and empty-signature issues).
- **vulture** — dead code detection.
- **refurb** — formatting.
- **interrogate** — docstring coverage `fail-under = 90`, `exclude = ["tests"]`, `ignore-init-method = true`, `ignore-module = true`. *Caveat:* testafize's default `Makefile` ships `interrogate` **commented out** (not in the `testpackages` install list, not run in `check`) even though the `[tool.interrogate]` config is present. To actually enforce the ≥90% criterion, uncomment/add `interrogate` to the `testpackages` + `check` targets and the dev group; until then the criterion is aspirational only.
- **uv** — no `exclude-newer` (dropped from the testafize default; a 7-day window makes a fresh lock unsatisfiable — see Phase 0). `poor-richard` pinned to git via `[tool.uv.sources]`.

**Docstring discipline:** every class, method, and skill method must have a model-ready docstring — these are prompt material for Noah (NOOA renders them). The class docstring doubles as the system prompt.

---

## 8. Release & Integration

- **Build & install:** `uv sync`, `uv build` (wheel ships tests inside via `uv_build`), install into the agent venv and verify the console script + `nooa.skills` entry point register.
- **Entry-point verification:** confirm `poor-richard-agent` script resolves to `poor_richard_agent:main`; confirm `SkillRegistry(discovered())` lists `poor-richard.almanack`.
- **Skill install for agents:** `poor-richard-agent`'s skill (entry point `poor-richard.almanack`) is opt-in via `SkillRegistry(self).activate(["poor-richard.almanack"])`; document the install path for NOOA agents (and the hax SKILL.md for session-based consumers).
- **Offline sandbox:** the agent makes no runtime network calls; the one-time `financedatabase` data fetch (almanack's `scripts/`) is documented and skippable in tests.
- **No memory, no sub-agent:** aligned with the almanack's self-contained, offline-first design and NOOA's P3/P4.

---

## 9. Risks & Open Questions

| Risk / Open question | Assessment | Mitigation / Decision |
|---|---|---|
| **Testing the agentic `research` loop** requires a mock LLM/runtime (NOOA capability-test pattern) — non-trivial | Medium complexity; reference agents don't test the agentic loop directly | Include `test_research_loop.py` following NOOA's pattern; if the mock setup proves too brittle, fall back to testing skill wiring + validated return, and validate the full NOOA loop via the framework's capability tests + the test-plan real-agent experiment. |
| **Entry-point skill discovery in test venvs** — `activate()` loads via `nooa.skills` entry points, which must be registered in the installed package | Low risk if `uv build`/editable install registers entry points | Verify `SkillRegistry(discovered())` lists `poor-richard.almanack` in tests; add an explicit registration check. |
| **Skill attribute name** (`self.almanack`) is entry-point-derived | Low risk; consistent with NOOA convention (xng→`web`, ccnget→`archive`) | Document `self.almanack` clearly in the agent docstrings; keep the entry-point name `poor-richard.almanack` stable. |
| **NOOA version compatibility** (`nooa>=0.0.9`, installed 0.0.10) | Low risk; with `exclude-newer` dropped, `uv lock` resolves **0.0.10** — the version this plan was verified against (reference agents lock 0.0.9, API-compatible here) | Keep `nooa>=0.0.9`; the API used (Skill/SkillRegistry/strategies) matches 0.0.10 source; re-run full suite after any upgrade. |
| **Phase 0 dependency resolution** — `poor-richard` not on PyPI + testafize `exclude-newer="7 days"` blocks a fresh lock | **Resolved in Phase 0:** git source for `poor-richard` + dropped `exclude-newer` | `uv lock` now resolves 156 packages (nooa 0.0.10); keep the git source and no-`exclude-newer` config. |
| **Almanack data-dependent card (`financedatabase`)** setup | Low risk, noted hazard in test plan | Agent tests skip the financedatabase-dependent path when data absent (mirror almanack's skip pattern); document one-time fetch script. |
| **HAX SKILL.md scope** (optional companion) | Low risk; keep it focused on `--ask`→`--example` pipeline + gotchas | Treat as optional; do not add UX scope beyond the reference-data workflow. |

---

## 10. Next Steps

1. **Phase 0:** Scaffold the package, `pyproject.toml` with entry-point registration, `uv sync`.
2. **Phase 1–2:** Implement `models.py`, `skills.py`, `agent.py`, `__init__.py` (agent class + `research` method + `main()`).
3. **Phase 3:** Console script, `README.md`, SKILL.md; verify `uv build`.
4. **Phase 4:** Write offline tests (`conftest`, `test_skills`, `test_agent`, `test_research_loop`).
5. **Phase 5:** Run the full tooling gate and offline test run (`unshare -n uv run pytest`); fix failures; package and verify end-to-end.
6. **Integration:** Install the agent into NOOA test agents, run the cold-vs-warm SKILL.md A/B from `test_plan.md`, and fold misses into the keyword field / card-text discipline (per `future-directions.md`).

**Success criteria** (all met):
- ✅ All tests pass **offline** (network blocked) — 14/14 under the autouse `no_network` fixture, proving correctness and no runtime network egress.
- ✅ `poor-richard-agent` runs under `nooa`, returns a validated `ResearchReport` as scriptable JSON with correct exit codes (verified live: exit 0 with answers, exit 2 for usage).
- ✅ Tooling gate green (ruff/bandit/ty/vulture/refurb/**interrogate**/audit) with **100%** docstring coverage.
- ✅ The agent's NOOA-native skill is discoverable via `SkillRegistry` (`poor-richard.almanack`) and opt-in via `activate()` → `self.almanack`.

**Remaining (integration, out of the agent's build scope):** Step 6 — install the agent into NOOA test agents, run the cold-vs-warm SKILL.md A/B from `test_plan.md`, and fold misses into the almanack's keyword field / card-text discipline. (Note: a live run surfaced a likely almanack data bug — the `pycountry` card's golden answer for "ISO 3166-1 alpha-3 for France?" is `"France"` but `pycountry`'s `alpha_3` is `"FRA"`.)
