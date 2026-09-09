# poor-richard-agent

A [NOOA](https://arxiv.org/abs/2607.20709) agent that answers a factual question
using the [Poor Richard almanack](https://github.com/brian-learns/poor-richard) —
a curated set of 43 offline Python reference libraries (ISO codes, physical
constants, unit conversions, holiday and business-day calendars, celestial
ephemerides, checksum validation, ...). No memory, no network at runtime: the only
LLM loop is NOOA's, and every answer comes from the almanack's verified data.

The agent is a single Python class (`src/poor_richard_agent/agent.py`); the
model-facing surface:

- `await self.almanack.search(query, top=3)` — deterministic; ranks the almanack's
  libraries against the question (up to 3 `SearchHit`, each carrying the card's
  best-matched golden question and its verified answer). A ranking helper — not the
  full set of available libraries.
- `await self.almanack.get(card_id)` — deterministic; returns a flat `CardDetail`
  (all golden questions with verified answers, the pinned `example`, and the
  `notes` that guard against API drift).
- `research(topic)` — agentic (CodeAct, `...` body): the model picks the right
  library from the full catalog in its system prompt, fetches the card, and either
  reads the matching golden question's verified answer or calls the library to
  compute one, then returns a validated `ResearchReport` (discovered hits,
  answers, offline flag, note).
- `today` — state field (weekday, date, local time + UTC offset) visible to the model
  so it can resolve relative dates like "next NYSE session".

The agent's system prompt embeds the **full catalog of all 43 libraries** (id,
import name, archetypes, provenance) via `library_catalog()`, so the model can see
every installed library — not just the top search hits — and pick by what each
references.

The two tools are plain Python in `PoorRichardSkill`
(`src/poor_richard_agent/skills.py`), registered under the `nooa.skills`
entry-point group so any NOOA agent can opt in via
`SkillRegistry(self).activate(["poor-richard.almanack"])`.

## Prerequisites

- A `llama-server` router (OpenAI-compatible). Defaults: `http://127.0.0.1:8080/v1`
  with model `Qwen3.6-35B-A3B-MXFP4_MOE`; override with `NOOA_MODEL` / `NOOA_LLM_BASE`.
- The `poor-richard` almanack (a dependency, pulled from git). Its one
  data-dependent card, `financedatabase`, needs a one-time fetch on a fresh
  machine (the almanack's `scripts/fetch_financedatabase.py`); its test skips if
  the data is absent.

## Usage

Starting the nooa dev console first and leaving it open makes it easy to review
the agent traces.

```
export NOOA_VIEWER_AUTH_TOKEN=$(openssl rand -hex 16)
uv run nooa start-dev -h 0.0.0.0
```

Then run the agent:

```
uv run poor-richard-agent "What is the ISO 3166-1 alpha-3 code for France?"
```

It prints the validated `ResearchReport` as JSON. Exit codes: 0 ok (answers
found), 1 no match / research error, 2 usage error.

## Notes

- **Offline-first**: the agent makes no network calls at runtime; it only reads the
  almanack's bundled, offline-verified data. A pass in the offline test suite
  therefore means correct *and* offline.
- **Verified or computed answers**: each answer is either the almanack card's golden
  `expected` value or a value computed by calling the installed library — never
  something the model recalls. The card's `notes`/`example` pin the API shape at the
  installed version — the agent is told to prefer those over its own memory of the
  library.
- **Discovery, not guessing**: the full 43-library catalog (id, import name,
  archetypes, provenance) is in the system prompt, so the model sees every installed
  library and picks by what each references; `search()` (token coverage + name
  similarity) is a ranking helper, not the only path.
- The validated return is a flat pydantic `ResearchReport` (`models.py`); it never
  embeds the almanack's internal dataclasses.
- Thinking is disabled for the NOOA loop via `chat_template_kwargs` (litellm
  `extra_body`) for speed.
