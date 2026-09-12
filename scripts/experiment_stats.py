#!/usr/bin/env python3
"""Per-experiment stats from the NOOA trace viewer, for batch A/B comparison.

Queries the running viewer's API (default ``127.0.0.1:5001``) and reports, for
each experiment (tagged via ``TRACE_EXPERIMENT=<name>`` when running
``poor-richard-agent --batch``): the sessions in it, the question each session
answered, and per-question plus aggregate durations.

Usage:
    python scripts/experiment_stats.py                  # all experiments
    python scripts/experiment_stats.py -e before -e after
    python scripts/experiment_stats.py --json           # machine-readable

Exit codes: 0 ok, 1 viewer unreachable / bad response, 2 unknown experiment.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

_SPAN_ATTR_KEYS = ("input.value",)


def _get(base: str, path: str) -> dict:
    """GET *path* from the viewer and decode the JSON body."""
    with urllib.request.urlopen(f"{base}{path}", timeout=15) as resp:
        return json.load(resp)


def _list_sessions(base: str, experiment: str) -> list[dict]:
    """All sessions of *experiment*, paginating the session list API."""
    sessions: list[dict] = []
    page = 1
    while True:
        params = urllib.parse.urlencode(
            {"experiment": experiment, "page": page, "limit": 500}
        )
        data = _get(base, f"/api/traces?{params}")
        sessions.extend(data["traces"])
        if not data["has_more"]:
            return sessions
        page += 1


def _session_detail(base: str, session_id: str) -> tuple[str | None, float | None]:
    """Return ``(topic, duration_s)`` from the session's ``method.research`` span.

    The topic comes from the span's ``input.value`` attribute
    (``{"args": ["<topic>"]}``); the duration from its start/end nanos.
    Either may be ``None`` when the span or field is absent.
    """
    data = _get(base, f"/api/trace?session_id={urllib.parse.quote(session_id)}")
    for span in data.get("events", []):
        if span.get("name") != "method.research":
            continue
        attrs = {a["key"]: a.get("value", {}) for a in span.get("attributes", [])}
        topic: str | None = None
        raw = attrs.get("input.value", {}).get("stringValue")
        if raw:
            try:
                topic = json.loads(raw)["args"][0]
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                pass
        start = int(span.get("startTimeUnixNano") or 0)
        end = int(span.get("endTimeUnixNano") or 0)
        duration = (end - start) / 1e9 if end > start else None
        return topic, duration
    return None, None


def _experiment_stats(base: str, experiment: str) -> dict:
    """Collect per-session rows and aggregates for one experiment."""
    sessions = sorted(_list_sessions(base, experiment), key=lambda s: s["id"])
    rows: list[dict] = []
    for s in sessions:
        topic, duration = _session_detail(base, s["id"])
        rows.append(
            {
                "session_id": s["id"],
                "topic": topic,
                "duration_s": round(duration, 1) if duration is not None else None,
                "span_count": s.get("event_count"),
            }
        )
    durations = [r["duration_s"] for r in rows if r["duration_s"] is not None]
    return {
        "session_count": len(rows),
        "span_count": sum(r["span_count"] or 0 for r in rows),
        "total_duration_s": round(sum(durations), 1) if durations else None,
        "avg_duration_s": round(sum(durations) / len(durations), 1) if durations else None,
        "min_duration_s": round(min(durations), 1) if durations else None,
        "max_duration_s": round(max(durations), 1) if durations else None,
        "sessions": rows,
    }


def _print_table(experiment: str, stats: dict) -> None:
    print(f"experiment: {experiment}")
    print(
        f"  {stats['session_count']} sessions, {stats['span_count']} spans"
    )
    print(f"  {'#':>3}  {'session':>28}  {'time':>7}  question")
    for number, row in enumerate(stats["sessions"], start=1):
        duration = f"{row['duration_s']:.1f}s" if row["duration_s"] is not None else "-"
        topic = (row["topic"] or "?")[:60]
        print(f"  {number:>3}  {row['session_id']:>28}  {duration:>7}  {topic}")
    if stats["total_duration_s"] is not None:
        print(
            f"  total {stats['total_duration_s']}s  avg {stats['avg_duration_s']}s"
            f"  min {stats['min_duration_s']}s  max {stats['max_duration_s']}s"
        )
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Per-experiment stats from the NOOA trace viewer API."
    )
    parser.add_argument("--host", default="127.0.0.1", help="viewer host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5001, help="viewer port (default: 5001)")
    parser.add_argument(
        "-e",
        "--experiment",
        action="append",
        metavar="NAME",
        help="only this experiment (repeatable); default: all",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args()

    base = f"http://{args.host}:{args.port}"
    try:
        known = _get(base, "/api/experiments")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"experiment-stats: cannot reach viewer at {base}: {exc}", file=sys.stderr)
        return 1

    if args.experiment:
        unknown = [e for e in args.experiment if e not in known]
        if unknown:
            print(
                f"experiment-stats: unknown experiment(s): {', '.join(unknown)};"
                f" known: {', '.join(known)}",
                file=sys.stderr,
            )
            return 2
        experiments = list(dict.fromkeys(args.experiment))
    else:
        experiments = known

    result: dict[str, dict] = {}
    try:
        for experiment in experiments:
            result[experiment] = _experiment_stats(base, experiment)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"experiment-stats: viewer error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for experiment in experiments:
            _print_table(experiment, result[experiment])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
