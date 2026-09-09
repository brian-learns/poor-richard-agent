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
- `discovered` — up to 3 ranked cards (card_id, pypi, import_name, the matched
  golden question + its verified answer).
- `answers` — the verified answer(s) assembled from the best card (question,
  expected, notes with the pinned API shape).
- `offline` — always true (no runtime network).
- `note` — recommended import + API shape, or why nothing matched.

Exit codes: 0 ok (answers found), 1 no match / research error, 2 usage error.

If working inside the project, prefix commands with `uv run`; if the package is
installed, call `poor-richard-agent` directly.

## Prerequisites

- A `llama-server` router (OpenAI-compatible). Defaults: `http://127.0.0.1:8080/v1`,
  model `Qwen3.6-35B-A3B-MXFP4_MOE`; override with `NOOA_MODEL` / `NOOA_LLM_BASE`.
- The `poor-richard` almanack is a dependency (pulled from git). Its one
  data-dependent card, `financedatabase`, needs a one-time fetch on a fresh machine.

## How it works (for the agent)

The agent is one NOOA `Agent` class (`PoorRichardAgent`) with two deterministic
tools on `self.almanack` (a `PoorRichardSkill`):

- `await self.almanack.search(topic)` — rank the 43 libraries; returns `SearchHit`s
  with each card's best-matched golden question + verified answer.
- `await self.almanack.get(card_id)` — the full `ReferenceCard` (all golden
  questions, the pinned `example`, and the `notes` that guard against API drift).

The single agentic method `research(topic)` (CodeAct) discovers, verifies against
the card's golden question, and returns the validated `ResearchReport`. Resolve
relative dates against the `today` state field. Prefer the card's `notes`/`example`
API shape over your own memory of the library.

## Gotchas

- Answers are the almanack's **verified golden values**, not model recall — do not
  "correct" an `expected` value from memory; if it looks wrong, say so in `note`.
- Several libraries have APIs that differ from older docs; the card's `notes`/`example`
  are pinned to the installed version and verified offline.
- No network at runtime; the offline test suite blocks sockets, so a passing test is
  both correct and offline.
