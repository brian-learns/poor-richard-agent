---
name: poor-richard-agent
description: NOOA agent that answers factual questions offline from the Poor Richard almanack (43 curated Python libraries - ISO codes, constants, unit conversions, holiday/business-day calendars, ephemerides, checksum validation). Use when asked a factual question in these domains and an authoritative offline answer is preferred over a web lookup. One CLI call in, one validated JSON ResearchReport out.
---

# poor-richard-agent

A NOOA agent that turns a factual question into an authoritative, offline answer
by discovering the right library from the Poor Richard almanack and returning its
verified golden answer. One command in, one validated JSON `ResearchReport` out.

## CLI

```
poor-richard-agent "What is the ISO 3166-1 alpha-3 code for France?"
```

Prints the validated `ResearchReport` as JSON:

- `topic` — the question asked.
- `discovered` — up to 3 ranked cards from `search()` (card_id, pypi, import_name,
  the matched golden question + its verified answer). A ranking hint, not the full
  set of available libraries.
- `answers` — the answer(s): a verified golden `expected` when a card question
  matches, otherwise a value computed by calling the library (question asked,
  expected, notes with the pinned API shape).
- `offline` — always true (no runtime network).
- `note` — the import + API shape used, or why nothing could answer.

Exit codes: 0 ok (answers found), 1 no match / research error, 2 usage error.

If working inside the project, prefix commands with `uv run`; if the package is
installed, call `poor-richard-agent` directly.

## Prerequisites

- A `llama-server` router (OpenAI-compatible). Defaults: `http://127.0.0.1:8080/v1`,
  model `Qwen3.6-35B-A3B-MXFP4_MOE`; override with `NOOA_MODEL` / `NOOA_LLM_BASE`.
- The `poor-richard` almanack is a dependency (pulled from git). Its one
  data-dependent card, `financedatabase`, needs a one-time fetch on a fresh machine.

## How it works (for the agent)

The agent is one NOOA `Agent` class (`PoorRichardAgent`). Its system prompt
embeds the **full catalog of all 43 installed libraries** (rendered by
`library_catalog()` from `poor_richard.CARDS`), one line each:
`card_id (import <import_name>)? [archetypes]: provenance`. This is the source of
truth for what is available — the model picks the library whose provenance fits,
rather than trusting the top search hits. It has two deterministic tools on
`self.almanack` (a `PoorRichardSkill`):

- `await self.almanack.search(topic)` — a ranking helper; returns up to 3
  `SearchHit`s (card_id, pypi, import_name, the matched golden question + answer).
  Not the full set — a library absent from the hits may still be the right one.
- `await self.almanack.get(card_id)` — a `CardDetail` with `card_id`,
  `import_name`, `pypi`, `questions` (each with `question`/`expected`/`status`),
  `notes` (API-drift guardrails), and `example`. Use these exact field names —
  the card's id is `card_id` (matching the search hits), not `id`.

The single agentic method `research(topic)` (CodeAct) picks a library from the
catalog, fetches its card, and either reads the matching golden question's verified
`expected` or — when no question matches — `import`s the library in a cell and
computes the answer. It returns the validated `ResearchReport`. Resolve relative
dates against the `today` state field. Prefer the card's `notes`/`example` API
shape over your own memory of the library.

## Gotchas

- Answers come from the almanack, not model recall: either a card's **verified
  golden `expected`** or a value **computed by calling the installed library**.
  Do not "correct" either from memory; if a value looks wrong, say so in `note`.
- Several libraries have APIs that differ from older docs; the card's `notes`/`example`
  are pinned to the installed version and verified offline.
- `search()` ranks only a few hits; the full catalog in the system prompt is the
  source of truth for what is installed (e.g. `skyfield` computes rise/set times
  even though its golden question is about the J2000 epoch).
- No network at runtime; the offline test suite blocks sockets, so a passing test is
  both correct and offline.
