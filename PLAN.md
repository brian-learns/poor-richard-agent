# Plan: Using Agent Memory to Remember Almanack Library Details

**Status:** Proposed — draft plan
**Date:** 2026-07-24
**Scope:** An opt-in, layered enhancement to `poor-richard-agent` that uses durable agent memory to remember details about the **43 libraries in the Poor Richard almanack** — and how that memory supports the agent's library discovery, API-drift guardrails, and cross-session continuity.

**Companion references:**
- Project: `./README.md`, `./PLAN.md` (existing overall project plan; Phases 0–5 complete).
- Reference paper: `./2607.20709.md` (arXiv 2607.20709, NVIDIA Object-Oriented Agents / NOOA).
- Almanack: `./poor-richard/` — offline-verified 43-library catalog (`registry.py` `CARDS`), `search()` / `get()`, golden-question test linkage, `notes`/`example` API-pin.

---

## 1. Purpose & Objective

`poor-richard-agent` currently answers factual questions **offline-first and self-contained per run, with no agent memory**. Memory is deliberately absent because adding persistent state would contradict the offline-first, sandbox-safe core and risk the model writing from stale training knowledge.

This plan proposes a **separate, opt-in, layered memory capability** that does **not** alter the core design. Memory is a **retrieval / augmentation layer over the almanack's verified data**, not a replacement for it.

The objective:

1. **Durability** — the agent can remember details about each almanack library (id, import name, archetype, provenance, pinned API shape, verified answers, example usages) across **multiple sessions and runs**.
2. **Verified-data-grounded** — every memory entry is sourced exclusively from the almanack's offline-verified `CARDS` data and its golden-question tests. Memory never stores raw model recall.
3. **API-drift guardrails preserved** — memory carries the pinned `notes`/`example` API shape, so a library version change does not let the agent revert to stale knowledge.
4. **NOOA-native** — memory is implemented as typed Python state/context, rendered as prompt material, and validated through NOOA's harness APIs, per the paper's agent-as-a-Python-object model.
5. **Minimal & opt-in** — memory is a focused, layered capability scoped to almanack-library details. It does **not** replace per-run discovery, and it does **not** introduce memory or sub-agent behavior into the core run model.

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
- `PLAN.md` §4.1 explicitly constrains the design: *"Minimal, NOOA-native: no shell tools, no todo list, no memory, no sub-agent."*
- `PLAN.md` §3.5 notes: *"per the almanack's design, no persistent memory is needed — each run is self-contained (no memory, no sub-agent)."*
- `PLAN.md` §8 reinforces: *"No memory, no sub-agent: aligned with the almanack's self-contained, offline-first design and NOOA's P3/P4."*

### 2.3 Constraints the plan must respect

| Constraint | Origin |
|---|---|
| **Offline-first / no network egress** | README, PLAN §4.1/§3.6 |
| **Self-contained per run** (memory is a layer on top, not the run's source of truth) | README, PLAN §4.1/§3.5 |
| **Verified data is the source of truth** (never raw model recall) | README Notes, PLAN §4.4/§4.6 |
| **API-drift guardrails** (`notes`/`example` pin the API shape) | README Notes, PLAN §4.4/§4.6 |
| **NOOA-native** (Python object, typed state/context, docstrings as prompt, validated return) | PLAN §3, `2607.20709.md` §2 |
| **Minimal & scoped** (no bespoke DSL, no UX scope beyond reference-data workflow) | PLAN §3.3/§3.4, §7 |
| **Type-checked & validated** (pydantic models) | PLAN §3.3, §4.5 |

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

### 3.2 NOOA framework & reference agents

- NOOA `Agent` base class with `__init_subclass__` (`llm=` config), `_resolve_system_prompt` (class docstring → system prompt), context blocks, event manager, runtime. Memory integrates through the inherited state/context/runtime, consistent with `ccnget-agent` / `xng-agent`.
- `ccnget-agent` / `xng-agent` are explicitly **self-contained, no-memory** agents; this plan layers memory on top without changing their core behavior.

### 3.3 The Poor Richard almanack — `./poor-richard/`

- `src/poor_richard/registry.py` — `ReferenceCard`, `Question`, `Archetype`, `CARDS` (43 offline-verified cards, schema enforces unique ids, importability, verified-question↔test linkage). `search()` / `get()` are the data-access primitives.
- `docs/reference-cards.md` — question archetypes, evaluation axes (provenance, update model, offline integrity, coverage, precision, LLM output shape), card schema, golden-question test method.
- `docs/personas.md` — Noah (NOOA agent — primary almanack consumer), Hank (terminal agent), Broman (human). Memory benefits the Noah surface most directly; can extend to Hank/Broman session continuity.
- `docs/test_plan.md` — real-agent tasks (T1–T8) with scoring grid (Correct / Conventional / Discovered / Offline) and cold-vs-warm SKILL.md A/B. Memory is a candidate for extending real-agent evaluation.
- `docs/future-directions.md` — §1 discusses keyword field / card-text discipline; memory complements these by reducing per-run discovery cost.

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

### 5.2 Data ingestion — offline, from `CARDS`

- Memory is **re-ingested from the almanack's offline-verified `CARDS`** (and golden-question tests) at construction/update time — an offline, deterministic operation.
- Ingestion is **out-of-loop** (PLAN P3): it happens once at setup or on explicit re-sync, never during the agentic loop.
- Ingestion is **validated**: every entry is type-checked against the almanack schema, so memory is guaranteed consistent with the verified data.
- Memory reflects the almanack's **current** offline-verified state; when almanack data updates, ingestion re-pulls the verified cards (offline).

### 5.3 Persistence — offline, sandbox-safe

- Memory is **persisted locally** (e.g., a structured, sandbox-safe local store — file or in-process persisted) with **no network writes**.
- Storage location is sandbox-safe and confined to the agent's runtime environment; no external/network dependencies.
- Persistence is **reversible** (e.g., backed by a snapshot) if needed for recovery or rollback.
- Concurrent access to shared memory state is guarded where concurrency occurs (NOOA P1/P3).

### 5.4 Activation & context binding

- Memory is accessed as a **typed method** on the agent: `await self.memory.get(topic) -> list[LibraryMemory]` (PLAN P2) — a typed, out-of-loop retrieval, not text-only exchange.
- Retrieved library details are **bound to the model-visible state** (e.g., `self.memory` field) and rendered as **prompt material** via docstrings or context blocks, consistent with NOOA's docstrings-as-prompt and context-rendering (paper §2/§3).
- Memory is **validated** before being bound (type + shape), so the model receives only well-formed, verified data.

### 5.5 Retrieval — selective, grounded

Retrieval selects library details relevant to the current turn, complementing the existing `search()` ranking:

- **By query/archetype/provenance** — retrieve cards whose archetype or provenance matches the topic.
- **By topic similarity** — retrieve the most relevant library(s) for the question.
- **Per-library** — surface a known library's pinned API shape when the model has already seen it (e.g., recurring "ISO 3166-1 code" questions).
- **Guardrailed** — retrieval returns only verified, validated entries; it never surfaces raw model recall or unverified data.

---

## 6. Integration with the Existing Agent

### 6.1 `PoorRichardAgent` (`src/poor_richard_agent/agent.py`)

- Add a **`self.memory: LibraryMemory`** state field (NOOA P1: fields = model-visible state). This is opt-in and initialized from ingested almanack data.
- **`__init__`:** construct `LibraryMemory` from the offline-verified `CARDS` (ingestion is offline-safe; no connection until a turn runs). Guard any concurrent initialization.
- **`research(topic)`** (CodeAct loop):
  1. **Context** — resolve relative dates against `self.today` as before.
  2. **Discover** — as before, pick from the system-prompt catalog; **use `self.memory.get(topic)` to surface relevant, known library details** to accelerate discovery (memory is an *augmentation*, not the sole source — catalog-based discovery remains primary).
  3. **Verify or compute** — as before (`search` → `get` → golden answer or computed call). Memory's pinned API shape (`pinned_api`) is consulted to reinforce the **API-drift guardrail**: the model prefers the card's pinned `notes`/`example` over its own recall (per README Notes / PLAN §4.4/§4.6).
  4. **Report** — assemble the validated `ResearchReport`; include memory-sourced details where relevant (e.g., a known library's pinned API shape).
- **System prompt / docstrings** (NOOA §2): the memory store is described in docstrings as prompt material; the agent's self-description includes how memory augments discovery and preserves API guardrails.

### 6.2 Skill tools (`src/poor_richard_agent/skills.py`)

- `memory.get(topic)` is a **deterministic, offline, out-of-loop** retrieval (PLAN P3). It is exposed via the skill surface as a typed tool the model may call.
- Memory retrieval is **not** agentic; it is a plain async Python method wrapping the offline store, consistent with `search`/`get` tools.
- Memory retrieval is **timeout-bounded** (`asyncio.wait_for`) and **resource-hygienic** (cleanup in `finally`), matching the existing tool standards.

### 6.3 Validated models (`src/poor_richard_agent/models.py`)

- Extend pydantic models as needed to represent memory entries (`LibraryMemory`) and any memory-augmented return, **flat fields only** (PLAN §4.5): never embed almanack internals.
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
| **Noah session continuity** (primary consumer) | Memory extends Noah's understanding within and across sessions, aligned with `docs/personas.md` (Noah is the primary almanack consumer). |
| **Hank / Broman continuity** (optional) | Memory can extend terminal-agent and human session continuity, per `docs/personas.md`. |
| **Evaluation continuity** | Memory supports the test plan's (Correct / Conventional / Discovered / Offline) scoring by reducing per-run discovery cost and enabling Conventional/Discovered credit. |

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
- **Concurrency safety:** shared memory state is guarded where concurrent calls occur (NOOA P1/P3).

---

## 10. Risks & Mitigations

| Risk / Open question | Assessment | Mitigation / Decision |
|---|---|---|
| **Stale memory vs. almanack updates** | Medium | Memory is sourced from the almanack's current offline-verified state; ingestion re-pulls verified cards on update (offline). Memory is a *layer*, not the source of truth — verified almanack data always wins. |
| **Memory introducing staleness that conflicts with verified data** | Medium | Memory is an **augmentation/guardrail** layer over verified data; verified almanack answers always take precedence over memory. Memory only supplies context, not answers. |
| **Offline persistence limits** (local-only storage) | Low | Use sandbox-safe, local, reversible persistence (file/in-process); no network. Local persistence is sufficient for offline-first operation. |
| **Concurrency / shared state** | Low | Guard shared memory state where concurrent calls occur; mirror `ccnget`/`xng` shared-resource cleanup (PLAN §3.6). |
| **NOOA version compatibility** | Low | Memory uses NOOA's typed state/context APIs; follow NOOA's API contract and re-verify after any upgrade (PLAN §9 risk row). |
| **Scope creep / core-contradiction risk** | Low | Memory is **opt-in and layered**; it does not change the core no-memory, self-contained design. Memory is a retrieval/augmentation layer, not a replacement. |
| **Memory retrieval cost / context bloat** | Low | Retrieval is selective (not a full catalog re-render); memory is efficient, type-validated, and rendered as minimal prompt material (NOOA context-efficiency §4). |
| **Memory in real-agent evaluation** (test_plan T1–T8, A/B) | Low–Medium | Memory is a candidate for extending real-agent scoring; validate via the offline test suite first, then fold into the cold-vs-warm SKILL.md A/B from `docs/test_plan.md`. |

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
- Add `self.memory` state field to `PoorRichardAgent` (`agent.py`); initialize from ingested data.
- Integrate `memory.get(topic)` into `research(topic)` (§6.1) as a discovery **augmentation**, preserving catalog-based discovery as primary.
- Ensure memory's `pinned_api` enforces API-drift guardrails during verify/compute (§6.1).

### Phase 9 — Retrieval, context binding & guardrails
- Implement **selective retrieval** (`memory.get` by topic/archetype/provenance/per-library) — typed, out-of-loop (§5.5).
- Bind retrieved details to `self.memory` and render as prompt material via docstrings/context (§5.4, NOOA §2).
- Validate binding (type + shape) before model exposure.

### Phase 10 — Testing (offline, no-network)
- **Memory store tests** (offline): ingestion correctness, schema/type validation, persistence round-trip, retrieval selectivity.
- **Memory integration tests** (`test_agent`): `self.memory` construction, ingestion from `CARDS`, retrieval in `research`, validated binding, API-drift guardrail behavior.
- All tests run socket-blocked (autouse `no_network` fixture, adapted from `poor-richard`), mirroring PLAN §6.
- Agentic loop tests: verify memory does not break the CodeAct loop and validated return.

### Phase 11 — Quality gate & integration
- Run full tooling gate (`make check`): ruff, bandit, vulture, refurb, **ty**, **interrogate**, **uv audit** — memory code included (mirrors PLAN §7).
- Docstring coverage ≥90% (NOOA docstrings-as-prompt material).
- Offline test run (`no_network` suite).
- **Real-agent A/B** (optional): install the agent's skill into NOOA test agents, run the cold-vs-warm SKILL.md A/B from `docs/test_plan.md`, and fold memory's contribution into the scoring grid (Correct / Conventional / Discovered / Offline).

---

## 12. Success Criteria

- **Offline & no-network:** memory operations are fully offline; a pass means correctness and no runtime network egress.
- **Verified-data-grounded:** every memory entry is sourced from almanack's offline-verified `CARDS`/golden tests; no raw model recall enters the store.
- **API-drift guardrails:** memory's `pinned_api` is preserved and enforced — the agent prefers the card's pinned `notes`/`example` over its own recall.
- **NOOA-native:** memory is typed state/context, validated via pydantic, rendered as prompt material via docstrings, and exposed via NOOA's harness APIs.
- **Minimal & opt-in:** memory is a layered, opt-in capability that does **not** alter the core no-memory, self-contained design.
- **Tests:** memory store + integration tests pass offline (no-network), covering ingestion, persistence, retrieval, guardrails, and loop integration.
- **Tooling gate:** full quality gate (ruff/bandit/ty/vulture/refurb/interrogate/audit) green, 100% docstring coverage.
- **Real-agent (optional):** memory contribution validated in the cold-vs-warm SKILL.md A/B from `docs/test_plan.md`.

---

## 13. Constraints & Trade-offs

- **Core design preserved:** memory is opt-in and layered; the core offline-first, self-contained, no-memory run model is unchanged. Memory does **not** replace per-run discovery.
- **Memory is not the answer source:** verified almanack data (catalog + golden answers) always remain the source of truth. Memory is a retrieval/augmentation and guardrail layer.
- **Local-only persistence:** memory persistence is offline/sandbox-safe (local, reversible); no network is introduced.
- **Scoping:** memory is focused on almanack-library details only — no UX scope beyond the reference-data workflow.
- **Augmentation over replacement:** memory accelerates and enriches discovery but does not replace the system-prompt catalog or `search()` ranking.

---

## 14. Next Steps

1. **Phase 6:** Define `LibraryMemory` model + offline ingestion from `CARDS`/golden tests.
2. **Phase 7:** Implement offline, sandbox-safe persistence + concurrency guarding.
3. **Phase 8:** Integrate `self.memory` into `PoorRichardAgent` and `research(topic)` as a discovery augmentation.
4. **Phase 9:** Implement selective retrieval + validated context binding + API-drift guardrails.
5. **Phase 10:** Write offline tests (memory store, integration, loop) under the no-network suite.
6. **Phase 11:** Run the full quality gate + offline test run, then optionally run the real-agent cold-vs-warm A/B from `docs/test_plan.md`.

**Success criteria:** all listed in §12 — memory is an offline, verified-data-grounded, NOOA-native, opt-in, layered capability that preserves the core design and preserves API-drift guardrails.
