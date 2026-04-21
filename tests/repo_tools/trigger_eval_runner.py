#!/usr/bin/env python3
"""Run trigger-routing benchmark cases with codex exec JSON output."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import shlex
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA = "aidd.trigger_eval.v1"


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(math.floor(rank))
    high = int(math.ceil(rank))
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _safe_mean(values: List[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _safe_stdev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def _build_allowed_routes(dataset: Dict[str, Any]) -> List[str]:
    routes = set()
    for case in dataset.get("cases", []):
        target = str(case.get("target_skill") or "").strip()
        if target:
            routes.add(target)
        expected_else = case.get("expected_route_if_not")
        if expected_else is not None:
            text = str(expected_else).strip()
            if text:
                routes.add(text)
    routes.add("none")
    return sorted(routes)


def _build_prompt(query: str, allowed_routes: List[str]) -> str:
    choices = ", ".join(allowed_routes)
    return (
        "Route the request to exactly one AIDD stage skill route.\n"
        f"Allowed routes: {choices}.\n"
        "Return JSON only with format: {\"route\":\"<allowed-route>\",\"reason\":\"short\"}.\n"
        "If nothing should trigger, return route=none.\n"
        f"User request:\n{query}\n"
    )


def _parse_json_lines(raw: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _extract_agent_message(events: List[Dict[str, Any]]) -> str:
    message = ""
    for event in events:
        # Legacy --json format
        msg = event.get("msg")
        if isinstance(msg, dict) and msg.get("type") == "agent_message":
            message = str(msg.get("message") or "")
            continue
        # Experimental JSON format
        if str(event.get("type") or "") == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and str(item.get("item_type") or "") == "assistant_message":
                message = str(item.get("text") or "")
    return message.strip()


def _extract_total_tokens(events: List[Dict[str, Any]]) -> Optional[int]:
    last_tokens: Optional[int] = None
    for event in events:
        # Legacy --json format
        msg = event.get("msg")
        if not isinstance(msg, dict) or msg.get("type") != "token_count":
            # Experimental JSON currently may expose counters as top-level telemetry.
            usage = event.get("usage")
            if isinstance(usage, dict):
                total = usage.get("total_tokens")
                if isinstance(total, int):
                    last_tokens = total
            continue
        info = msg.get("info")
        if isinstance(info, dict):
            usage = info.get("total_token_usage")
            if isinstance(usage, dict):
                total = usage.get("total_tokens")
                if isinstance(total, int):
                    last_tokens = total
    return last_tokens


def _extract_error(events: List[Dict[str, Any]]) -> str:
    for event in events:
        # Legacy --json format
        msg = event.get("msg")
        if isinstance(msg, dict) and msg.get("type") == "error":
            return str(msg.get("message") or "").strip()
        # Experimental JSON format
        if str(event.get("type") or "") == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and str(item.get("item_type") or "") == "error":
                return str(item.get("text") or item.get("message") or "").strip()
    return ""


def _normalize_route(route: str, allowed_routes: List[str]) -> str:
    value = str(route or "").strip().lower()
    if value in allowed_routes:
        return value
    return "none"


def _extract_route(agent_message: str, allowed_routes: List[str]) -> str:
    message = agent_message.strip()
    if not message:
        return "none"
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        route = _normalize_route(str(payload.get("route") or ""), allowed_routes)
        return route

    lower = message.lower()
    candidates = sorted((route for route in allowed_routes if route != "none"), key=len, reverse=True)
    for route in candidates:
        pattern = re.compile(rf"(?<![a-z0-9-]){re.escape(route)}(?![a-z0-9-])")
        if pattern.search(lower):
            return route
    if re.search(r"(?<![a-z0-9-])none(?![a-z0-9-])", lower):
        return "none"
    for route in candidates:
        # Fallback for unexpected punctuation/tokenization around route names.
        if route in lower:
            return route
    if "none" in lower:
        return "none"
    return "none"


def _expected_route(case: Dict[str, Any]) -> str:
    should_trigger = bool(case.get("should_trigger"))
    target_skill = str(case.get("target_skill") or "").strip()
    if should_trigger:
        return target_skill
    fallback = case.get("expected_route_if_not")
    return str(fallback if fallback is not None else "none").strip() or "none"


def _run_one_case(
    *,
    codex_cmd: str,
    prompt: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    full_cmd = f"{codex_cmd} {shlex.quote(prompt)}"
    started = time.monotonic()
    try:
        completed = subprocess.run(
            full_cmd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        return {
            "exit_code": 124,
            "duration_sec": elapsed,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timeout": True,
        }
    elapsed = time.monotonic() - started
    return {
        "exit_code": int(completed.returncode),
        "duration_sec": elapsed,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timeout": False,
    }


def run(args: argparse.Namespace) -> int:
    dataset_path = Path(args.dataset).resolve()
    out_path = Path(args.out).resolve()
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = list(payload.get("cases") or [])
    if not cases:
        raise SystemExit("dataset must contain non-empty `cases`")

    allowed_routes = _build_allowed_routes(payload)
    if not any(token in args.codex_cmd for token in ("--json", "--experimental-json")):
        raise SystemExit("--codex-cmd must include --json or --experimental-json")

    results: List[Dict[str, Any]] = []
    per_repeat: Dict[int, Dict[str, List[float]]] = {}

    for repeat in range(1, args.repeats + 1):
        repeat_correct = 0
        repeat_total = 0
        repeat_durations: List[float] = []
        repeat_tokens: List[float] = []
        for case in cases:
            case_id = str(case.get("id") or "")
            query = str(case.get("query") or "").strip()
            expected = _expected_route(case)
            prompt = _build_prompt(query, allowed_routes)
            run_data = _run_one_case(codex_cmd=args.codex_cmd, prompt=prompt, timeout_sec=args.timeout_sec)

            raw = (run_data.get("stdout") or "") + "\n" + (run_data.get("stderr") or "")
            events = _parse_json_lines(raw)
            agent_message = _extract_agent_message(events)
            predicted = _extract_route(agent_message, allowed_routes)
            total_tokens = _extract_total_tokens(events)
            error_text = _extract_error(events)
            timeout = bool(run_data.get("timeout"))
            exit_code = int(run_data.get("exit_code", 1))
            duration_sec = float(run_data.get("duration_sec", 0.0))

            correct = (predicted == expected) and not timeout and exit_code == 0
            repeat_total += 1
            if correct:
                repeat_correct += 1
            repeat_durations.append(duration_sec)
            if isinstance(total_tokens, int):
                repeat_tokens.append(float(total_tokens))

            results.append(
                {
                    "variant": args.variant,
                    "repeat": repeat,
                    "case_id": case_id,
                    "target_skill": case.get("target_skill"),
                    "should_trigger": bool(case.get("should_trigger")),
                    "query": query,
                    "expected_route": expected,
                    "predicted_route": predicted,
                    "correct": correct,
                    "duration_sec": round(duration_sec, 6),
                    "total_tokens": total_tokens,
                    "exit_code": exit_code,
                    "timeout": timeout,
                    "error": error_text,
                    "agent_message": agent_message,
                }
            )

        pass_rate = (repeat_correct / repeat_total) if repeat_total else 0.0
        per_repeat[repeat] = {
            "pass_rate": [pass_rate],
            "duration_mean": [_safe_mean(repeat_durations)],
            "tokens_mean": [_safe_mean(repeat_tokens)],
        }

    all_durations = [float(item["duration_sec"]) for item in results]
    all_tokens = [float(item["total_tokens"]) for item in results if isinstance(item.get("total_tokens"), int)]
    all_correct = [1.0 if item.get("correct") else 0.0 for item in results]

    skill_stats: Dict[str, Dict[str, float]] = {}
    risky_skills = [str(item.get("skill") or "").strip() for item in payload.get("risky_skills", [])]
    for skill in risky_skills:
        scoped = [row for row in results if str(row.get("target_skill") or "") == skill]
        total = len(scoped)
        correct = sum(1 for row in scoped if row.get("correct"))
        skill_stats[skill] = {
            "correct": correct,
            "total": total,
            "pass_rate": (correct / total) if total else 0.0,
        }

    repeat_pass_rates = [values["pass_rate"][0] for _, values in sorted(per_repeat.items())]
    repeat_duration_means = [values["duration_mean"][0] for _, values in sorted(per_repeat.items())]
    repeat_token_means = [values["tokens_mean"][0] for _, values in sorted(per_repeat.items())]

    summary = {
        "cases": len(cases),
        "repeats": args.repeats,
        "runs": len(results),
        "correct": int(sum(all_correct)),
        "pass_rate": (_safe_mean(all_correct) if all_correct else 0.0),
        "duration": {
            "mean": _safe_mean(all_durations),
            "p50": _percentile(all_durations, 50),
            "p95": _percentile(all_durations, 95),
        },
        "tokens": {
            "samples": len(all_tokens),
            "mean": _safe_mean(all_tokens),
            "p50": _percentile(all_tokens, 50),
            "p95": _percentile(all_tokens, 95),
        },
        "variance": {
            "pass_rate": _safe_stdev(repeat_pass_rates),
            "duration": _safe_stdev(repeat_duration_means),
            "tokens": _safe_stdev(repeat_token_means),
        },
        "per_skill": skill_stats,
    }

    output = {
        "schema": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "variant": args.variant,
        "dataset": str(dataset_path),
        "codex_cmd": args.codex_cmd,
        "allowed_routes": allowed_routes,
        "summary": summary,
        "results": results,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[trigger-eval] wrote {out_path}")
    print(f"[trigger-eval] pass_rate={summary['pass_rate']:.4f} runs={summary['runs']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run trigger-eval benchmark with codex exec.")
    parser.add_argument("--dataset", required=True, help="Path to trigger-eval dataset JSON.")
    parser.add_argument("--variant", required=True, help="Variant label (baseline|with_skill|...).")
    parser.add_argument("--repeats", type=int, default=1, help="How many full dataset repeats to execute.")
    parser.add_argument("--codex-cmd", required=True, help="Base codex command including --json output mode.")
    parser.add_argument("--out", required=True, help="Output JSON report path.")
    parser.add_argument("--timeout-sec", type=int, default=120, help="Timeout per case in seconds.")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    raise SystemExit(run(parser.parse_args()))
