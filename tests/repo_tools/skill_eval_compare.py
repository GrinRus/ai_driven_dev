#!/usr/bin/env python3
"""Compare baseline and candidate skill eval summaries."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

from skill_eval_common import DELTA_SCHEMA, bool_env, load_json, utc_now, write_json

DEFAULT_POLICY = {
    "advisory_window": {
        "min_prs": 10,
        "min_days": 14,
        "required_consecutive_nightly": 3,
    },
    "hard_thresholds": {
        "macro_trigger_f1": 0.90,
        "exact_match_rate": 0.88,
        "completion_proxy_pass_rate": 0.92,
        "critical_skill_recall": 0.85,
    },
    "regression_guard": {
        "max_drop": 0.02,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare skill eval summaries.")
    parser.add_argument("--baseline", required=True, type=Path, help="Baseline summary.json path")
    parser.add_argument("--candidate", required=True, type=Path, help="Candidate summary.json path")
    parser.add_argument("--out", required=True, type=Path, help="Output delta JSON path")
    parser.add_argument(
        "--policy",
        required=False,
        type=Path,
        default=Path("tests/repo_tools/skill_eval/policy.v1.json"),
        help="Skill eval policy JSON path.",
    )
    return parser.parse_args()


def _metric(payload: Dict[str, Any], key: str) -> float:
    metrics = payload.get("metrics") or {}
    try:
        return float(metrics.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _critical_recalls(payload: Dict[str, Any]) -> Dict[str, float]:
    raw = payload.get("critical_skill_recall") or {}
    out: Dict[str, float] = {}
    for key, value in raw.items():
        try:
            out[str(key)] = float(value)
        except (TypeError, ValueError):
            out[str(key)] = 0.0
    return out


def _env_int(name: str, default: int = 0) -> int:
    raw = str(os.environ.get(name, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _load_policy(path: Path) -> Dict[str, Any]:
    policy = dict(DEFAULT_POLICY)
    if not path.exists():
        return policy
    loaded = load_json(path)
    if not isinstance(loaded, dict):
        return policy
    for key in ("advisory_window", "hard_thresholds", "regression_guard"):
        if isinstance(loaded.get(key), dict):
            policy[key] = dict(policy.get(key, {}), **loaded[key])
    return policy


def main() -> int:
    args = parse_args()
    enforce = bool_env("AIDD_SKILL_EVAL_ENFORCE", default=False)
    policy = _load_policy(args.policy)

    baseline = load_json(args.baseline)
    candidate = load_json(args.candidate)

    hard_thresholds = policy.get("hard_thresholds") or {}
    regression_guard = policy.get("regression_guard") or {}
    advisory_window = policy.get("advisory_window") or {}
    critical_recall_min = float(hard_thresholds.get("critical_skill_recall") or 0.85)
    regression_max_drop = float(regression_guard.get("max_drop") or 0.02)

    advisory_prs = _env_int("AIDD_SKILL_EVAL_ADVISORY_PRS", 0)
    advisory_days = _env_int("AIDD_SKILL_EVAL_ADVISORY_DAYS", 0)
    nightly_streak = _env_int("AIDD_SKILL_EVAL_NIGHTLY_STREAK", 0)
    hard_switch_ready = (
        advisory_prs >= int(advisory_window.get("min_prs") or 10)
        and advisory_days >= int(advisory_window.get("min_days") or 14)
        and nightly_streak >= int(advisory_window.get("required_consecutive_nightly") or 3)
    )

    baseline_status = str(baseline.get("status") or "")
    candidate_status = str(candidate.get("status") or "")

    findings: list[str] = []
    status = "ok"

    if baseline_status != "completed":
        findings.append(f"baseline status is `{baseline_status}` (expected `completed`)")
        status = "warn"

    if candidate_status != "completed":
        findings.append(f"candidate status is `{candidate_status}` (expected `completed`)")
        status = "warn"
        if enforce:
            status = "failed"

    metric_deltas: Dict[str, Dict[str, float]] = {}
    for key in ("macro_trigger_f1", "exact_match_rate", "completion_proxy_pass_rate"):
        threshold = float(hard_thresholds.get(key) or 0.0)
        base = _metric(baseline, key)
        cand = _metric(candidate, key)
        delta = cand - base
        metric_deltas[key] = {"baseline": round(base, 6), "candidate": round(cand, 6), "delta": round(delta, 6)}
        if candidate_status == "completed":
            if cand < threshold:
                findings.append(
                    f"hard-threshold miss: {key}={cand:.3f} < {threshold:.3f}"
                )
                if enforce:
                    status = "failed"
                elif status == "ok":
                    status = "warn"
            if delta < -regression_max_drop:
                findings.append(
                    f"regression: {key} dropped by {abs(delta):.3f} (> {regression_max_drop:.3f})"
                )
                if enforce:
                    status = "failed"
                elif status == "ok":
                    status = "warn"

    baseline_recalls = _critical_recalls(baseline)
    candidate_recalls = _critical_recalls(candidate)
    recall_deltas: Dict[str, Dict[str, float]] = {}
    for skill in sorted(set(baseline_recalls) | set(candidate_recalls)):
        base = baseline_recalls.get(skill, 0.0)
        cand = candidate_recalls.get(skill, 0.0)
        delta = cand - base
        recall_deltas[skill] = {
            "baseline": round(base, 6),
            "candidate": round(cand, 6),
            "delta": round(delta, 6),
        }
        if candidate_status == "completed":
            if cand < critical_recall_min:
                findings.append(
                    f"hard-threshold miss: critical_skill_recall[{skill}]={cand:.3f} < {critical_recall_min:.3f}"
                )
                if enforce:
                    status = "failed"
                elif status == "ok":
                    status = "warn"
            if delta < -regression_max_drop:
                findings.append(
                    f"regression: critical_skill_recall[{skill}] dropped by {abs(delta):.3f} (> {regression_max_drop:.3f})"
                )
                if enforce:
                    status = "failed"
                elif status == "ok":
                    status = "warn"

    if enforce and not hard_switch_ready:
        findings.append(
            "policy gate: hard enforcement enabled before advisory window criteria "
            f"(prs={advisory_prs}, days={advisory_days}, nightly_streak={nightly_streak})"
        )
        status = "failed"
    elif not enforce and hard_switch_ready and status == "ok":
        status = "ready_for_hard_switch"

    payload = {
        "schema": DELTA_SCHEMA,
        "pack_version": "1",
        "generated_at": utc_now(),
        "enforced": enforce,
        "status": status,
        "policy_path": args.policy.as_posix(),
        "thresholds": {
            **hard_thresholds,
            "regression_max_drop": regression_max_drop,
        },
        "advisory_window": advisory_window,
        "advisory_progress": {
            "prs": advisory_prs,
            "days": advisory_days,
            "consecutive_nightly": nightly_streak,
            "hard_switch_ready": hard_switch_ready,
        },
        "metrics": metric_deltas,
        "critical_skill_recall": recall_deltas,
        "findings": findings,
        "baseline": args.baseline.as_posix(),
        "candidate": args.candidate.as_posix(),
    }
    write_json(args.out, payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    if status == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
