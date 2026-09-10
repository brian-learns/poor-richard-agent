# Plan: Using Agent Memory to Remember Almanack Library Details

**Status:** Proposed — draft plan
**Date:** 2026-07-24
**Scope:** An opt-in, layered enhancement to `poor-richard-agent` that uses durable agent memory to remember details about the **43 libraries in the Poor Richard almanack** — and how that memory supports the agent's library discovery, API-drift guardrails, and cross-session continuity.

**Companion references:**
- Project: `./README.md`, `./PLAN.md` (existing overall project plan; Phases 0–5 complete).
- Reference paper: `./2607.20709.md` (arXiv 2607.20709, NVIDIA Object-Oriented Agents / NOOA).
- Almanack: `../poor-richard/` — offline-verified 43-library catalog (`registry.py` `CARDS`), `search()` / `get()`, golden-question test linkage, `notes`/`example` API-pin.

---

## 1. Purpose & Objective

`poor-richard-agent` currently answers factual questions **offline-first and self-contained per run, with no agent memory**. Memory is deliberately absent because adding persistent state would contradict the offline-first, sandbox-safe core and risk the model writing from stale training knowledge.

This plan proposes a **separate, opt-in, layered memory capability** that does **not** alter the core design. Memory is a **retrieval / augmentation layer over the almanack's verified data**, not a replacement for it.

The objective:

1. **Durability** — the agent can remember details about each almanack library (id, import name, archetype, provenance, pinned API shape, verified answers, example usages) across **multiple sessions and runs** via **local, file-based persistence** (§5.3). Memory survives process/session boundaries but is never the run's source of truth — the verified almanack catalog and per-run discovery always remain primary.
2. **Verified-data-grounded** — every memory entry is sourced exclusively from the almanack's offline-verified `CARDS` data and its golden-question tests. Memory never stores raw model recall.
3. **API-drift guardrails preserved** — memory carries the pinned `notes`/`example` API shape, so a library version change does not let the agent revert to stale knowledge.
4. **NOOA-native** — memory is implemented as typed Python state/context, rendered as prompt material, and validated through NOOA's harness APIs, per the paper's agent-as-a-Python-object model.
5. **Minimal & opt-in** — memory is a focused, layered capability scoped to almanack-library details. It is **opt-in** (activation mechanism defined in the phased plan) and does **not** replace per-run discovery, and it does **not** introduce memory or sub-agent behavior into the core run model.

---

## 2. Background: Current State & Constraints

### 2.1 Current architecture (from `README.md` / `PLAN.md`)

- The agent is a single `PoorRichardAgent(Agent, llm=nooa_llm)` class; methods are model actions, fields are model-visible state, docstrings are the prompt, type annotations are the contract.
- Tool surface: `await self.almanack.search(query, top=3)` (deterministic ranking) and `await self.almanack.get(card_id)` (deterministic, flat `CardDetail`). Both are plain async Python, offline, wrapped via `asyncio.to_thread`.
- Agentic method `research(topic) -> ResearchReport` uses NOOA's `@strategy(CodeActStrategy())` loop; the full 43-library catalog is embedded in the system prompt via `library_catalog()`.
- `today` is a state field for relative-date resolution (mirrors `xng-agent`).
- The project is **offline-first**: no runtime network egress; the one-time `financedatabase` fetch is a documented script + skippable in tests.

### 2.2 Why memory is currently unused

- `README.md` states: *"No memory, no network at runtime: the only LLM loop is NOOA's, and every answer comes from the almanack's verified data."*
- The current design is constrained by **PLAN §4 (Principles 4 & 5), §2.3 (Constraints), and §13 (Constraints & Trade-offs)** to keep memory out of the core run model: memory must be NOOA-native and minimal, must be opt-in and layered, and is never the run's source of truth or a replacement for per-run discovery.
- The plan's **Constraints (§2.3) and Constraints & Trade-offs (§13)** reinforce that the core offline-first, self-contained, no-memory run model is unchanged: memory is a retrieval/augmentation layer, not the source of answer truth.

### 2.3 Constraints the plan must respect

| Constraint | Origin |
|---|---|
| **Offline-first / no network egress** | README, PLAN §2.3 (Constraints table), §13 |
| **Self-contained per run** (memory is a layer on top, not the run's source of truth) | README, PLAN §2.3, §13 |
| **Verified data is the source of truth** (never raw model recall) | README Notes, PLAN §4 (Principle 2), §9 |
| **API-drift guardrails** (`notes`/`example` pin the API shape) | README Notes, PLAN §4 (Principle 3), §5.1, §6.1 |
| **NOOA-native** (Python object, typed state/context, docstrings as prompt, validated return) | PLAN §3.1 (NOOA paper review), §4 (Principles 1 & 4) |
| **Minimal & scoped** (no bespoke DSL, no UX scope beyond reference-data workflow) | PLAN §4 (Principle 4), §7 |
| **Type-checked & validated** (pydantic models) | PLAN §4 (Principle 6), §9 |

---

## 3. Reference Materials Review

### 3.1 NOOA paper — `./2607.20709.md` (arXiv 2607.20709)

Relevant concepts that shape the memory plan:

- **Agent-as-a-Python-object** (§2): an agent is a Python class — methods are model-facing actions, fields are model-visible state, docstrings are the prompt, type annotations are contracts. Memory must therefore be a **typed field/state** on the agent, not a free-form string, and must be rendered as prompt material via docstrings or context.
- **Design principles P1–P5** (§2):
  - **P1 Reuse Python abstractions** — memory is built with Python classes, typed state, and the framework's existing state/context APIs; no bespoke DSL.
  - **P2 Reframe agentic loops as typed method calls** — memory retrieval is a typed method (`memory.get(topic) -> list[LibraryMemory]`) with typed input/output, not text-only exchange.
  - **P3 Move deterministic work out of the agentic loop** — memory ingestion and retrieval are deterministic, offline, and out-of-loop; only the agentic `research` loop is LLM-driven.
  - **P4 Unlock the model's existing Python knowledge** — memory surfaces typed, documented library details so the model uses them directly (grounded in verified data, not recall).
  - **P5 Expose the harness as explicit APIs** — memory is a documented, explicit part of the agent's state/context surface, not hidden.
- **Agent loop (§3)**: CodeAct strategy with a `...` body; **typed event/state updates**; **validated return**; and **long-term memory** as part of the harness's agent-loop capability. Memory aligns with this: it is a typed state update that the loop consumes and persists.
- **Evaluation (§4)**: capability tests, validated termination, context efficiency. Memory must be **validated** (type + shape) and **efficient** (selective, not a full re-render every turn).
- **Harness APIs (§5)**: the framework exposes context/state/events as explicit APIs. Memory is built on the same surface, so it integrates via NOOA's state/context APIs rather than a custom mechanism.
- **Adaptation to offline-first constraints**: NOOA's paper presents a full first-class long-term-memory subsystem (§3.7: SQLite store, vector index, seven write/recall tools, reflection consolidation, ACT-R ranking). The plan **deliberately adapts this to a minimal, verified-data-grounded layer** rather than replicating NOOA's full memory subsystem — because replicating it would introduce persistent state that contradicts the offline-first, sandbox-safe core (PLAN §2.3, §13). The adaptation preserves the paper's design principles (P1–P5) and agent-loop mechanisms while simplifying the memory subsystem to a local, offline, validated retrieval/augmentation layer (§5).

### 3.2 NOOA framework & reference agents

- NOOA `Agent` base class with `__init_subclass__` (`llm=` config), `_resolve_system_prompt` (class docstring → system prompt), context blocks, event manager, runtime. Memory integrates through the inherited state/context/runtime, consistent with `ccnget-agent` / `xng-agent`.
- `ccnget-agent` / `xng-agent` are explicitly **self-contained, no-memory** agents; this plan layers memory on top without changing their core behavior.

### 3.3 The Poor Richard almanack — `../poor-richard/` (git dependency)

- `../poor-richard/src/poor_richard/registry.py` — `ReferenceCard`, `Question`, `Archetype`, `CARDS` (43 offline-verified cards, schema enforces unique ids, importability, verified-question↔test linkage). `search()` / `get()` are the data-access primitives.
- `../poor-richard/docs/reference-cards.md` — question archetypes, evaluation axes (provenance, update model, offline integrity, coverage, precision, LLM output shape), card schema, golden-question test method.
- `../poor-richard/docs/personas.md` — Noah (NOOA agent — primary almanack consumer), Hank (terminal agent), Broman (human). Memory benefits the Noah surface most directly; can extend to Hank/Broman session continuity.
- `../poor-richard/docs/test_plan.md` — real-agent tasks (T1–T8) with scoring grid (Correct / Conventional / Discovered / Offline) and cold-vs-warm SKILL.md A/B. Memory is a candidate for extending real-agent evaluation.
- `../poor-richard/docs/future-directions.md` — §1 discusses keyword field / card-text discipline; memory complements these by reducing per-run discovery cost.

---

## 4. Core Design Principles for Memory

The following principles govern any memory addition and are normative constraints for this plan:

1. **Offline-first, sandbox-safe.** Memory has no network egress. All persistence is local and sandbox-safe. A memory PASS therefore implies correctness and no runtime network writes.
2. **Verified data is the source of truth.** Memory content is sourced **only** from the almanack's offline-verified `CARDS` and golden-question tests. Memory never stores raw model recall — it stores *verified almanack data plus pinned API shapes*.
3. **API-drift guardrails are preserved.** Memory carries the pinned `notes`/`example` API shape from each card. Memory is a *guardrail*, not a source of answer truth — verified almanack answers always win.
4. **Minimal & NOOA-native.** Built with Python abstractions and NOOA's typed state/context APIs. No bespoke DSL, no UX scope beyond reference-data workflow.
5. **Opt-in & layered.** Memory is an opt-in capability layered **on top** of the existing self-contained, per-run discovery. It does not replace discovery, and it does not change the core run model (no memory / no sub-agent in the core path).
6. **Typed & validated.** Memory is a pydantic model with strict type and shape validation, matching the tool return shapes (`SearchHit`, `CardDetail`, etc.).
7. **Efficient & selective.** Retrieval is selective (by archetype, provenance, topic similarity, or per-library) — memory is augmented retrieval, not a full re-render of the catalog every turn.
8. **Consistent with the core (no contradiction).** Memory is a *retrieval/augmentation layer*; the verified almanack catalog and per-run discovery remain the primary source of truth.
9. **Durability across sessions & runs (layered, not core).** Memory is a *durable, cross-session/run augmentation* layered on top of the self-contained per-run run model. It survives process/session boundaries via local, sandbox-safe file-based persistence (§5.3), but it is never the run's source of truth — verified almanack data always remain primary. Durability is an augmentation; it does not make the core run persistent-state-dependent.

---

## 5. Memory Architecture

### 5.1 Memory store — `LibraryMemory`

A typed, pydantic-backed store of almanack-library details, built as a Python class extending NOOA's state/context surface (mirroring `PoorRichardAgent`'s use of state fields).

**What it stores** (one entry per almanack library card):

| Field | Source | Purpose |
|---|---|---|
| `card_id` | almanack `ReferenceCard.id` | stable identity |
| `name` | `ReferenceCard.name` | display name |
| `pypi` | `ReferenceCard.pypi` | distribution |
| `import_name` | `ReferenceCard.import_name` / importability | how the model imports the library |
| `archetype` | almanack `Archetype` | classification (e.g. calendar, constant, checksum) |
| `provenance` | almanack provenance | why the library is included |
| `pinned_api` | `Question.notes` + `Question.example` | API-shape guardrail (pinned, not model-recalled) |
| `verified_answers` | golden-question `expected` values | verified values for matching questions |
| `example_usages` | example usages from the card | concrete call shapes |
| `related_questions` | linked golden questions | query patterns that map to this library |
| `offline` | `ReferenceCard` offline flag | integrity marker |

**Design notes:**
- The store is **sourced exclusively from offline-verified almanack data**; it never holds raw model recall.
- Entries are pydantic-validated to match the tool return shapes (`CardDetail`-style), so memory is type-checked and consistent with the existing models.
- The store holds **no shared mutable state** beyond its entries, mirroring the skill's minimal-state approach; any per-run mutable state is guarded per NOOA's concurrency model.
- **Retrieval grounding**: each entry carries `verified_answers` (golden-question `expected` values) and `related_questions` (linked golden-question patterns) so topic-based retrieval is possible without re-rendering the full catalog every turn. The full golden-question text is captured at ingestion via the almanack's `Question` records, enabling topic matching.
- **Verification status**: entries are derived from the almanack's verified cards; the almanack's `status` (e.g. `verified` vs `candidate`) is honored so only verified values are surfaced as `verified_answers`, preserving the almanack's integrity semantics.

### 5.2 Data ingestion — offline, from `CARDS`

- Memory is **re-ingested from the almanack's offline-verified `CARDS`** (and golden-question tests) at construction/update time — an offline, deterministic operation.
- Ingestion is **out-of-loop** (PLAN P3): it happens once at setup or on explicit re-sync, never during the agentic loop.
- Ingestion is **validated**: every entry is type-checked against the almanack schema, so memory is guaranteed consistent with the verified data.
- Memory reflects the almanack's **current** offline-verified state; when almanack data updates, ingestion re-pulls the verified cards (offline).

### 5.3 Persistence — offline, sandbox-safe

- Memory is **persisted locally as a file-based, sandbox-safe store** (e.g., a structured file — JSON or SQLite-backed) with **no network writes** — file-based persistence is used for durability across sessions and runs.
- Storage location is sandbox-safe and confined to the agent's runtime environment (e.g., the agent's working directory or a designated data path); no external/network dependencies.
- **Startup loading**: at agent construction, the persisted store is **re-read** from the file, validated (type + shape), and merged into the memory store before the agent starts. A missing/empty store is treated as an empty (cold) store — never an error.
- Persistence is **reversible** (e.g., backed by the on-disk file or a snapshot) if needed for recovery or rollback.
- Concurrent access to shared memory state is guarded where concurrency occurs (NOOA P1/P3).

### 5.4 Activation & context binding

- Memory is accessed as a **typed method** on the agent: `await self.memory.get(topic) -> list[LibraryMemory]` (PLAN P2) — a typed, out-of-loop retrieval, **invoked by agent code**, not by the model. It returns relevant, validated library details for the turn; it is never an agentic (model-invoked) tool.
- **Context rendering into the CodeAct loop**: during `research()`, memory is integrated into the NOOA CodeAct context as prompt material. The retrieved details (or a bounded summary of the relevant subset of the full store) are bound to `self.memory` and rendered via the agent's context/docstring mechanism (NOOA §2/§3), so the model sees only what is relevant and bounded — the full `self.memory` store is never injected wholesale into context.
- **Validation before binding**: every memory entry and every retrieval result is validated (type + shape) before binding, and the binding renders only validated, well-formed data, so the model receives only verified, type-consistent material.

### 5.5 Retrieval — selective, grounded

Retrieval selects library details relevant to the current turn, complementing the existing `search()` ranking:

- **By query/archetype/provenance** — retrieve cards whose archetype or provenance matches the topic.
- **By topic similarity** — retrieve the most relevant library(s) for the question.
- **Per-library** — surface a known library's pinned API shape when the model has already seen it (e.g., recurring "ISO 3166-1 code" questions).
- **Guardrailed** — retrieval returns only verified, validated entries; it never surfaces raw model recall or unverified data.

---

## 6. Integration with the Existing Agent

### 6.1 `PoorRichardAgent` (`src/poor_richard_agent/agent.py`)

- Add a **`self.memory: LibraryMemory`** state field (NOOA P1: fields = model-visible state). This is **opt-in** (activation mechanism defined in the phased plan) and initialized from the ingested almanack data.
- **`__init__`:** construct `LibraryMemory` from the offline-verified almanack `CARDS` (ingestion is offline-safe; no connection until a turn runs). Guard any concurrent initialization. At construction, the persisted store is re-read, validated, and merged into the store (§5.3).
- **`research(topic)`** (CodeAct loop):
  1. **Context** — resolve relative dates against `self.today` as before.
  2. **Discover** — as before, pick from the system-prompt catalog; **`memory.get(topic)` is invoked by agent code** (out-of-loop, §5.4/§6.2) to surface relevant, known library details, which are then bound into the CodeAct context as prompt material. This accelerates discovery (memory is an *augmentation*, not the sole source — catalog-based discovery remains primary).
  3. **Verify or compute** — as before (`search` → `get` → golden answer or computed call). Memory's `pinned_api` (the card's pinned `notes`/`example` API shape) is surfaced in context as an **API-drift guardrail**: the model is instructed to prefer the card's pinned `notes`/`example` over its own recall. **Verified almanack answers always take precedence over memory** — memory supplies context and guardrails only, never answers.
  4. **Report** — assemble the validated `ResearchReport`. Memory-sourced details (a known library's pinned API shape, previously discovered library details) are included where relevant, but every answer still comes from verified almanack data or a computed call — memory never substitutes for the verified source of truth.
- **System prompt / docstrings** (NOOA §2): the memory store and its retrieval mechanism are described in docstrings as prompt material; the agent's self-description includes how memory augments discovery and preserves API guardrails, consistent with NOOA's docstrings-as-prompt model.

### 6.2 Skill tools (`src/poor_richard_agent/skills.py`)

- `memory.get(topic)` is a **deterministic, offline, out-of-loop** retrieval (PLAN P3 & P2): it is a plain async Python method wrapping the offline store, **invoked by agent code** within `research()` (§6.1) — **not** a model-callable agentic tool. This keeps retrieval out of the LLM-driven loop and consistent with NOOA's P3 (deterministic work out of the agentic loop).
- It is exposed through the skill module (`PoorRichardSkill`), consistent with how `search`/`get` are exposed as deterministic, async, `asyncio.to_thread`-wrapped tools.
- Memory retrieval is **timeout-bounded** (`asyncio.wait_for`) and **resource-hygienic** (cleanup in `finally`), matching the existing tool standards.

### 6.3 Validated models (`src/poor_richard_agent/models.py`)

- Extend pydantic models as needed to represent memory entries (`LibraryMemory`) and any memory-augmented return, **flat fields only** (PLAN §4, Principle 6): never embed almanack internals.
- Memory models mirror `CardDetail`'s flat shape so memory entries are type-consistent with the existing validated tool returns.

### 6.4 State, context, and docstrings-as-prompt-material

- Memory is exposed through NOOA's **state/context/event** surface (harness APIs, paper §3/§5), not a bespoke mechanism (NOOA §5).
- `today` and `self.memory` are both model-visible state fields; both visible to the model for relative-date and library-detail resolution.
- Memory is documented in docstrings as prompt material (NOOA §2) — it is part of the agent's self-describing identity.

---

## 7. Use Cases & Benefits

| Use case | How memory helps |
|---|---|
| **Recurring / typed questions** (e.g., "ISO 3166-1 alpha-3 code for France?" across sessions) | Memory surfaces the right library's pinned API shape instantly — no re-discovery from scratch. |
| **API-drift guardrails** (core benefit) | Memory stores the pinned `notes`/`example` API shape per library; even if a library version changes, the agent uses the pinned shape, never stale recall. |
| **Discovery acceleration** | Memory of library archetypes/provenance helps the model pick the correct library faster, complementing `search()` ranking. |
| **Cross-session continuity** | A NOOA agent running across multiple runs builds a richer, durable understanding of the almanack's libraries over time. |
| **Noah session continuity** (primary consumer) | Memory extends Noah's understanding within and across sessions, aligned with `../poor-richard/docs/personas.md` (Noah is the primary almanack consumer). |
| **Hank / Broman continuity** (optional) | Memory can extend terminal-agent and human session continuity, per `../poor-richard/docs/personas.md`. |
| **Evaluation continuity** | Memory supports the test plan's (Correct / Conventional / Discovered / Offline) scoring by reducing per-run discovery cost and enabling Conventional/Discovered credit. |

> **Durability mechanism**: cross-session/run continuity relies on **file-based persistence** (§5.3) — memory is re-read, validated, and merged at agent startup; it survives process/session boundaries. It is a *durable augmentation*, never the run's source of truth (verified almanack data always remain primary).

---

## 8. Mechanics: How Memory Supports Memory-Related Details

1. **Ingestion (offline, out-of-loop):** `LibraryMemory` is populated from the almanack's offline-verified `CARDS` + golden-question tests at construction/re-sync. Validated against the almanack schema.
2. **Selective retrieval (typed, out-of-loop):** `memory.get(topic)` returns a validated, type-consistent list of relevant `LibraryMemory` entries — grounded in verified data, never raw recall.
3. **Context binding (validated, typed):** retrieved details are bound to `self.memory` and rendered as prompt material via docstrings/context, after type+shape validation.
4. **Guardrail enforcement:** memory's `pinned_api` is consulted so the model prefers the card's pinned `notes`/`example` over its own recall — preserving API-drift protection.
5. **Augmentation (not replacement):** memory accelerates discovery but does **not** replace the system-prompt catalog or `search()` ranking; verified almanack data remains the source of truth.

---

## 9. Data & Validation Requirements

- **Source exclusivity:** memory content is sourced **only** from offline-verified almanack data (`CARDS`, golden-question tests). No unverified model recall enters the store.
- **Type & shape validation:** every memory entry is pydantic-validated to match the existing tool models (`SearchHit`, `CardDetail`, `Answer`, etc.); memory is type-checked (`ty all = "error"`).
- **Consistency with almanack data:** memory entries must stay consistent with the almanack's schema, ids, and verified-question↔test linkage. Ingestion re-pulls verified cards on updates.
- **Offline integrity:** memory is offline; a memory operation's correctness is verifiable offline (no network).
- **Updateability & reversibility:** memory can be re-ingested and restored (reversible) to reflect almanack updates, without network.
- **Retrieval validation:** `memory.get(topic)` results are validated (type + shape) before being bound and rendered; retrieval failures are handled fault-tolerantly (e.g., return an empty/bounded result, surface a safe fallback, or log) so retrieval never breaks the agentic loop.
- **Initialization validation:** memory initialization from `CARDS` is validated end-to-end — all entries are type-checked against the schema, and a malformed or incomplete store is handled (e.g., degraded to an empty store with a safe fallback) rather than failing agent startup.
- **Concurrency safety:** shared memory state is guarded where concurrent calls occur (NOOA P1/P3).

---

## 10. Risks & Mitigations

| Risk / Open question | Assessment | Mitigation / Decision |
|---|---|---|
| **Stale memory vs. almanack updates** | Medium | Memory is sourced from the almanack's current offline-verified state; ingestion re-pulls verified cards on update (offline). Memory is a *layer*, not the source of truth — verified almanack data always wins. |
| **Memory introducing staleness that conflicts with verified data** | Medium | Memory is an **augmentation/guardrail** layer over verified data; verified almanack answers always take precedence over memory. Memory only supplies context, not answers. |
| **Offline persistence limits** (local-only storage) | Low | Use sandbox-safe, local, reversible persistence (file/in-process); no network. Local persistence is sufficient for offline-first operation. |
| **Concurrency / shared state** | Low | Guard shared memory state where concurrent calls occur; mirror `ccnget`/`xng` shared-resource cleanup (PLAN §9, concurrency safety; §13 trade-off). |
| **NOOA version compatibility** | Low | Memory uses NOOA's typed state/context APIs; follow NOOA's API contract and re-verify after any upgrade (PLAN §10 Risks). |
| **Scope creep / core-contradiction risk** | Low | Memory is **opt-in and layered**; it does not change the core no-memory, self-contained design. Memory is a retrieval/augmentation layer, not a replacement. |
| **Memory retrieval cost / context bloat** | Low | Retrieval is selective (not a full catalog re-render); memory is efficient, type-validated, and rendered as minimal prompt material (NOOA context-efficiency §4). |
| **Durability across sessions/runs** | Medium | Cross-session/run continuity relies on file-based persistence (§5.3); persistence failure, stale on-disk data, or concurrent load during startup could leave memory inconsistent or missing. Mitigation: validated startup loading (§5.3), offline test coverage of persistence & durability (Phase 10), and local sandbox-safe storage (§13 trade-off). |
| **Opt-in activation & lifecycle** | Low–Medium | If the opt-in mechanism is poorly defined, memory could be unexpectedly active (or inactive) across runs. Mitigation: explicit, testable activation/deactivation lifecycle (Phase 8), and opt-in flag/env override. |
| **Retrieval fault tolerance** | Low | `memory.get()` is out-of-loop; retrieval failures must not break the agentic loop. Mitigation: fault-tolerant fallbacks for retrieval errors (§9) and offline coverage in Phase 10. |
| **Memory in real-agent evaluation** (test_plan T1–T8, A/B) | Low–Medium | Memory is a candidate for extending real-agent scoring; validate via the offline test suite first, then fold into the cold-vs-warm SKILL.md A/B from `../poor-richard/docs/test_plan.md`. |

---

## 11. Phased Implementation Plan

The plan builds on the existing **Phases 0–5** (scaffold, skill+models, agent, CLI/docs, offline tests, tooling/release — all complete). Memory is a new **Phase 6+** rollout, layered on top.

### Phase 6 — Memory data model & offline ingestion
- Define `LibraryMemory` pydantic model (§5.1 fields) and its validation schema.
- Implement **offline ingestion** from almanack `CARDS` + golden-question tests (§5.2) — validated, out-of-loop.
- Confirm ingestion is offline-safe and schema-consistent.

### Phase 7 — Memory store & offline persistence
- Implement `LibraryMemory` store with **offline, sandbox-safe persistence** (§5.3).
- Add concurrency guarding for shared memory state (NOOA P1/P3).
- Verify persistence is reversible and local-only (no network).

### Phase 8 — Memory integration into the agent
- Define the **opt-in activation mechanism** (`self.memory` opt-in flag, explicit enable/disable lifecycle — env/flag override, testable).
- Define the **`memory.get(topic)` invocation** in `research(topic)`: invoked by agent code (out-of-loop, §5.4/§6.2), results bound into the CodeAct context as prompt material.
- Add `self.memory` state field to `PoorRichardAgent` (`agent.py`); initialize from ingested data.
- Integrate `memory.get(topic)` into `research(topic)` (§6.1) as a discovery **augmentation**, preserving catalog-based discovery as primary.
- Ensure memory's `pinned_api` enforces API-drift guardrails during verify/compute (§6.1).

### Phase 9 — Retrieval, context binding & guardrails
- Implement **selective retrieval** (`memory.get` by topic/archetype/provenance/per-library) — typed, out-of-loop (§5.5).
- **Render memory into the CodeAct loop context**: integrate memory rendering into `research()`'s NOOA CodeAct context (system prompt, dynamic context) as bounded prompt material (§5.4, NOOA §2/§3), ensuring the full `self.memory` store is never injected wholesale.
- Bind retrieved details to `self.memory` and render as prompt material via docstrings/context (§5.4, NOOA §2).
- Validate binding (type + shape) before model exposure.
- Ensure **retrieval fault tolerance** (fail-safe fallbacks for retrieval errors) — §9.

### Phase 10 — Testing (offline, no-network)
- **Memory store tests** (offline): ingestion correctness, schema/type validation, persistence round-trip, retrieval selectivity.
- **Memory integration tests** (`test_agent`): `self.memory` construction, ingestion from `CARDS`, retrieval in `research`, validated binding, API-drift guardrail behavior.
- All tests run socket-blocked (autouse `no_network` fixture, adapted from `poor-richard`), mirroring PLAN §6.
- Agentic loop tests: verify memory does not break the CodeAct loop and validated return.

### Phase 11 — Quality gate & integration
- Run full tooling gate (`make check`): ruff, bandit, vulture, refurb, **ty**, **interrogate**, **uv audit** — memory code included (mirrors PLAN §7).
- Docstring coverage ≥90% (NOOA docstrings-as-prompt material).
- Offline test run (`no_network` suite).
- **Real-agent A/B** (optional): install the agent's skill into NOOA test agents, run the cold-vs-warm SKILL.md A/B from `../poor-richard/docs/test_plan.md`, and fold memory's contribution into the scoring grid (Correct / Conventional / Discovered / Offline).

---

## 12. Success Criteria

- **Offline & no-network:** memory operations are fully offline; a pass means correctness and no runtime network egress.
- **Verified-data-grounded:** every memory entry is sourced from almanack's offline-verified `CARDS`/golden tests; no raw model recall enters the store.
- **API-drift guardrails:** memory's `pinned_api` is preserved and enforced — the agent prefers the card's pinned `notes`/`example` over its own recall.
- **NOOA-native:** memory is typed state/context, validated via pydantic, rendered as prompt material via docstrings, and exposed via NOOA's harness APIs.
- **Durability across sessions/runs:** memory is persisted locally (file-based, §5.3) and survives process/session boundaries via validated startup loading (§5.3); a pass implies memory persists correctly across sessions and restarts.
- **Minimal & opt-in:** memory is a layered, opt-in capability that does **not** alter the core no-memory, self-contained design.
- **Tests:** memory store + integration tests pass offline (no-network), covering ingestion, **persistence & durability across sessions/runs**, retrieval, guardrails, **retrieval fault tolerance**, and loop integration.
- **Tooling gate:** full quality gate (ruff/bandit/ty/vulture/refurb/interrogate/audit) green, 100% docstring coverage.
- **Real-agent (optional):** memory contribution validated in the cold-vs-warm SKILL.md A/B from `../poor-richard/docs/test_plan.md`.

---

## 13. Constraints & Trade-offs

- **Core design preserved:** memory is opt-in and layered; the core offline-first, self-contained, no-memory run model is unchanged. Memory does **not** replace per-run discovery.
- **Memory is not the answer source:** verified almanack data (catalog + golden answers) always remain the source of truth. Memory is a retrieval/augmentation and guardrail layer.
- **Local-only persistence:** memory persistence is offline/sandbox-safe (local, reversible); no network is introduced.
- **Scoping:** memory is focused on almanack-library details only — no UX scope beyond the reference-data workflow.
- **Augmentation over replacement:** memory accelerates and enriches discovery but does not replace the system-prompt catalog or `search()` ranking.
- **Durability across sessions vs. self-contained per run:** memory trades the "self-contained per run" minimalism for durable, cross-session/run continuity via local file-based persistence — but durability is layered on top; the core run model remains self-contained, and verified data always win.
- **Simplified memory subsystem vs. NOOA's full memory:** NOOA's paper presents a full first-class memory subsystem (SQLite, vector index, consolidation). The plan deliberately simplifies this to a minimal, offline, validated retrieval/augmentation layer — sacrificing NOOA's consolidation/vector features for offline-first safety and minimalism.
- **memory.get() as out-of-loop method vs. model-callable tool:** `memory.get()` is implemented as a deterministic, out-of-loop method invoked by agent code (per NOOA P2/P3), not a model-callable agentic tool. This keeps retrieval out of the LLM-driven loop and consistent with the offline-first, minimal design, at the cost of a model-initiated retrieval interface.

---

## 14. Next Steps

1. **Pre-review fixes:** resolve internal cross-references (§2.2, §2.3), correct `memory.get()` design consistency (§6.2: out-of-loop deterministic method, not model-callable tool), and clarify durability across sessions (§1, §5.3).
2. **Phase 6:** Define `LibraryMemory` model + offline ingestion from `CARDS`/golden tests.
3. **Phase 7:** Implement offline, sandbox-safe file-based persistence + startup loading + concurrency guarding.
4. **Phase 8:** Define the opt-in activation mechanism; define `memory.get(topic)` invocation in `research(topic)` (agent-code-driven, out-of-loop); integrate `self.memory` and `memory.get()` into `PoorRichardAgent` and `research()` as a discovery augmentation.
5. **Phase 9:** Implement selective retrieval; render memory into the CodeAct loop context (bounded, not full-store); validated binding + API-drift guardrails; ensure retrieval fault tolerance.
6. **Phase 10:** Write offline tests (memory store, ingestion, persistence & durability across sessions/runs, retrieval, guardrails, retrieval fault tolerance, loop integration) under the no-network suite.
7. **Phase 11:** Run the full quality gate + offline test run, then optionally run the real-agent cold-vs-warm A/B from `../poor-richard/docs/test_plan.md`.

**Success criteria:** all listed in §12 — memory is an offline, verified-data-grounded, NOOA-native, opt-in, layered capability that preserves the core design and preserves API-drift guardrails.
