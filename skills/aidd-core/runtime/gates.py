from __future__ import annotations

import json
import shlex
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

DEFAULT_TESTS_POLICY = {
    "implement": "none",
    "review": "targeted",
    "qa": "full",
}

TEST_EXECUTION_PROFILES = ("fast", "targeted", "full", "none")
TEST_EXECUTION_WHEN = ("on_stop", "checkpoint", "manual")


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


def _ensure_list(value: object) -> list[object]:
    if isinstance(value, list):
        return list(value)
    if value is None:
        return []
    return [value]


def _normalize_str_list(value: object) -> list[str]:
    out: list[str] = []
    for item in _ensure_list(value):
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _normalize_profiles(value: object) -> list[str]:
    raw = _normalize_str_list(value)
    profiles = [item.lower() for item in raw]
    if not profiles:
        return ["fast", "targeted", "full"]
    normalized: list[str] = []
    for profile in profiles:
        if profile in TEST_EXECUTION_PROFILES and profile not in normalized:
            normalized.append(profile)
    return normalized


def _parse_command_tokens(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    try:
        return [token for token in shlex.split(text) if token]
    except ValueError:
        return []


def _normalize_command_entry(entry: object, index: int) -> tuple[dict | None, str]:
    default_id = f"cmd_{index}"
    if isinstance(entry, str) or isinstance(entry, list):
        tokens = _parse_command_tokens(entry)
        if not tokens:
            return None, f"commands[{index}] invalid command"
        return {
            "id": default_id,
            "command": tokens,
            "cwd": ".",
            "profiles": ["fast", "targeted", "full"],
            "filters": [],
        }, ""
    if not isinstance(entry, dict):
        return None, f"commands[{index}] must be object|string|list"

    tokens = _parse_command_tokens(entry.get("command"))
    if not tokens:
        return None, f"commands[{index}].command invalid"

    entry_id = str(entry.get("id") or default_id).strip() or default_id
    cwd = str(entry.get("cwd") or ".").strip() or "."
    profiles = _normalize_profiles(entry.get("profiles"))
    if not profiles:
        return None, f"commands[{index}].profiles invalid"
    filters = _normalize_str_list(entry.get("filters"))
    return {
        "id": entry_id,
        "command": tokens,
        "cwd": cwd,
        "profiles": profiles,
        "filters": filters,
    }, ""


def load_qa_tests_contract(config: dict | None) -> tuple[dict, list[str]]:
    cfg = config if isinstance(config, dict) else {}
    qa_cfg = cfg.get("qa")
    if isinstance(qa_cfg, bool):
        qa_cfg = {"enabled": qa_cfg}
    if not isinstance(qa_cfg, dict):
        qa_cfg = {}
    tests_cfg = qa_cfg.get("tests")
    if not isinstance(tests_cfg, dict):
        tests_cfg = {}

    commands_raw = tests_cfg.get("commands")
    profile_raw = tests_cfg.get("profile_default")
    if profile_raw in {None, ""}:
        # Backward-compat: legacy qa.tests.commands without profile_default implies targeted execution.
        has_commands = bool(_ensure_list(commands_raw))
        profile_default = "targeted" if has_commands else "none"
    else:
        profile_default = str(profile_raw).strip().lower() or "none"
    when_default = str(tests_cfg.get("when_default") or "manual").strip().lower() or "manual"
    reason_default = str(tests_cfg.get("reason_default") or "project contract").strip() or "project contract"
    filters_default = _normalize_str_list(tests_cfg.get("filters_default"))
    contract_version_raw = tests_cfg.get("contract_version", 1)

    errors: list[str] = []
    if profile_default not in TEST_EXECUTION_PROFILES:
        errors.append("profile_default invalid")
    if when_default not in TEST_EXECUTION_WHEN:
        errors.append("when_default invalid")
    try:
        contract_version = int(contract_version_raw)
    except (TypeError, ValueError):
        contract_version = 1
        errors.append("contract_version invalid")

    commands: list[dict] = []
    for index, item in enumerate(_ensure_list(commands_raw), start=1):
        normalized, error = _normalize_command_entry(item, index)
        if normalized is None:
            errors.append(error)
            continue
        commands.append(normalized)

    if profile_default != "none" and not commands:
        errors.append("project_contract_missing")

    contract = {
        "contract_version": contract_version,
        "profile_default": profile_default if profile_default in TEST_EXECUTION_PROFILES else "none",
        "filters_default": filters_default,
        "when_default": when_default if when_default in TEST_EXECUTION_WHEN else "manual",
        "reason_default": reason_default,
        "commands": commands,
    }
    return contract, errors


def load_qa_tests_contract_for_target(target: Path) -> tuple[dict, list[str]]:
    config = load_gates_config(target)
    return load_qa_tests_contract(config)


def select_commands_for_profile(contract: dict, profile: str) -> list[dict]:
    selected: list[dict] = []
    profile_value = str(profile or "").strip().lower()
    for entry in contract.get("commands") or []:
        if not isinstance(entry, dict):
            continue
        profiles = [str(item).strip().lower() for item in (entry.get("profiles") or [])]
        if profile_value and profiles and profile_value not in profiles:
            continue
        selected.append(entry)
    return selected
