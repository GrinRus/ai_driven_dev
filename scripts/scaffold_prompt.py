#!/usr/bin/env python3
"""Scaffold Claude Code prompt files from the shared templates.

Usage examples:

  python3 scripts/scaffold_prompt.py --type agent --target .claude/agents/new.md \
      --name new-agent --description "Новый агент" --tools "Read, Write"

  python3 scripts/scaffold_prompt.py --type command --target .claude/commands/new.md \
      --description "Команда" --argument-hint "<TICKET>" --allowed-tools "Read,Edit"

The script copies `templates/prompt-<type>.md`, replaces placeholders ({{NAME}},
{{DESCRIPTION}}, etc.) and writes the result to the requested path. Use `--force`
to overwrite existing files.
"""

from __future__ import annotations

import argparse
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = {
    "agent": REPO_ROOT / "templates" / "prompt-agent.md",
    "command": REPO_ROOT / "templates" / "prompt-command.md",
}


def replace_tokens(template: str, mapping: dict[str, str]) -> str:
    text = template
    for key, value in mapping.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def scaffold_prompt(args: argparse.Namespace) -> int:
    template_path = TEMPLATES[args.type]
    if not template_path.exists():
        raise SystemExit(f"Template not found: {template_path}")

    target = Path(args.target)
    if not target.is_absolute():
        target = REPO_ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and not args.force:
        print(f"[prompt] {target} already exists. Use --force to overwrite.")
        return 1

    template_text = template_path.read_text(encoding="utf-8")
    replacements = {
        "DESCRIPTION": args.description,
        "LANG": args.lang,
        "PROMPT_VERSION": args.prompt_version,
        "SOURCE_VERSION": args.source_version or args.prompt_version,
    }

    if args.type == "agent":
        replacements.update(
            {
                "NAME": args.name,
                "TOOLS": args.tools,
            }
        )
    else:
        replacements.update(
            {
                "ARGUMENT_HINT": args.argument_hint,
                "ALLOWED_TOOLS": args.allowed_tools,
            }
        )

    rendered = replace_tokens(template_text, replacements)
    target.write_text(rendered, encoding="utf-8")
    print(f"[prompt] Scaffolded {args.type} prompt at {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create Claude Code prompt files from templates/prompt-*.md.")
    parser.add_argument("--type", choices=("agent", "command"), required=True, help="Какой шаблон использовать.")
    parser.add_argument("--target", required=True, help="Файл, который следует создать (например, .claude/agents/foo.md).")
    parser.add_argument("--description", default="Краткое описание", help="Описание агента/команды в фронт-маттере.")
    parser.add_argument("--lang", default="ru", help="Локаль промпта (ru|en).")
    parser.add_argument("--prompt-version", default="0.1.0", help="Версия промпта (major.minor.patch).")
    parser.add_argument("--source-version", help="Версия исходника (для локализаций). По умолчанию = prompt_version.")
    parser.add_argument("--force", action="store_true", help="Перезаписать целевой файл, если он существует.")

    agent = parser.add_argument_group("Agent-specific options")
    agent.add_argument("--name", default="new-agent", help="Имя агента в поле name.")
    agent.add_argument("--tools", default="Read, Write", help="Список инструментов для поля tools (через запятую).")

    command = parser.add_argument_group("Command-specific options")
    command.add_argument("--argument-hint", default="<TICKET>", help="Значение argument-hint для команды.")
    command.add_argument("--allowed-tools", default="Read,Edit,Write,Grep,Glob", help="Список allowed-tools (через запятую).")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return scaffold_prompt(args)


if __name__ == "__main__":
    raise SystemExit(main())
