#!/usr/bin/env python3
"""Upgrade AIDD docs by inserting missing AIDD:* anchor sections."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


CORE_SECTIONS = [
    "AIDD:CONTEXT_PACK",
    "AIDD:NON_NEGOTIABLES",
    "AIDD:OPEN_QUESTIONS",
    "AIDD:RISKS",
    "AIDD:DECISIONS",
]

SECTION_TEMPLATES: Dict[str, List[str]] = {
    "AIDD:CONTEXT_PACK": ["- <краткий контекст>"],
    "AIDD:NON_NEGOTIABLES": ["- <что нельзя нарушать>"],
    "AIDD:OPEN_QUESTIONS": ["- <вопрос> → <кто отвечает> → <срок>"],
    "AIDD:RISKS": ["- <риск> → <митигация>"],
    "AIDD:DECISIONS": ["- <решение> → <почему>"],
    "AIDD:GOALS": ["- <goal 1>", "- <goal 2>"],
    "AIDD:NON_GOALS": ["- <non-goal>"],
    "AIDD:ACCEPTANCE": ["- <AC-1>", "- <AC-2>"],
    "AIDD:METRICS": ["- <metric> → <target>"],
    "AIDD:ROLL_OUT": ["- <этапы/флаги/откат>"],
    "AIDD:ARCHITECTURE": ["- <ключевые слои/границы>"],
    "AIDD:FILES_TOUCHED": ["- <путь/модуль> — <что меняем>"],
    "AIDD:ITERATIONS": ["- <итерация> → <цель> → <DoD>"],
    "AIDD:TEST_STRATEGY": ["- <что/где/как тестируем>"],
    "AIDD:INTEGRATION_POINTS": ["- <точка интеграции>"],
    "AIDD:REUSE_CANDIDATES": ["- <reuse-кандидат>"],
    "AIDD:COMMANDS_RUN": ["- <команда/лог>"],
    "AIDD:NEXT_3": ["- [ ] <первый приоритетный чекбокс>"],
    "AIDD:HANDOFF_INBOX": ["- [ ] <handoff со ссылкой на report>"],
    "AIDD:CHECKLIST": ["- <см. чеклисты ниже>"],
    "AIDD:PROGRESS_LOG": ["- <YYYY-MM-DD> — <что сделано> — <ссылка>"],
    "AIDD:QA_TRACEABILITY": ["- <AC-1> → <тест/лог/шаг>"],
    "AIDD:HOW_TO_UPDATE": ["- <правила обновления>"],
}

TYPE_SECTIONS: Dict[str, Sequence[str]] = {
    "prd": [
        *CORE_SECTIONS,
        "AIDD:GOALS",
        "AIDD:NON_GOALS",
        "AIDD:ACCEPTANCE",
        "AIDD:METRICS",
        "AIDD:ROLL_OUT",
    ],
    "plan": [
        *CORE_SECTIONS,
        "AIDD:ARCHITECTURE",
        "AIDD:FILES_TOUCHED",
        "AIDD:ITERATIONS",
        "AIDD:TEST_STRATEGY",
    ],
    "research": [
        *CORE_SECTIONS,
        "AIDD:INTEGRATION_POINTS",
        "AIDD:REUSE_CANDIDATES",
        "AIDD:COMMANDS_RUN",
    ],
    "tasklist": [
        "AIDD:CONTEXT_PACK",
        "AIDD:NEXT_3",
        "AIDD:HANDOFF_INBOX",
        "AIDD:CHECKLIST",
        "AIDD:PROGRESS_LOG",
        "AIDD:HOW_TO_UPDATE",
    ],
}


def find_insert_index(lines: List[str]) -> int:
    if lines and lines[0].strip() == "---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                return idx + 1
    for idx, line in enumerate(lines):
        if line.startswith("# "):
            return idx + 1
    return 0


def existing_sections(text: str) -> set[str]:
    return {
        line.strip()[3:].strip()
        for line in text.splitlines()
        if line.strip().startswith("## ")
    }


def render_section(name: str) -> List[str]:
    body = SECTION_TEMPLATES.get(name, ["- <todo>"])
    return [f"## {name}", *body, ""]


def upgrade_file(path: Path, doc_type: str) -> bool:
    content = path.read_text(encoding="utf-8")
    existing = existing_sections(content)
    required = TYPE_SECTIONS.get(doc_type, ())
    missing = [section for section in required if section not in existing]
    if not missing:
        return False

    lines = content.splitlines()
    insert_at = find_insert_index(lines)
    insert_block: List[str] = []
    if insert_at and insert_at < len(lines) and lines[insert_at].strip():
        insert_block.append("")
    for section in missing:
        insert_block.extend(render_section(section))
    if insert_block and insert_block[-1] == "":
        insert_block.pop()
    new_lines = lines[:insert_at] + insert_block + [""] + lines[insert_at:]
    new_text = "\n".join(new_lines).rstrip() + "\n"
    path.write_text(new_text, encoding="utf-8")
    return True


def iter_docs(root: Path) -> Iterable[Tuple[Path, str]]:
    for doc_type in ("prd", "plan", "research", "tasklist"):
        base = root / "aidd" / "docs" / doc_type
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.md")):
            if path.name == "template.md":
                continue
            yield path, doc_type


def main() -> int:
    parser = argparse.ArgumentParser(description="Insert missing AIDD:* sections into docs.")
    parser.add_argument("--root", default=".", help="Repo root containing aidd/docs.")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files.")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    changed: List[Path] = []
    for path, doc_type in iter_docs(repo_root):
        original = path.read_text(encoding="utf-8")
        if upgrade_file(path, doc_type):
            changed.append(path)
            if args.dry_run:
                path.write_text(original, encoding="utf-8")

    if args.dry_run:
        for item in changed:
            print(f"[dry-run] would update {item}")
    else:
        for item in changed:
            print(f"[updated] {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
