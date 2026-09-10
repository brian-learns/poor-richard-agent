# Plan: `poor-richard-agent` — NOOA agent for the Poor Richard almanack, with shared library-usage memory

**Status:** Core complete (Phases 0–5); memory capability proposed (Phases 6–9)
**Date:** 2026-09-09
**Companion references:** `./README.md`, `./2607.20709.md` (NOOA paper), `../poor-richard/` (almanack), installed `nooa` 0.0.10 + `nooa-memory` 0.0.10.

---

## 1. Core project (Phases 0–5 — complete)

`poor-richard-agent` is a NOOA agent that turns a factual question into an authoritative, **offline** answer: the full 43-library almanack catalog is embedded in the system prompt, `await self.almanack.search()`/`get()` (a `Skill` under the `nooa.skills` entry point) are deterministic tools, and the one agentic method `research(topic) -> ResearchReport` runs a CodeAct loop with a validated pydantic return. All tests run socket-blocked (`no_network` autouse fixture); the tooling gate is ruff/bandit/vulture/refurb/ty/interrogate/uv audit.

The full phase-by-phase record for Phases 0–5 (scaffold, skill+models, agent, CLI/docs, offline tests, tooling/release) is in git history (`git log -- PLAN.md`; the pre-memory plan is the revision preceding `e857202`). This document replaces it.

**Deliberate core invariants the memory work must preserve:**

| Invariant | Where enforced |
|---|---|
| Offline-first: no runtime network egress; a test PASS = correct *and* offline | `tests/conftest.py` `no_network` (blocks loopback too) |
| Verified almanack data is the source of answer truth | `agent.py` docstring: answers come from verified golden `expected` or a computed call — never from memory or the web |
| API-drift guardrails: card `notes`/`example` pin the API shape | `agent.py` docstring workflow step 3 |
| NOOA-native: one `Agent` subclass, docstrings-as-prompt, typed state, validated return | `agent.py`, `skills.py`, `models.py` |

---

## 2. Memory: purpose & objective

Watching live traces of NOOA agents answering almanack questions, the same mistakes recur every session — guessing import names, inventing attribute names (`.iso_alpha2`), passing positional args to keyword-only APIs. Each run re-pays the discovery cost the almanack's catalog and `get()` already removed for *finding* the library, but not for *using* it.

Objective: let agents **share learned insights about how to use the almanack libraries** across sessions and between agents, using NOOA's first-class long-term memory subsystem (`nooa-memory`, the paper's §3.7):

1. **Insights, not answers.** Memory stores usage knowledge — import names, call shapes, keyword-only pitfalls, attribute names, "X is not Y" corrections — keyed per `card_id`. It never stores computed answer values. The verified almanack remains the source of answer truth; memory supplies how-to context only.
2. **Shared.** One SQLite store, readable/writable by every agent surface (Noah first; Hank/Broman later per `../poor-richard/docs/personas.md`), in the unowned/shared namespace.
3. **Local embeddings.** Semantic recall via the embedding model on the local llama-server router — no cloud, no new network egress beyond the already-required local LLM endpoint.
4. **Opt-in & additive.** Off by default; when off, the agent is byte-for-byte the current core (no tools rendered, no hooks, no file). When on, it is a pure layer: uninstallable, inert when disabled.

---

## 3. Research findings (verified 2026-09-09 against the installed packages and the local router)

### 3.1 `nooa-memory` 0.0.10 (NVIDIA, Apache-2.0, ~4.3k LOC)

The paper's §3.7 subsystem, packaged. Declared deps: `nooa`, `numpy`, `pydantic` only (`litellm` is lazy-imported for the embedding backend — see §7).

- **Additive install:** `MemoryManager.install(agent, config=...)` wires event hooks + a context block onto an unmodified agent; `uninstall()` restores it; `config.enabled=False` is inert. Also mountable as the `nemo.memory` skill (entry point `nooa.skills`), but that mount is zero-arg by design — it cannot carry a custom `MemoryConfig`, so we do **not** use it (§4.2).
- **Store:** one human-inspectable SQLite file (`MemoryStore`); default path `.nooa/memory/memory.sqlite`; `Memory` records carry `type` (info/skill/episode/intent/todo/reflection/scratch), `importance` (1–10), `tags`, typed graph edges (`related`, `refines`, `contradicts`, `derived_from`, …), and a capped on-record access log.
- **Retrieval:** hybrid dense+keyword candidate pool → ACT-R scoring (relevance/recency/importance, min-max blended) → optional 1-hop graph spread. Vector backends: `numpy` (exact, default, zero extra deps), `sqlite_vec`, `chroma`.
- **Model-callable tools (7):** `remember`, `recall`, `search`, `update_memory`, `forget`, `associate`, `deref` — via `MemoryToolsMixin` (exposed as `self.*`) or the skill (exposed as `self.memory.*`).
- **Spontaneous injection:** pre-turn hook derives a query (default strategy `last_message`), recalls top-k, and renders them into a bounded dynamic context block `recalled_memories` (default 2,000 chars, self-gated cadence). The agent receives relevant hints without calling any tool.
- **Auto-encoding:** writes on `Error`/`Notification` events (salience-gated; `Error` → importance 7). This captures exactly the recurring trace mistakes this feature targets.
- **Reflection:** post-task consolidation — deterministic dedup (cos ≥ 0.95 merge), related-edge linking, ACT-R/Ebbinghaus pruning; optional LLM `reasoner` (distill episodes → `reflection` insights) and `reconciler` (merge stale/contradicted values), both taking a `get_llm` getter so they run on the local model. Default (no reasoner/reconciler passed) = deterministic ops only, no LLM cost.
- **Forgetting:** decay with `protected_types=("skill",)` by default — `skill`-type memories never auto-forget.
- **Owner scoping:** `owner=""` writes to the unowned/shared namespace visible to every reader; `recall(query, owner="*")` reads all owners; per-owner rows stay private.
- **Fault tolerance (verified in source):** the NOOA event manager logs and swallows handler exceptions (`nooa/runtime/event_manager.py:241-262`), and nooa_memory's write-on-event path is itself try/excepted — a dead embedding server degrades spontaneous injection for a turn; it cannot break the agentic loop.

### 3.2 Local embeddings (live-verified)

- The llama-server router at `127.0.0.1:8080` proxies `/v1/embeddings` for `nomic-embed-text-v1.5` (768-dim, ~1 s/call) and also serves `Qwen3-VL-Embedding-2B` as an alternative.
- `EmbeddingConfig(backend="litellm", model="openai/nomic-embed-text-v1.5", endpoint="http://127.0.0.1:8080/v1", api_key="local")` works end-to-end: wrote six library-usage hints, recalled them — "ISO 3166-1 alpha-3 code for France?" surfaced the pycountry hint (cos 0.66), "timezone for latitude/longitude" surfaced the timezonefinder hint (cos 0.72), dense-only matched a paraphrase ("buying groceries" → grocery memory, cos 0.66) that keyword match missed.
- **Gotcha (verified):** raw `MemoryStore.add(memory)` does **not** embed — vectors are stored only via `MemoryManager.remember()` or by passing `embedding=` explicitly. The manager path is what we use; the raw store is test-only.
- **Gotcha (verified):** with a very small store, min-max score normalization lets an unrelated memory ride along at rank 2. Harmless at working scale; do not tune against toy stores.
- The package default embedder is `HashingEmbedder` (deterministic, offline, zero-deps) — the correct default for the socket-blocked test suite.

---

## 4. Design decisions

1. **Use `nooa-memory` as-is; build no custom store.** The earlier draft plan (git `e857202`..`cd9e7a8`) proposed hand-rolling a pydantic "LibraryMemory" store re-ingested from `CARDS`. That design is retired: it stored a snapshot of data the agent already has in-prompt and one `get()` away, accumulated nothing across sessions, and reinvented (worse) what `nooa-memory` ships. The recurring-mistake problem also *requires* model-authored memories, which that plan's "never store model recall" constraint forbade.
2. **Mount as a configured skill subclass, activated through `SkillRegistry`** — the same opt-in mechanism the almanack skill uses (`agent.py:82-84`), rather than `MemoryManager.install` in `__init__` or the zero-arg `nemo.memory` entry point. A `PoorRichardMemorySkill(MemorySkill)` subclass reads its `MemoryConfig` from environment in `__init__` (still zero-arg instantiable, as `SkillRegistry.load()` requires), so the custom embedding config rides the standard activation path. Tools appear as `self.memory.*`; the schema guide is auto-injected with the correct `self.memory.` prefix.
3. **Opt-in via `NOOA_MEMORY=1`.** Unset → the skill is not activated: no `self.memory` attribute, no tools in the prompt, no hooks, no SQLite file. The default agent construction is unchanged, so the existing suite passes untouched.
4. **Shared namespace: `owner=""`.** All agents write to and read from the shared namespace on one store file — the "share hints between agents" requirement. (Per-owner scoping with `owner="*"` recall remains available later if private tiers are wanted.)
5. **Insight discipline is prompt-level, plus reviewability.** Nothing in `nooa-memory` hard-blocks a stored answer value — the injected schema guide already says "distilled facts/skills/decisions, one self-contained item each — never raw transcripts", and we add one docstring paragraph: store only how-to insights per `card_id` (imports, call shapes, pitfalls), never computed answer values; prefer `type="skill"` (decay-protected) for how-tos. The store is a human-inspectable SQLite file; a wrong memory is `update_memory`/`forget`-able by the model or editable on disk. This is a known, accepted limit (§7).
6. **Local nomic embeddings by default when memory is on; hashing in tests.** `NOOA_EMBED_BACKEND` defaults to `litellm` against `NOOA_LLM_BASE` (the router already required for the LLM) with model `openai/nomic-embed-text-v1.5`; tests exercise the `hashing` backend so the socket-blocked suite never touches the router.
7. **Reflection: deterministic only for now.** `MemorySkill` passes no reasoner/reconciler, so post-task reflection does dedup/link/prune with zero LLM calls. LLM-backed reasoner/reconciler (local Qwen) is an optional later phase — it is where repeated `Error` episodes get distilled into durable `skill` insights.
8. **Keep the Error auto-write.** Salient errors ("model guessed `.iso_alpha2` → AttributeError") are the raw material of the insights we want; the model's curation guide tells it to refine or forget auto-written noise.

---

## 5. Integration

### 5.1 `src/poor_richard_agent/skills.py` — add `PoorRichardMemorySkill`

```python
from nooa_memory import EmbeddingConfig, MemoryConfig
from nooa_memory.memory_skill import MemorySkill

class PoorRichardMemorySkill(MemorySkill):
    """Shared almanack library-usage memory (opt-in via NOOA_MEMORY=1)."""

    def __init__(self) -> None:
        super().__init__(MemoryConfig(
            enabled=True,
            path=os.environ.get("NOOA_MEMORY_PATH", ".nooa/memory/memory.sqlite"),
            owner="",
            embedding=EmbeddingConfig(
                backend=os.environ.get("NOOA_EMBED_BACKEND", "litellm"),
                model=os.environ.get("NOOA_EMBED_MODEL", "openai/nomic-embed-text-v1.5"),
                endpoint=os.environ.get("NOOA_LLM_BASE", "http://127.0.0.1:8080/v1"),
                api_key="local",
            ),
        ))
```

(`MemorySkill.__init__` rewrites `api_prefix` to `self.memory.` automatically.)

### 5.2 `pyproject.toml` — second entry point

```toml
[project.entry-points."nooa.skills"]
"poor-richard.almanack" = "poor_richard_agent.skills:PoorRichardSkill"
"poor-richard.memory" = "poor_richard_agent.skills:PoorRichardMemorySkill"
```

Also add `litellm` to dependencies (nooa-memory lazy-imports it but does not declare it).

### 5.3 `src/poor_richard_agent/agent.py` — activation + docstring paragraph

- `__init__`: `if os.environ.get("NOOA_MEMORY"): self.skills.activate(["poor-richard.memory"])` — alongside the almanack activation.
- Class docstring: a `{self.memory_block()}` placeholder (mirrors `{self.library_catalog()}` at `agent.py:51`) returning `""` when memory is off, or — when on — the insight-discipline paragraph: memory holds how-to insights about almanack libraries keyed by `card_id` (imports, call shapes, pitfalls); store/consult only usage knowledge, never computed answer values; recalled memories are hints, not ground truth — the card's `notes`/`example` and verified golden answers still win.

### 5.4 What the model gains when on

- `self.memory.remember/recall/search/update_memory/forget/associate/deref` (rendered in `doc(self)`).
- The auto-injected `memory_system` guide (nooa_memory's curation instructions, `self.memory.`-prefixed).
- Per-turn `recalled_memories` context block: top-k hints for the current topic, bounded to ~2,000 chars.
- Auto-written `Error`/`Notification` memories, deduped/refined by post-task reflection.

---

## 6. Phased implementation

### Phase 6 — Configured memory skill
- `PoorRichardMemorySkill` (`skills.py`) + `poor-richard.memory` entry point + `litellm` dependency.
- Env-gated activation in `PoorRichardAgent.__init__`; `{self.memory_block()}` docstring placeholder.
- Verify: off-by-default construction is unchanged (existing suite green); on-construction renders `self.memory.*` tools and the guide block.

### Phase 7 — Shared store & embedding wiring
- Default shared path (env-overridable `NOOA_MEMORY_PATH`) and `owner=""`.
- Live smoke: write/recall round-trip through the manager with the local nomic embedder; confirm dense+hybrid recall and spontaneous injection in a real `research()` run against the router.

### Phase 8 — Offline tests & quality gate
- Memory-on tests under `no_network` with the **hashing** embedder: activation, tool rendering, remember→recall round-trip, shared-namespace visibility, skill-type decay protection, retrieval fault tolerance (dead embedder → loop survives, injection just missing).
- Config-wiring test asserting the litellm `EmbeddingConfig` values without any network call.
- Full tooling gate (`make check`), docstring coverage ≥90%.

### Phase 9 — Learning loop (optional)
- LLM-backed reflection: `llm_reasoner`/`llm_reconciler` wired to `nooa_llm` (local), so repeated `Error` episodes distill into durable `skill` insights and stale hints get reconciled.
- Seed the store from observed trace mistakes (manual `remember` or a script) and run the cold-vs-warm A/B from `../poor-richard/docs/test_plan.md` to measure the recurring-mistake reduction.

---

## 7. Risks & mitigations

| Risk | Assessment | Mitigation |
|---|---|---|
| **Answer values leak into memory** (violating "insights, not answers") | Medium — prompt-level discipline only; nothing hard-blocks it | Docstring discipline paragraph (§4.5); `card_id`-tagged, `skill`-typed writes; store is one inspectable SQLite file — review + `forget`/edit on disk; Phase 9 reconciler merges/corrects |
| **Stale hints after an almanack/library update** | Medium — hints are now genuinely agent-authored and can rot | Hints carry the `card_id` tag (scoping); `refines`/`contradicts` edges + Phase 9 reconciler; on a major almanack bump, prune the store (documented ops note); answers still always come from the card, so a wrong hint degrades efficiency, not correctness |
| **Embedding server down at runtime** | Low | Verified: event-handler exceptions are logged and swallowed (`nooa/runtime/event_manager.py:241-262`); litellm calls are timeout-bounded (60 s) with retries; failure degrades spontaneous injection for a turn, never breaks the loop |
| **`litellm` undeclared by nooa-memory** | Low | Add `litellm` to our dependencies (§5.2); it is already in `uv.lock` via nooa |
| **Test-suite coupling to the router** | Low | Hashing embedder is the package default and the test default (§4.6); litellm config asserted, not called |
| **Context bloat from injected memories** | Low | Bounded block (default 2,000 chars, top-k 5, self-gated cadence); `SpontaneousConfig` knobs available |
| **Small-store ranking artifacts** (min-max normalization) | Cosmetic | Noted (§3.2); do not tune retrieval against toy stores |
| **Shared store write contention** (multiple agents, one file) | Low | SQLite with WAL; agents in this workflow run sequentially; revisit only if concurrent surfaces appear |

---

## 8. Success criteria

- **Off by default:** with `NOOA_MEMORY` unset, the agent constructs and behaves exactly as today; the existing socket-blocked suite passes unchanged.
- **Opt-in layer:** with `NOOA_MEMORY=1`, `self.memory.*` tools + guide render in the prompt; a SQLite store is created at the configured path; uninstall/disable leaves the agent unchanged.
- **Shared insights:** a hint written by one agent run is recalled (semantically, via local embeddings) by a fresh run on the same store; `owner=""` visibility verified.
- **Insight discipline:** docstring paragraph present; no computed answer values in seeded/tested memory content.
- **Offline-safe:** all new tests pass socket-blocked; a dead embedding server does not break `research()` (fault-tolerance test).
- **Gate:** `make check` green (ruff/bandit/vulture/refurb/ty/interrogate/uv audit), docstring coverage ≥90%.
- **Measured benefit (Phase 9, optional):** cold-vs-warm A/B shows fewer recurring API/import mistakes with the warmed store.

---

## 9. Constraints & trade-offs

- **Core invariants unchanged** (§1): offline-first, verified-data answer truth, API-drift guardrails, NOOA-native single class. Memory is a layer; when off, the core is untouched.
- **Memory is not the answer source.** Recalled hints are context; the card's `notes`/`example` and verified golden answers always win. This is stated in the agent docstring so the model treats injections as hints.
- **Insight storage is model-curated, human-reviewable** — a deliberate departure from the retired draft plan's "verified data only" rule, required by the recurring-mistake objective, and compensated by the inspectable single-file store.
- **Loopback embeddings are "offline" in the project's sense**: same local router as the LLM itself (already a runtime requirement); the socket-blocked test suite still covers all code paths via the hashing backend.
- **No custom retrieval, schema, or persistence code** — all of it comes from `nooa-memory`; our package contributes one configured skill subclass, one entry point, one docstring paragraph, and tests.
