from __future__ import annotations

import json
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

DEFAULT_TESTS_POLICY = {
    "implement": "none",
    "review": "targeted",
    "qa": "full",
}


def _resolve_gates_path(target: Path) -> Path:
    return target / "config" / "gates.json" if target.is_dir() else target


def load_gates_config(target: Path) -> dict:
    path = _resolve_gates_path(target)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"не удалось прочитать {path}: {exc}")


def load_gate_section(target: Path, section: str) -> dict:
    config = load_gates_config(target)
    raw = config.get(section)
    if isinstance(raw, bool):
        return {"enabled": raw}
    return raw if isinstance(raw, dict) else {}


def normalize_patterns(raw: Iterable[str] | None) -> list[str] | None:
    if not raw:
        return None
    patterns: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text:
            patterns.append(text)
    return patterns or None


def _normalize_tests_policy_value(value: object) -> str:
    if value is None:
        return ""
    raw = str(value).strip().lower()
    if raw in {"none", "no", "off", "disabled", "skip"}:
        return "none"
    if raw in {"targeted", "selective"}:
        return "targeted"
    if raw in {"full", "all"}:
        return "full"
    return ""


def resolve_stage_tests_policy(config: dict, stage: str) -> str:
    stage_value = str(stage or "").strip().lower()
    if stage_value not in DEFAULT_TESTS_POLICY:
        return ""
    raw_policy = config.get("tests_policy") or config.get("testsPolicy") if isinstance(config, dict) else None
    policy_value = ""
    if isinstance(raw_policy, dict):
        policy_value = _normalize_tests_policy_value(raw_policy.get(stage_value))
    elif raw_policy is not None:
        policy_value = _normalize_tests_policy_value(raw_policy)
    if policy_value:
        return policy_value
    return DEFAULT_TESTS_POLICY.get(stage_value, "")


def matches(patterns: Iterable[str] | None, value: str) -> bool:
    if not value:
        return False
    if isinstance(patterns, str):
        patterns = (patterns,)
    for pattern in patterns or ():
        if pattern and fnmatch(value, pattern):
            return True
    return False


def branch_enabled(branch: str | None, *, allow: Iterable[str] | None = None, skip: Iterable[str] | None = None) -> bool:
    if not branch:
        return True
    if skip and matches(skip, branch):
        return False
    if allow and not matches(allow, branch):
        return False
    return True
