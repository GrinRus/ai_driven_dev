import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
import unittest
from typing import Dict, Optional

from .helpers import REPO_ROOT


REQUIRED_AGENT_PAIRS = [
    ("analyst", "idea-new"),
    ("planner", "plan-new"),
    ("plan-reviewer", "review-spec"),
    ("spec-interview-writer", "spec-interview"),
    ("tasklist-refiner", "tasks-new"),
    ("implementer", "implement"),
    ("reviewer", "review"),
    ("researcher", "researcher"),
    ("prd-reviewer", "review-spec"),
]

REQUIRED_STAGE_ANCHORS = [
    "idea",
    "research",
    "plan",
    "review-plan",
    "review-prd",
    "spec-interview",
    "tasklist",
    "implement",
    "review",
    "qa",
]

TEMPLATE_ANCHORS = {
    "docs/prd/template.md": [
        "AIDD:CONTEXT_PACK",
        "AIDD:NON_NEGOTIABLES",
        "AIDD:OPEN_QUESTIONS",
        "AIDD:RISKS",
        "AIDD:DECISIONS",
        "AIDD:ANSWERS",
        "AIDD:GOALS",
        "AIDD:NON_GOALS",
        "AIDD:ACCEPTANCE",
        "AIDD:METRICS",
        "AIDD:ROLL_OUT",
    ],
    "docs/plan/template.md": [
        "AIDD:CONTEXT_PACK",
        "AIDD:NON_NEGOTIABLES",
        "AIDD:OPEN_QUESTIONS",
        "AIDD:RISKS",
        "AIDD:DECISIONS",
        "AIDD:ANSWERS",
        "AIDD:ARCHITECTURE",
        "AIDD:FILES_TOUCHED",
        "AIDD:ITERATIONS",
        "AIDD:TEST_STRATEGY",
    ],
    "docs/research/template.md": [
        "AIDD:CONTEXT_PACK",
        "AIDD:NON_NEGOTIABLES",
        "AIDD:OPEN_QUESTIONS",
        "AIDD:RISKS",
        "AIDD:DECISIONS",
        "AIDD:INTEGRATION_POINTS",
        "AIDD:REUSE_CANDIDATES",
        "AIDD:COMMANDS_RUN",
        "AIDD:TEST_HOOKS",
    ],
    "docs/tasklist/template.md": [
        "AIDD:CONTEXT_PACK",
        "AIDD:SPEC_PACK",
        "AIDD:TEST_STRATEGY",
        "AIDD:TEST_EXECUTION",
        "AIDD:ITERATIONS_FULL",
        "AIDD:NEXT_3",
        "AIDD:HANDOFF_INBOX",
        "AIDD:QA_TRACEABILITY",
        "AIDD:CHECKLIST",
        "AIDD:PROGRESS_LOG",
        "AIDD:HOW_TO_UPDATE",
    ],
}

def build_agent(name: str) -> str:
    question = ""
    if name in {"analyst", "validator"}:
        question = (
            "\n        Вопрос N (Blocker|Clarification): ...\n"
            "        Зачем: ...\n"
            "        Варианты: A) ... B) ...\n"
            "        Default: ...\n"
        )
    return (
        dedent(
            f"""
            ---
            name: {name}
            description: test agent
            lang: ru
            prompt_version: 1.0.0
            source_version: 1.0.0
            tools: Read, Edit, Write
            model: inherit
            permissionMode: inherit
            ---

            ## Контекст
            MUST READ FIRST: aidd/AGENTS.md, aidd/docs/sdlc-flow.md, aidd/docs/status-machine.md.
            Text.

            ## Входные артефакты
            - item

            ## Автоматизация
            Text.

            ## Пошаговый план
            1. step

            ## Fail-fast и вопросы
            Text.{question}

            ## Формат ответа
            Text.
            """
        ).strip()
        + "\n"
    )


def build_command(description: str = "test command") -> str:
    return dedent(
        f"""
        ---
        description: "{description}"
        argument-hint: "<TICKET>"
        lang: ru
        prompt_version: 1.0.0
        source_version: 1.0.0
        allowed-tools: Read,Edit,Write
        model: inherit
        disable-model-invocation: false
        ---

        ## Контекст
        Text.

        ## Входные артефакты
        - item

        ## Когда запускать
        Text.

        ## Автоматические хуки и переменные
        Text.

        ## Что редактируется
        Text.

        ## Пошаговый план
        1. step

        ## Fail-fast и вопросы
        Text.

        ## Ожидаемый вывод
        Text.

        ## Примеры CLI
        - `/cmd ABC-123`
        """
    ).strip() + "\n"


class PromptLintTests(unittest.TestCase):
    def run_lint(self, root: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "tests" / "repo_tools" / "lint-prompts.py"), "--root", str(root)],
            text=True,
            capture_output=True,
            env=env,
            cwd=REPO_ROOT,
        )

    def write_prompts(
        self,
        root: Path,
        agent_override: Optional[Dict[str, str]] = None,
        command_override: Optional[Dict[str, str]] = None,
    ) -> None:
        agent_override = agent_override or {}
        command_override = command_override or {}
        for agent_name, command_name in REQUIRED_AGENT_PAIRS:
            agent_path = root / "agents" / f"{agent_name}.md"
            agent_path.parent.mkdir(parents=True, exist_ok=True)
            content = agent_override.get(agent_name, build_agent(agent_name))
            agent_path.write_text(content, encoding="utf-8")

            command_path = root / "commands" / f"{command_name}.md"
            command_path.parent.mkdir(parents=True, exist_ok=True)
            command_content = command_override.get(command_name, build_command(command_name))
            command_path.write_text(command_content, encoding="utf-8")
        self.write_docs(root)

    def write_docs(self, root: Path) -> None:
        anchors_dir = root / "docs" / "anchors"
        anchors_dir.mkdir(parents=True, exist_ok=True)
        for stage in REQUIRED_STAGE_ANCHORS:
            (anchors_dir / f"{stage}.md").write_text(f"# Anchor: {stage}\n", encoding="utf-8")

        for rel_path, sections in TEMPLATE_ANCHORS.items():
            template_path = root / rel_path
            template_path.parent.mkdir(parents=True, exist_ok=True)
            lines = ["# Template"]
            for section in sections:
                lines.append(f"## {section}")
            template_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        index_schema = root / "docs" / "index" / "schema.json"
        index_schema.parent.mkdir(parents=True, exist_ok=True)
        index_schema.write_text(
            json.dumps(
                {
                    "schema": "aidd.ticket.v1",
                    "required": [
                        "schema",
                        "ticket",
                        "slug",
                        "stage",
                        "updated",
                        "summary",
                        "artifacts",
                        "reports",
                        "next3",
                        "open_questions",
                        "risks_top5",
                        "checks",
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_valid_prompts_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root)
            result = self.run_lint(root)
            self.assertEqual(
                result.returncode,
                0,
                msg=f"stdout: {result.stdout}\nstderr: {result.stderr}",
            )

    def test_missing_section_fails(self) -> None:
        broken_agent = dedent(
            """
            ---
            name: implementer
            description: bad agent
            lang: ru
            prompt_version: 1.0.0
            source_version: 1.0.0
            tools: Read
            model: inherit
            ---

            ## Контекст
            Text.

            ## Входные артефакты
            - item

            ## Пошаговый план
            1. step

            ## Fail-fast и вопросы
            Text.

            ## Формат ответа
            Text.
            """
        ).strip() + "\n"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"implementer": broken_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing section", result.stderr)

    def test_missing_command_section_fails(self) -> None:
        broken_command = dedent(
            """
            ---
            description: "broken"
            argument-hint: "<TICKET>"
            lang: ru
            prompt_version: 1.0.0
            source_version: 1.0.0
            allowed-tools: Read
            model: inherit
            ---

            ## Контекст
            Text.

            ## Входные артефакты
            - item

            ## Пошаговый план
            1. step

            ## Fail-fast и вопросы
            Text.
            """
        ).strip() + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, command_override={"implement": broken_command})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing section", result.stderr)

    def test_duplicate_front_matter_key_fails(self) -> None:
        duplicate_agent = build_agent("implementer").replace(
            "prompt_version: 1.0.0",
            "prompt_version: 1.0.0\nprompt_version: 1.0.1",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"implementer": duplicate_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate front matter key", result.stderr)

    def test_invalid_status_fails(self) -> None:
        bad_status = build_command().replace(
            "## Контекст\nText.",
            "## Контекст\nStatus: approved",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, command_override={"implement": bad_status})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown status", result.stderr)

    def test_invalid_status_ru_label_fails(self) -> None:
        bad_status = build_command().replace(
            "## Контекст\nText.",
            "## Контекст\nСтатус: approved",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, command_override={"implement": bad_status})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown status", result.stderr)

    def test_tool_parity_fails(self) -> None:
        command_no_write = build_command().replace("allowed-tools: Read,Edit,Write", "allowed-tools: Read", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, command_override={"implement": command_no_write})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("allowed-tools missing", result.stderr)

    def test_html_ticket_escape_fails(self) -> None:
        bad_command = build_command().replace("Text.", "Text &lt;ticket&gt;.", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, command_override={"implement": bad_command})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("replace HTML escape", result.stderr)

    def test_command_length_limit_fails(self) -> None:
        long_tail = "\n".join([f"Extra line {idx}" for idx in range(220)])
        long_command = build_command() + "\n" + long_tail + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, command_override={"implement": long_command})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exceeds max command length", result.stderr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
