#!/usr/bin/env python3
"""Compare baseline vs candidate trigger-eval reports."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict


SCHEMA = "aidd.trigger_eval.compare.v1"


def _read(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid JSON object: {path}")
    return payload


def _pct_delta(base: float, cand: float) -> float:
    if base == 0:
        return 0.0 if cand == 0 else 100.0
    return ((cand - base) / base) * 100.0


def run(args: argparse.Namespace) -> int:
    baseline_path = Path(args.baseline).resolve()
    candidate_path = Path(args.candidate).resolve()
    out_path = Path(args.out).resolve()

    baseline = _read(baseline_path)
    candidate = _read(candidate_path)

    b = baseline.get("summary") or {}
    c = candidate.get("summary") or {}

    b_pass = float(b.get("pass_rate") or 0.0)
    c_pass = float(c.get("pass_rate") or 0.0)

    b_duration = b.get("duration") or {}
    c_duration = c.get("duration") or {}
    b_tokens = b.get("tokens") or {}
    c_tokens = c.get("tokens") or {}
    c_variance = c.get("variance") or {}

    b_dur_p50 = float(b_duration.get("p50") or 0.0)
    c_dur_p50 = float(c_duration.get("p50") or 0.0)
    b_tokens_mean = float(b_tokens.get("mean") or 0.0)
    c_tokens_mean = float(c_tokens.get("mean") or 0.0)

    per_skill = c.get("per_skill") or c.get("summary", {}).get("per_skill") or {}
    per_skill_pass = {k: float((v or {}).get("pass_rate") or 0.0) for k, v in per_skill.items()}

    criteria = {
        "overall_pass_rate_ge_0_90": c_pass >= args.min_overall_pass_rate,
        "per_skill_pass_rate_ge_0_85": all(value >= args.min_skill_pass_rate for value in per_skill_pass.values()),
        "duration_p50_growth_pct_le_15": _pct_delta(b_dur_p50, c_dur_p50) <= args.max_duration_growth_pct,
        "tokens_mean_growth_pct_le_10": _pct_delta(b_tokens_mean, c_tokens_mean) <= args.max_tokens_growth_pct,
        "variance_pass_rate_le_0_05": float(c_variance.get("pass_rate") or 0.0) <= args.max_pass_rate_variance,
    }

    comparison = {
        "schema": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "baseline": str(baseline_path),
        "candidate": str(candidate_path),
        "metrics": {
            "baseline": {
                "pass_rate": b_pass,
                "duration_p50": b_dur_p50,
                "tokens_mean": b_tokens_mean,
            },
            "candidate": {
                "pass_rate": c_pass,
                "duration_p50": c_dur_p50,
                "tokens_mean": c_tokens_mean,
                "per_skill": per_skill,
                "variance": c_variance,
            },
            "delta": {
                "pass_rate_abs": c_pass - b_pass,
                "duration_p50_pct": _pct_delta(b_dur_p50, c_dur_p50),
                "tokens_mean_pct": _pct_delta(b_tokens_mean, c_tokens_mean),
            },
        },
        "criteria": criteria,
        "all_criteria_pass": all(criteria.values()),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[trigger-eval-compare] wrote {out_path}")
    print(f"[trigger-eval-compare] all_criteria_pass={comparison['all_criteria_pass']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare trigger-eval reports.")
    parser.add_argument("--baseline", required=True, help="Baseline trigger-eval JSON.")
    parser.add_argument("--candidate", required=True, help="Candidate trigger-eval JSON.")
    parser.add_argument("--out", required=True, help="Output comparison JSON.")
    parser.add_argument("--min-overall-pass-rate", type=float, default=0.90)
    parser.add_argument("--min-skill-pass-rate", type=float, default=0.85)
    parser.add_argument("--max-duration-growth-pct", type=float, default=15.0)
    parser.add_argument("--max-tokens-growth-pct", type=float, default=10.0)
    parser.add_argument("--max-pass-rate-variance", type=float, default=0.05)
    return parser


if __name__ == "__main__":
    parser = build_parser()
    raise SystemExit(run(parser.parse_args()))
