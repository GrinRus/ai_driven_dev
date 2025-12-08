#!/usr/bin/env python3
"""Validate Claude prompt files in RU/EN locales."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


PROMPT_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
VALID_LANGS = {"ru", "en"}

LANG_SECTION_TITLES = {
    "agent": {
        "ru": [
            "Контекст",
            "Входные артефакты",
            "Автоматизация",
            "Пошаговый план",
            "Fail-fast и вопросы",
            "Формат ответа",
        ],
        "en": [
            "Context",
            "Input Artifacts",
            "Automation",
            "Step-by-step Plan",
            "Fail-fast & Questions",
            "Response Format",
        ],
    },
    "command": {
        "ru": [
            "Контекст",
            "Входные артефакты",
            "Когда запускать",
            "Автоматические хуки и переменные",
            "Что редактируется",
            "Пошаговый план",
            "Fail-fast и вопросы",
            "Ожидаемый вывод",
            "Примеры CLI",
        ],
        "en": [
            "Context",
            "Input Artifacts",
            "When to Run",
            "Automation & Hooks",
            "What is Edited",
            "Step-by-step Plan",
            "Fail-fast & Questions",
            "Expected Output",
            "CLI Examples",
        ],
    },
}

LANG_PATHS: Dict[str, Dict[str, List[Path]]] = {
    "ru": {
        "agent": [Path("agents"), Path(".claude/agents"), Path(".claude-plugin/agents")],
        "command": [Path("commands"), Path(".claude/commands"), Path(".claude-plugin/commands")],
    },
    "en": {
        "agent": [Path("prompts/en/agents")],
        "command": [Path("prompts/en/commands")],
    },
}


PAIRINGS: List[Tuple[str, str]] = [
    ("analyst", "idea-new"),
    ("planner", "plan-new"),
    ("implementer", "implement"),
    ("reviewer", "review"),
    ("researcher", "researcher"),
    ("prd-reviewer", "review-prd"),
]


@dataclass
class PromptFile:
    path: Path
    kind: str  # "agent" or "command"
    lang: str
    front_matter: Dict[str, str]
    sections: List[str]

    @property
    def stem(self) -> str:  # pragma: no cover - trivial
        return self.path.stem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Claude prompt files")
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root containing .claude/",
    )
    return parser.parse_args()


def read_prompt(path: Path, kind: str, expected_lang: str) -> Tuple[PromptFile | None, List[str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: List[str] = []
    if not lines or lines[0].strip() != "---":
        errors.append(f"{path}: missing YAML front matter (start with ---)")
        return None, errors

    try:
        closing = lines.index("---", 1)
    except ValueError:
        errors.append(f"{path}: missing closing --- for front matter")
        return None, errors

    front_lines = lines[1:closing]
    front: Dict[str, str] = {}
    for idx, raw in enumerate(front_lines, start=2):
        line = raw.strip()
        if not line or line.startswith("-"):
            continue
        if ":" not in line:
            errors.append(f"{path}:{idx}: invalid front matter line (expected key: value)")
            continue
        key, value = line.split(":", 1)
        clean_value = value.strip().strip('"').strip("'")
        front[key.strip()] = clean_value

    body = lines[closing + 1 :]
    sections: List[str] = []
    for raw in body:
        striped = raw.strip()
        if striped.startswith("## "):
            sections.append(striped[3:].strip())

    lang = front.get("lang", "").strip()
    if lang and lang not in VALID_LANGS:
        errors.append(f"{path}: unsupported lang `{lang}` (expected ru/en)")
    if expected_lang and lang and lang != expected_lang:
        errors.append(
            f"{path}: lang `{lang}` does not match expected `{expected_lang}` based on directory"
        )

    return PromptFile(path=path, kind=kind, lang=lang or expected_lang, front_matter=front, sections=sections), errors


def ensure_keys(info: PromptFile, keys: Iterable[str]) -> List[str]:
    errors = []
    front = info.front_matter
    for key in keys:
        if key not in front:
            errors.append(f"{info.path}: missing `{key}` in front matter")
    return errors


def ensure_sections(info: PromptFile, required: List[str]) -> List[str]:
    errors = []
    sections = info.sections
    current_index = -1
    for section in required:
        try:
            idx = sections.index(section)
        except ValueError:
            errors.append(f"{info.path}: missing section `## {section}`")
            continue
        if idx <= current_index:
            errors.append(
                f"{info.path}: section `## {section}` out of order (expected after previous sections)"
            )
        current_index = idx
    return errors


def validate_prompt(info: PromptFile) -> List[str]:
    errors: List[str] = []
    front = info.front_matter
    if info.kind == "agent":
        errors.extend(
            ensure_keys(
                info,
                [
                    "name",
                    "description",
                    "lang",
                    "prompt_version",
                    "source_version",
                    "tools",
                    "permissionMode",
                ],
            )
        )
    else:
        errors.extend(
            ensure_keys(
                info,
                [
                    "description",
                    "argument-hint",
                    "lang",
                    "prompt_version",
                    "source_version",
                    "allowed-tools",
                    "disable-model-invocation",
                ],
            )
        )

    lang = front.get("lang") or info.lang
    sections_required = LANG_SECTION_TITLES.get(info.kind, {}).get(lang or "ru")
    if sections_required:
        errors.extend(ensure_sections(info, sections_required))
    if lang and lang not in VALID_LANGS:
        errors.append(f"{info.path}: unsupported lang `{lang}` (expected ru/en)")

    version = front.get("prompt_version")
    if version and not PROMPT_VERSION_RE.match(version):
        errors.append(f"{info.path}: prompt_version `{version}` must match X.Y.Z")

    source_version = front.get("source_version")
    if source_version and not PROMPT_VERSION_RE.match(source_version):
        errors.append(f"{info.path}: source_version `{source_version}` must match X.Y.Z")

    return errors


def lint_prompts(root: Path) -> Tuple[List[str], Dict[str, Dict[str, Dict[str, PromptFile]]]]:
    errors: List[str] = []
    files: Dict[str, Dict[str, Dict[str, PromptFile]]] = {
        lang: {"agent": {}, "command": {}} for lang in LANG_PATHS
    }
    for lang, kinds in LANG_PATHS.items():
        for kind, directories in kinds.items():
            for rel_dir in directories:
                directory = root / rel_dir
                if not directory.exists():
                    continue
                for path in sorted(directory.glob("*.md")):
                    info, load_errors = read_prompt(path, kind, lang)
                    if load_errors:
                        errors.extend(load_errors)
                        continue
                    if info is None:
                        continue
                    files.setdefault(lang, {}).setdefault(kind, {})[info.stem] = info
                    errors.extend(validate_prompt(info))
    errors.extend(validate_pairings(files))
    errors.extend(validate_locale_pairs(files))
    return errors, files


def validate_pairings(files: Dict[str, Dict[str, Dict[str, PromptFile]]]) -> List[str]:
    errors: List[str] = []
    for lang, kinds in files.items():
        agents = kinds.get("agent", {})
        commands = kinds.get("command", {})
        other_lang = "en" if lang == "ru" else "ru"
        other_agents = files.get(other_lang, {}).get("agent", {})
        other_commands = files.get(other_lang, {}).get("command", {})
        for agent_name, command_name in PAIRINGS:
            agent = agents.get(agent_name)
            command = commands.get(command_name)
            agent_prefix = "prompts/en/agents" if lang == "en" else ".claude/agents"
            command_prefix = "prompts/en/commands" if lang == "en" else ".claude/commands"
            parity_skip = parity_skipped(
                agent,
                command,
                other_agents.get(agent_name),
                other_commands.get(command_name),
            )
            if agent is None:
                if not parity_skip:
                    errors.append(f"{agent_prefix}/{agent_name}.md: missing agent for `{command_name}`")
            if command is None:
                if not parity_skip:
                    errors.append(f"{command_prefix}/{command_name}.md: missing command for `{agent_name}`")
            if agent and command:
                if agent.front_matter.get("prompt_version") != command.front_matter.get("prompt_version"):
                    errors.append(
                        f"Pair {agent_name}/{command_name} ({lang}): prompt_version mismatch `{agent.front_matter.get('prompt_version')}` vs `{command.front_matter.get('prompt_version')}`"
                    )
    return errors


def parity_skipped(*prompts: PromptFile | None) -> bool:
    for prompt in prompts:
        if not prompt:
            continue
        value = prompt.front_matter.get("Lang-Parity") or ""
        if value.strip().lower() == "skip":
            return True
    return False


def validate_locale_pairs(files: Dict[str, Dict[str, Dict[str, PromptFile]]]) -> List[str]:
    errors: List[str] = []
    ru_prompts = files.get("ru", {})
    en_prompts = files.get("en", {})
    for kind in ("agent", "command"):
        ru_items = ru_prompts.get(kind, {})
        en_items = en_prompts.get(kind, {})
        all_names = set(ru_items) | set(en_items)
        for name in sorted(all_names):
            ru_prompt = ru_items.get(name)
            en_prompt = en_items.get(name)
            if parity_skipped(ru_prompt, en_prompt):
                continue
            if ru_prompt is None:
                ru_path = f".claude/{'agents' if kind == 'agent' else 'commands'}/{name}.md"
                errors.append(f"Missing RU {kind} for `{name}` → add {ru_path} or mark Lang-Parity: skip")
                continue
            if en_prompt is None:
                errors.append(
                    f"Missing EN {kind} for `{name}` → add prompts/en/{kind}s/{name}.md or mark Lang-Parity: skip"
                )
                continue
            ru_version = ru_prompt.front_matter.get("prompt_version")
            en_version = en_prompt.front_matter.get("prompt_version")
            if ru_version != en_version:
                errors.append(
                    f"Prompt `{name}` ({kind}) has mismatched prompt_version: ru={ru_version}, en={en_version}"
                )
            ru_source = ru_prompt.front_matter.get("source_version")
            en_source = en_prompt.front_matter.get("source_version")
            if ru_source != ru_version:
                errors.append(
                    f"RU prompt `{name}` should set source_version equal to prompt_version ({ru_version})"
                )
            if en_source != ru_version:
                errors.append(
                    f"EN prompt `{name}` must set source_version to RU prompt_version ({ru_version})"
                )
    return errors


def main() -> int:
    args = parse_args()
    root = args.root
    if not root.exists():
        print(f"[prompt-lint] root {root} does not exist", file=sys.stderr)
        return 1
    errors, _ = lint_prompts(root)
    if errors:
        for msg in errors:
            print(f"[prompt-lint] {msg}", file=sys.stderr)
        return 1
    print("[prompt-lint] all prompts passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
