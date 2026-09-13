# poor-richard-agent

A [NOOA](https://arxiv.org/abs/2607.20709) agent that answers a factual question
using the [Poor Richard almanack](https://github.com/brian-learns/poor-richard)

The agent is a single Python class (`src/poor_richard_agent/agent.py`); the
model-facing surface:

## Usage

Starting the nooa dev console first and leaving it open makes it easy to review
the agent traces.

```
export NOOA_VIEWER_AUTH_TOKEN=$(openssl rand -hex 16)
uv run nooa start-dev -h 0.0.0.0
```

Then run the agent:

```
uv run poor-richard-agent --prompt "What is the ISO 3166-1 alpha-3 code for France?"
```

It prints the validated `ResearchReport` as JSON. Exit codes: 0 ok (answers
found), 1 no match / research error, 2 usage error.

Batch mode: `--batch FILE` runs the agent in series over a file of questions
(one per non-empty line), printing one report per question:

```
uv run poor-richard-agent --batch tests/test_questions.txt
```

get all extras
```
uv sync --all-extras
```

