#!/usr/bin/env python3
"""Generate or refresh skill eval dataset with Anthropic model."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

from skill_eval_common import CASE_SCHEMA, anthropic_messages_create, load_json, utc_now, write_jsonl

GEN_SYSTEM = """You generate one short user request for skill-routing evaluation.
Return only plain text (single line), no numbering, no markdown.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate skill eval cases using Anthropic API.")
    parser.add_argument(
        "--templates",
        type=Path,
        default=Path("tests/repo_tools/skill_eval/templates.v1.json"),
        help="Templates JSON describing skills and anti-triggers.",
    )
    parser.add_argument(
        "--out-cases",
        type=Path,
        default=Path("tests/repo_tools/skill_eval/cases.v1.jsonl"),
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("AIDD_SKILL_EVAL_GENERATOR_MODEL", "claude-3-5-haiku-latest"),
        help="Anthropic model used for generation.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic RNG seed.")
    parser.add_argument("--count", type=int, default=190, help="Total number of cases.")
    return parser.parse_args()


def _prompt_for_positive(skill: Dict[str, Any]) -> str:
    name = str(skill["name"])
    focus = str(skill.get("focus") or "")
    avoid = ", ".join(str(item) for item in (skill.get("avoid") or []))
    return (
        f"Write one realistic request that should trigger skill `{name}`. "
        f"Focus on: {focus}. "
        f"Avoid requests that belong to: {avoid}. "
        "The request must be specific and actionable for a coding assistant."
    )


def _prompt_for_near_miss(skill: Dict[str, Any]) -> str:
    name = str(skill["name"])
    focus = str(skill.get("focus") or "")
    avoid = ", ".join(str(item) for item in (skill.get("avoid") or []))
    return (
        "Write one realistic request that includes overlapping vocabulary but should NOT trigger any AIDD skill. "
        f"Reference terms near `{name}` ({focus}) only superficially. "
        f"Keep it outside AIDD workflow responsibilities and outside: {avoid}."
    )


def _prompt_for_no_skill() -> str:
    return (
        "Write one user request unrelated to software workflow orchestration, skill routing, coding tasks, "
        "or repository analysis. Keep it practical and short."
    )


def _generate_text(*, api_key: str, model: str, user_prompt: str) -> str:
    text = anthropic_messages_create(
        api_key=api_key,
        model=model,
        system_prompt=GEN_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.2,
        max_tokens=120,
    )
    first = text.strip().splitlines()[0].strip()
    return first.strip('"').strip("'").strip()


def main() -> int:
    args = parse_args()
    if args.count < 10:
        print("--count must be >= 10", file=sys.stderr)
        return 2

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("ANTHROPIC_API_KEY is required for skill_eval_generate.py", file=sys.stderr)
        return 2

    payload = load_json(args.templates)
    skills = payload.get("skills") or []
    if not isinstance(skills, list) or not skills:
        print(f"invalid templates file: {args.templates}", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    skills = list(skills)
    rng.shuffle(skills)

    positive_count = int(round(args.count * 0.6))
    near_miss_count = int(round(args.count * 0.3))
    no_skill_count = args.count - positive_count - near_miss_count

    rows: List[Dict[str, Any]] = []

    def skill_at(index: int) -> Dict[str, Any]:
        return skills[index % len(skills)]

    for idx in range(positive_count):
        skill = skill_at(idx)
        prompt = _generate_text(api_key=api_key, model=args.model, user_prompt=_prompt_for_positive(skill))
        rows.append(
            {
                "schema": CASE_SCHEMA,
                "id": f"gen-pos-{idx+1:03d}",
                "kind": "positive",
                "prompt": prompt,
                "expected_skills": [str(skill["name"])],
                "critical": str(skill.get("name")) in {"researcher", "review-spec", "implement", "review", "qa"},
                "tags": ["generated", "positive"],
            }
        )

    for idx in range(near_miss_count):
        skill = skill_at(idx + positive_count)
        prompt = _generate_text(api_key=api_key, model=args.model, user_prompt=_prompt_for_near_miss(skill))
        rows.append(
            {
                "schema": CASE_SCHEMA,
                "id": f"gen-near-{idx+1:03d}",
                "kind": "near_miss",
                "prompt": prompt,
                "expected_skills": [],
                "tags": ["generated", "near_miss", str(skill.get("name") or "")],
            }
        )

    for idx in range(no_skill_count):
        prompt = _generate_text(api_key=api_key, model=args.model, user_prompt=_prompt_for_no_skill())
        rows.append(
            {
                "schema": CASE_SCHEMA,
                "id": f"gen-none-{idx+1:03d}",
                "kind": "no_skill",
                "prompt": prompt,
                "expected_skills": [],
                "tags": ["generated", "no_skill"],
            }
        )

    rng.shuffle(rows)
    write_jsonl(args.out_cases, rows)
    print(
        json.dumps(
            {
                "status": "ok",
                "generated_at": utc_now(),
                "count": len(rows),
                "output": args.out_cases.as_posix(),
                "model": args.model,
                "seed": args.seed,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
