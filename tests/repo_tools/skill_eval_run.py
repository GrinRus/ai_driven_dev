#!/usr/bin/env python3
"""Run LLM-based skill routing benchmark."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from skill_eval_common import (
    NO_SKILL,
    SUMMARY_SCHEMA,
    anthropic_messages_create,
    bool_env,
    build_catalog_markdown,
    build_confusion_matrix,
    check_expected_skills_exist,
    compute_metrics,
    extract_first_json_object,
    load_cases,
    load_json,
    load_skill_catalog,
    repo_root,
    safe_float,
    select_cases,
    utc_now,
    write_confusion_csv,
    write_json,
    write_jsonl,
)

ROUTER_SYSTEM = """You are a strict skill router evaluator.
Pick exactly one skill from the provided catalog or __no_skill__.
Return only JSON object: {"predicted_skill":"...", "confidence":0..1, "reason":"..."}.
No markdown, no extra keys.
"""

JUDGE_SYSTEM = """You are a strict evaluation judge.
Assess whether predicted skill routing is correct for expected skills and likely to complete the task.
Return only JSON object: {"pass":true|false, "reason":"..."}.
No markdown, no extra keys.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LLM-only skill eval benchmark.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("tests/repo_tools/skill_eval/cases.v1.jsonl"),
        help="Path to SkillEvalCaseV1 JSONL dataset.",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Optional JSON catalog path. If omitted, catalog is loaded from skills/*/SKILL.md.",
    )
    parser.add_argument(
        "--router-model",
        default=os.environ.get("AIDD_SKILL_EVAL_ROUTER_MODEL", "claude-3-5-haiku-latest"),
        help="Anthropic model for routing prediction.",
    )
    parser.add_argument(
        "--judge-model",
        default=os.environ.get("AIDD_SKILL_EVAL_JUDGE_MODEL", "claude-3-5-haiku-latest"),
        help="Anthropic model for completion proxy judge.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("aidd/reports/events/skill-eval"),
        help="Directory for run artifacts.",
    )
    parser.add_argument("--max-cases", type=int, default=0, help="Optional cap for smoke run.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic shuffle seed.")
    return parser.parse_args()


def load_catalog(path: Path | None) -> List[Dict[str, Any]]:
    if path is None:
        return load_skill_catalog(repo_root() / "skills")
    payload = load_json(path)
    items = payload.get("skills") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError(f"invalid catalog payload in {path}; expected list or {{'skills': [...]}}")
    catalog: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        description = str(item.get("description") or "").strip()
        if name and description:
            catalog.append({"name": name, "description": description})
    if not catalog:
        raise ValueError(f"empty catalog in {path}")
    return catalog


def route_case(
    *,
    api_key: str,
    model: str,
    case: Dict[str, Any],
    catalog_md: str,
    skill_names: set[str],
) -> Dict[str, Any]:
    prompt = (
        "Catalog:\n"
        f"{catalog_md}\n\n"
        "Case:\n"
        f"id: {case['id']}\n"
        f"prompt: {case['prompt']}\n"
        "Choose best skill."
    )
    raw = anthropic_messages_create(
        api_key=api_key,
        model=model,
        system_prompt=ROUTER_SYSTEM,
        user_prompt=prompt,
        temperature=0.0,
        max_tokens=220,
    )
    parsed = extract_first_json_object(raw)
    predicted = str(parsed.get("predicted_skill") or NO_SKILL).strip()
    if predicted not in skill_names and predicted != NO_SKILL:
        predicted = NO_SKILL
    confidence = safe_float(parsed.get("confidence"), default=0.0)
    return {
        "predicted_skill": predicted,
        "router_confidence": round(max(0.0, min(1.0, confidence)), 6),
        "router_reason": str(parsed.get("reason") or "").strip(),
        "router_raw": raw,
    }


def judge_case(
    *,
    api_key: str,
    model: str,
    case: Dict[str, Any],
    predicted_skill: str,
    router_reason: str,
) -> Dict[str, Any]:
    expected = case.get("expected_skills") or []
    prompt = (
        f"Case id: {case['id']}\n"
        f"kind: {case['kind']}\n"
        f"user prompt: {case['prompt']}\n"
        f"expected_skills: {json.dumps(expected)}\n"
        f"predicted_skill: {predicted_skill}\n"
        f"router_reason: {router_reason}\n"
        "Decide if predicted routing is correct and likely to complete this request."
    )
    raw = anthropic_messages_create(
        api_key=api_key,
        model=model,
        system_prompt=JUDGE_SYSTEM,
        user_prompt=prompt,
        temperature=0.0,
        max_tokens=160,
    )
    parsed = extract_first_json_object(raw)
    return {
        "completion_proxy_pass": bool(parsed.get("pass")),
        "judge_reason": str(parsed.get("reason") or "").strip(),
        "judge_raw": raw,
    }


def _write_summary(summary_path: Path, payload: Dict[str, Any]) -> None:
    write_json(summary_path, payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def main() -> int:
    args = parse_args()
    enforce = bool_env("AIDD_SKILL_EVAL_ENFORCE", default=False)

    cases = load_cases(args.cases)
    catalog = load_catalog(args.catalog)
    skill_names = {str(item.get("name") or "").strip() for item in catalog}
    skill_names.discard("")
    check_expected_skills_exist(cases, skill_names)

    selected = select_cases(cases, max_cases=args.max_cases if args.max_cases > 0 else None, seed=args.seed)

    run_id = f"run-{utc_now().replace(':', '').replace('-', '')}"
    run_dir = args.out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "summary.json"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        summary = {
            "schema": SUMMARY_SCHEMA,
            "pack_version": "1",
            "run_id": run_id,
            "generated_at": utc_now(),
            "status": "skipped_missing_api_key",
            "reason_code": "anthropic_api_key_missing",
            "source_path": args.cases.as_posix(),
            "total_cases": len(selected),
            "router_model": args.router_model,
            "judge_model": args.judge_model,
            "enforced": enforce,
        }
        _write_summary(summary_path, summary)
        if enforce:
            print("[skill-eval] ANTHROPIC_API_KEY missing and enforcement is enabled", file=sys.stderr)
            return 2
        print("[skill-eval] advisory skip: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 0

    catalog_md = build_catalog_markdown(catalog)
    rows: List[Dict[str, Any]] = []
    for idx, case in enumerate(selected, start=1):
        routed = route_case(
            api_key=api_key,
            model=args.router_model,
            case=case,
            catalog_md=catalog_md,
            skill_names=skill_names,
        )
        judged = judge_case(
            api_key=api_key,
            model=args.judge_model,
            case=case,
            predicted_skill=routed["predicted_skill"],
            router_reason=routed["router_reason"],
        )
        row = {
            "schema": "aidd.skill_eval.result.v1",
            "id": case["id"],
            "kind": case["kind"],
            "prompt": case["prompt"],
            "expected_skills": case.get("expected_skills") or [],
            "predicted_skill": routed["predicted_skill"],
            "router_confidence": routed["router_confidence"],
            "router_reason": routed["router_reason"],
            "completion_proxy_pass": judged["completion_proxy_pass"],
            "judge_reason": judged["judge_reason"],
        }
        rows.append(row)
        if idx % 10 == 0:
            print(f"[skill-eval] processed {idx}/{len(selected)}")

    metrics = compute_metrics(rows, skills=sorted(skill_names))
    confusion = build_confusion_matrix(rows, sorted(skill_names))

    predictions_path = run_dir / "predictions.jsonl"
    write_jsonl(predictions_path, rows)
    write_confusion_csv(run_dir / "confusion_matrix.csv", confusion)

    summary = {
        "schema": SUMMARY_SCHEMA,
        "pack_version": "1",
        "run_id": run_id,
        "generated_at": utc_now(),
        "status": "completed",
        "source_path": args.cases.as_posix(),
        "router_model": args.router_model,
        "judge_model": args.judge_model,
        "seed": args.seed,
        "max_cases": args.max_cases,
        "metrics": {
            "macro_trigger_f1": metrics["macro_trigger_f1"],
            "exact_match_rate": metrics["exact_match_rate"],
            "completion_proxy_pass_rate": metrics["completion_proxy_pass_rate"],
        },
        "counts": {
            "total_cases": metrics["total_cases"],
            "kind_counts": metrics["kind_counts"],
        },
        "critical_skill_recall": metrics["critical_skill_recall"],
        "per_skill": metrics["per_skill"],
        "artifacts": {
            "predictions": predictions_path.as_posix(),
            "confusion_matrix": (run_dir / "confusion_matrix.csv").as_posix(),
        },
    }
    _write_summary(summary_path, summary)
    print(f"[skill-eval] completed -> {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
