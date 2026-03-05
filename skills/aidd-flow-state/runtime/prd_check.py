#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import hashlib
import json
import sys
from pathlib import Path
from typing import List, Optional

import os


def _ensure_plugin_root_on_path() -> None:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if env_root:
        root = Path(env_root).resolve()
        if (root / "aidd_runtime").is_dir():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return

    probe = Path(__file__).resolve()
    for parent in (probe.parent, *probe.parents):
        if (parent / "aidd_runtime").is_dir():
            os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(parent))
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return


_ensure_plugin_root_on_path()

from aidd_runtime import cache_helpers
from aidd_runtime import runtime


STATUS_RE = re.compile(r"^\s*Status:\s*([A-Za-z]+)", re.MULTILINE)
CACHE_FILENAME = "prd-check.hash"
CACHE_VERSION = "2"
AIDD_OPEN_QUESTIONS_HEADING = "## AIDD:OPEN_QUESTIONS"
AIDD_ANSWERS_HEADING = "## AIDD:ANSWERS"
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
LEGACY_ANSWER_RE = re.compile(r"^\s*(?:[-*+]\s*)?(?:Ответ|Answer)\s+\d+\s*:", re.IGNORECASE | re.MULTILINE)
COMPACT_ANSWER_RE = re.compile(r'\bQ(\d+)\s*=\s*(?:"([^"\n]+)"|([^\s;,#`]+))')
OPEN_ITEM_PREFIX_RE = re.compile(r"^(?:[-*+]\s+|\d+\.\s+)")
CHECKBOX_PREFIX_RE = re.compile(r"^\[[ xX]\]\s*")
NONE_VALUES = {"none", "нет", "n/a", "na"}
INVALID_ANSWER_VALUES = {"tbd", "todo", "none", "нет", "n/a", "na", "empty", "unknown", "-", "?"}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PRD Status: READY.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--prd", help="Override PRD path.")
    return parser.parse_args(argv)


def _resolve_prd_path(project_root: Path, ticket: str, override: Optional[str]) -> Path:
    if override:
        return runtime.resolve_path_for_target(Path(override), project_root)
    return project_root / "docs" / "prd" / f"{ticket}.prd.md"


def _cache_path(root: Path) -> Path:
    return root / ".cache" / CACHE_FILENAME


def _hash_prd(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_cache(path: Path, *, ticket: str, hash_value: str) -> None:
    payload = {"ticket": ticket, "hash": hash_value, "cache_version": CACHE_VERSION}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return


def _extract_section(text: str, heading_prefix: str) -> str | None:
    lines = text.splitlines()
    start_idx: Optional[int] = None
    heading_lower = heading_prefix.strip().lower()
    for idx, raw in enumerate(lines):
        if raw.strip().lower().startswith(heading_lower):
            start_idx = idx + 1
            break
    if start_idx is None:
        return None
    end_idx = len(lines)
    for idx in range(start_idx, len(lines)):
        if idx != start_idx and MARKDOWN_HEADING_RE.match(lines[idx]):
            end_idx = idx
            break
    return "\n".join(lines[start_idx:end_idx]).strip()


def _has_open_items(section: str) -> bool:
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        normalized = OPEN_ITEM_PREFIX_RE.sub("", stripped)
        normalized = CHECKBOX_PREFIX_RE.sub("", normalized).strip()
        if normalized.startswith("`") and normalized.endswith("`") and len(normalized) > 1:
            normalized = normalized[1:-1].strip()
        if normalized.startswith("**") and normalized.endswith("**") and len(normalized) > 3:
            normalized = normalized[2:-2].strip()
        if normalized.lower() in NONE_VALUES:
            continue
        return True
    return False


def _collect_compact_answers(section: str) -> dict[int, str]:
    answers: dict[int, str] = {}
    for match in COMPACT_ANSWER_RE.finditer(section or ""):
        try:
            number = int(match.group(1))
        except ValueError:
            continue
        if number <= 0:
            continue
        value = str((match.group(2) if match.group(2) is not None else match.group(3)) or "").strip()
        if not value:
            continue
        answers[number] = value
    return answers


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    _, project_root = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(project_root, ticket=args.ticket, slug_hint=None)

    prd_path = _resolve_prd_path(project_root, ticket, args.prd)
    if not prd_path.exists():
        rel = runtime.rel_path(prd_path, project_root)
        raise SystemExit(f"BLOCK: PRD не найден: {rel}")

    text = prd_path.read_text(encoding="utf-8")
    current_hash = _hash_prd(text)
    cache_path = _cache_path(project_root)
    cache_payload = cache_helpers.load_json_cache(cache_path)
    if (
        cache_payload.get("ticket") == ticket
        and cache_payload.get("hash") == current_hash
        and cache_payload.get("cache_version") == CACHE_VERSION
    ):
        print("[prd-check] SKIP: cache hit (reason_code=cache_hit)", file=sys.stderr)
        return 0
    match = STATUS_RE.search(text)
    if not match:
        raise SystemExit("BLOCK: PRD не содержит строку `Status:` → установите Status: READY перед plan-new.")

    status = match.group(1).strip().upper()
    if status != "READY":
        raise SystemExit(
            f"BLOCK: PRD Status: {status} → установите Status: READY перед /feature-dev-aidd:plan-new {ticket}."
        )
    open_questions = _extract_section(text, AIDD_OPEN_QUESTIONS_HEADING)
    if open_questions and _has_open_items(open_questions):
        raise SystemExit(
            "BLOCK: PRD Status: READY, но AIDD:OPEN_QUESTIONS содержит незакрытые пункты. "
            "Закройте вопросы перед /feature-dev-aidd:plan-new."
        )
    answers_section = _extract_section(text, AIDD_ANSWERS_HEADING) or ""
    if LEGACY_ANSWER_RE.search(answers_section):
        raise SystemExit(
            "BLOCK: AIDD:ANSWERS использует неканоничный формат ответов; "
            "используйте `AIDD:ANSWERS Q1=A; Q2=\"короткий текст\"`."
        )
    answers_map = _collect_compact_answers(answers_section)
    if answers_section.strip() and not answers_map:
        raise SystemExit(
            "BLOCK: AIDD:ANSWERS должен быть в compact формате `Q<N>=<value>` (например, `Q1=A` или `Q1=\"короткий текст\"`)."
        )
    invalid_numbers = sorted(
        number for number, value in answers_map.items() if value.strip().lower() in INVALID_ANSWER_VALUES
    )
    if invalid_numbers:
        sample = ", ".join(f"Q{num}" for num in invalid_numbers[:3])
        if len(invalid_numbers) > 3:
            sample = f"{sample}, …"
        raise SystemExit(
            f"BLOCK: AIDD:ANSWERS содержит недопустимые значения для {sample} (TBD/TODO/empty)."
        )

    print(f"[aidd] PRD ready for `{ticket}` (status: READY).")
    _write_cache(cache_path, ticket=ticket, hash_value=current_hash)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
