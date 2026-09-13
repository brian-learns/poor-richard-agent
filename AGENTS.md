# AGENTS.md — poor-richard-agent

A [NOOA](https://arxiv.org/abs/2607.20709) agent that answers factual questions
offline from the Poor Richard almanack (curated Python reference libraries).
The README covers architecture; this file covers what you need to work here.

## Run & test

- uv project (Python 3.12–3.13). `make check` (ruff/bandit/vulture/refurb/ty/
  interrogate + lockfile + audit), `make test` (check + pytest), `make format`.
- CLI: `uv run poor-richard-agent --prompt "<question>"` prints the validated
  `ResearchReport` as JSON; `--batch FILE` runs questions (one per non-empty
  line) in series, progress on stderr, one report per question on stdout.
  Per-question LLM turns (BeforeTurn events) and ended-span counts print on
  stderr, with a total in the batch summary. Exit codes: 0 answers found,
  1 no match / error, 2 usage.
- **Offline-first**: the agent makes no network calls at runtime — a green
  test run means correct *and* offline. Don't add runtime network deps.
- LLM: defaults to a local llama-server router (`http://127.0.0.1:8080/v1`);
  the model comes from `NOOA_MODEL` (no hard-coded default) and the base URL
  from `NOOA_LLM_BASE`. Building the client is offline-safe (no connection until
  a turn runs), so importing `poor_richard_agent.agent` is safe in tests.
- `poor-richard` comes from git (see `[tool.uv.sources]`); the `financedatabase`
  card needs a one-time data fetch (`scripts/fetch_financedatabase.py` in that
  repo) — its test skips if the data is absent.
- Traces: `export NOOA_VIEWER_AUTH_TOKEN=$(openssl rand -hex 16)` then
  `uv run nooa start-dev -h 0.0.0.0` for the NOOA dev console. The CLI prints
  each run's session ID on stderr (`session <id>` / batch progress lines),
  deep-linkable as `:5001/traces/view?session_id=<id>`. Each run gets a fresh
  session; tag a batch with `TRACE_EXPERIMENT=<name>` to group it. The /eval
  "Experiments" tab only shows *eval-pipeline* experiments (needs eval
  metadata), so for batch A/B comparison use
  `uv run python scripts/experiment_stats.py [-e NAME] [--json]` (queries the
  running viewer API).

## Wiring a custom LLM (what poor-richard-space does)

- `PoorRichardAgent(llm=client)` — the instance-level llm overrides the class
  default (`llm=nooa_llm`). Build one client per caller/token, e.g.
  `get_llm_client(f"openai/{model}", api_base=..., api_key=...)`.
- If the endpoint is a strict OpenAI-compatible gateway (e.g. HF's router via
  OVHcloud), pass `cache_control_injection_points=[]` to `get_llm_client`:
  NOOA's `CompletionClient` injects Anthropic-style `cache_control` by default
  and strict endpoints 400 (`wrong_api_format`) on it.
- Such gateways also reject provider-specific body params
  (`enable_thinking`, `chat_template_kwargs`) — the llama.cpp
  `extra_body` in `nooa_llm` is for the local router only.

## NOOA event facts (for UIs / trace consumers)

- Every event carries an auto-derived `event_type` discriminator (class name)
  → `event.model_dump_json()` lines are self-describing JSONL.
- `Task.prompt` is NOOA's full task prompt (method docstring + harness
  boilerplate, including `##` headings) — not the user's input.
- The first `PythonOutput` stdout is the execution-context banner (starts
  `Task: `, contains `Return type:`) — boilerplate, identical every run.
- Subscribe with `agent.event_manager.on("*", fn)` (returns an unsubscribe).

## Conventions

- The validated return contract is the flat pydantic models in `models.py`;
  never embed the almanack's internal dataclasses in them.
- Commit messages: imperative subject + short body explaining why.
