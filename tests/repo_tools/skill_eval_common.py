#!/usr/bin/env python3
"""Shared helpers for skill eval tooling."""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import random
import re
import statistics
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

CASE_SCHEMA = "aidd.skill_eval.case.v1"
SUMMARY_SCHEMA = "aidd.skill_eval.summary.v1"
DELTA_SCHEMA = "aidd.skill_eval.delta.v1"
NO_SKILL = "__no_skill__"
CRITICAL_SKILLS = ("researcher", "review-spec", "implement", "review", "qa")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_cases(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"cases file not found: {path}")
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_no}: {exc}") from exc
            validate_case(row, path=path, line_no=line_no)
            rows.append(row)
    if not rows:
        raise ValueError(f"no cases in {path}")
    return rows


def validate_case(row: Dict[str, Any], *, path: Path, line_no: int) -> None:
    if not isinstance(row, dict):
        raise ValueError(f"{path}:{line_no}: case must be an object")
    if str(row.get("schema") or "").strip() != CASE_SCHEMA:
        raise ValueError(f"{path}:{line_no}: unsupported schema (expected {CASE_SCHEMA})")
    case_id = str(row.get("id") or "").strip()
    if not case_id:
        raise ValueError(f"{path}:{line_no}: missing id")
    kind = str(row.get("kind") or "").strip()
    if kind not in {"positive", "near_miss", "no_skill"}:
        raise ValueError(f"{path}:{line_no}: invalid kind `{kind}`")
    prompt = str(row.get("prompt") or "").strip()
    if len(prompt) < 8:
        raise ValueError(f"{path}:{line_no}: prompt too short")
    expected = row.get("expected_skills") or []
    if not isinstance(expected, list):
        raise ValueError(f"{path}:{line_no}: expected_skills must be a list")
    normalized = [str(item).strip() for item in expected if str(item).strip()]
    if kind == "positive" and not normalized:
        raise ValueError(f"{path}:{line_no}: positive case must define expected_skills")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{path}:{line_no}: expected_skills contains duplicates")


def parse_front_matter(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for idx, raw in enumerate(lines[1:], start=1):
        if raw.strip() == "---":
            end = idx
            break
    if end is None:
        return {}

    front: Dict[str, Any] = {}
    active_list: str | None = None
    for raw in lines[1:end]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-") and active_list:
            item = stripped[1:].strip().strip('"').strip("'")
            front.setdefault(active_list, []).append(item)
            continue
        active_list = None
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value:
            front[key] = value
        else:
            front[key] = []
            active_list = key
    return front


def load_skill_catalog(skills_root: Path) -> List[Dict[str, Any]]:
    catalog: List[Dict[str, Any]] = []
    for skill_file in sorted(skills_root.glob("*/SKILL.md")):
        front = parse_front_matter(skill_file)
        name = str(front.get("name") or skill_file.parent.name).strip()
        description = str(front.get("description") or "").strip()
        if not name or not description:
            continue
        catalog.append(
            {
                "name": name,
                "description": description,
                "path": skill_file.as_posix(),
                "user_invocable": str(front.get("user-invocable") or "false").lower() == "true",
            }
        )
    if not catalog:
        raise ValueError(f"no skills discovered under {skills_root}")
    return catalog


def select_cases(cases: Sequence[Dict[str, Any]], *, max_cases: int | None, seed: int) -> List[Dict[str, Any]]:
    items = list(cases)
    rng = random.Random(seed)
    rng.shuffle(items)
    if max_cases and max_cases > 0:
        return items[:max_cases]
    return items


def expected_label(case: Dict[str, Any]) -> str:
    expected = [str(item).strip() for item in (case.get("expected_skills") or []) if str(item).strip()]
    if not expected:
        return NO_SKILL
    return sorted(expected)[0]


def build_confusion_matrix(rows: Sequence[Dict[str, Any]], skills: Sequence[str]) -> Dict[str, Dict[str, int]]:
    labels = [NO_SKILL, *sorted(skills)]
    matrix: Dict[str, Dict[str, int]] = {src: {dst: 0 for dst in labels} for src in labels}
    for row in rows:
        exp = expected_label(row)
        pred = str(row.get("predicted_skill") or NO_SKILL).strip() or NO_SKILL
        if pred not in matrix[NO_SKILL]:
            pred = NO_SKILL
        matrix.setdefault(exp, {dst: 0 for dst in labels})
        matrix[exp][pred] += 1
    return matrix


def write_confusion_csv(path: Path, matrix: Dict[str, Dict[str, int]]) -> None:
    labels = sorted(matrix.keys(), key=lambda item: (item != NO_SKILL, item))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["expected", *labels])
        for src in labels:
            row = [src]
            for dst in labels:
                row.append(int(matrix.get(src, {}).get(dst, 0)))
            writer.writerow(row)


def compute_metrics(rows: Sequence[Dict[str, Any]], *, skills: Sequence[str]) -> Dict[str, Any]:
    total = len(rows)
    if total <= 0:
        raise ValueError("no prediction rows")

    exact = 0
    completion_pass = 0
    kind_counts: Dict[str, int] = {}

    per_skill: Dict[str, Dict[str, float]] = {}
    sorted_skills = sorted(set(skills))
    for skill in sorted_skills:
        tp = fp = fn = support = 0
        for row in rows:
            exp = expected_label(row)
            pred = str(row.get("predicted_skill") or NO_SKILL).strip() or NO_SKILL
            if exp == skill:
                support += 1
                if pred == skill:
                    tp += 1
                else:
                    fn += 1
            elif pred == skill:
                fp += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_skill[skill] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "support": support,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        }

    for row in rows:
        exp = expected_label(row)
        pred = str(row.get("predicted_skill") or NO_SKILL).strip() or NO_SKILL
        if exp == pred:
            exact += 1
        if bool(row.get("completion_proxy_pass")):
            completion_pass += 1
        kind = str(row.get("kind") or "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1

    macro_f1 = statistics.mean((item["f1"] for item in per_skill.values())) if per_skill else 0.0
    critical_recalls: Dict[str, float] = {}
    for skill in CRITICAL_SKILLS:
        if skill in per_skill:
            critical_recalls[skill] = per_skill[skill]["recall"]

    return {
        "total_cases": total,
        "kind_counts": kind_counts,
        "exact_match_rate": round(exact / total, 6),
        "completion_proxy_pass_rate": round(completion_pass / total, 6),
        "macro_trigger_f1": round(macro_f1, 6),
        "per_skill": per_skill,
        "critical_skill_recall": critical_recalls,
    }


def anthropic_messages_create(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 600,
    timeout: int = 90,
) -> str:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    request = urllib.request.Request(
        url="https://api.anthropic.com/v1/messages",
        method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"anthropic HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"anthropic request failed: {exc}") from exc

    parsed = json.loads(raw)
    content = parsed.get("content") or []
    texts = [str(item.get("text") or "") for item in content if isinstance(item, dict)]
    return "\n".join(part for part in texts if part).strip()


def extract_first_json_object(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("model output does not contain JSON object")
    return json.loads(match.group(0))


def safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_catalog_markdown(catalog: Sequence[Dict[str, Any]]) -> str:
    lines = []
    for item in sorted(catalog, key=lambda row: str(row.get("name") or "")):
        name = str(item.get("name") or "").strip()
        desc = str(item.get("description") or "").strip()
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)


def check_expected_skills_exist(cases: Sequence[Dict[str, Any]], catalog_names: Iterable[str]) -> None:
    known = set(catalog_names)
    for case in cases:
        case_id = str(case.get("id") or "")
        for skill in case.get("expected_skills") or []:
            name = str(skill).strip()
            if name and name not in known:
                raise ValueError(f"case `{case_id}` references unknown skill `{name}`")


def bool_env(name: str, *, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}
