import os
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
import unittest
from typing import Dict, Optional

from .helpers import PAYLOAD_ROOT, REPO_ROOT


REQUIRED_AGENT_PAIRS = [
    ("analyst", "idea-new"),
    ("planner", "plan-new"),
    ("implementer", "implement"),
    ("reviewer", "review"),
    ("researcher", "researcher"),
    ("prd-reviewer", "review-prd"),
]


def build_agent(name: str) -> str:
    return dedent(
        f"""
        ---
        name: {name}
        description: test agent
        lang: ru
        prompt_version: 1.0.0
        source_version: 1.0.0
        tools: Read, Write
        model: inherit
        ---

        ## Контекст
        Text.

        ## Входные артефакты
        - item

        ## Автоматизация
        Text.

        ## Пошаговый план
        1. step

        ## Fail-fast и вопросы
        Text.

        ## Формат ответа
        Text.
        """
    ).strip() + "\n"


def build_command(description: str = "test command") -> str:
    return dedent(
        f"""
        ---
        description: "{description}"
        argument-hint: "<TICKET>"
        lang: ru
        prompt_version: 1.0.0
        source_version: 1.0.0
        allowed-tools: Read,Edit
        model: inherit
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


def build_agent_en(name: str) -> str:
    return dedent(
        f"""
        ---
        name: {name}
        description: test agent en
        lang: en
        prompt_version: 1.0.0
        source_version: 1.0.0
        tools: Read, Write
        model: inherit
        ---

        ## Context
        Text.

        ## Input Artifacts
        - item

        ## Automation
        Text.

        ## Step-by-step Plan
        1. step

        ## Fail-fast & Questions
        Text.

        ## Response Format
        Text.
        """
    ).strip() + "\n"


def build_command_en(description: str = "test command") -> str:
    return dedent(
        f"""
        ---
        description: "{description}"
        argument-hint: "<TICKET>"
        lang: en
        prompt_version: 1.0.0
        source_version: 1.0.0
        allowed-tools: Read,Edit
        model: inherit
        ---

        ## Context
        Text.

        ## Input Artifacts
        - item

        ## When to Run
        Text.

        ## Automation & Hooks
        Text.

        ## What is Edited
        Text.

        ## Step-by-step Plan
        1. step

        ## Fail-fast & Questions
        Text.

        ## Expected Output
        Text.

        ## CLI Examples
        - `/cmd ABC-123`
        """
    ).strip() + "\n"


class PromptLintTests(unittest.TestCase):
    def run_lint(self, root: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        pythonpath = os.pathsep.join(filter(None, [str(REPO_ROOT / "src"), env.get("PYTHONPATH")]))
        env["PYTHONPATH"] = pythonpath
        return subprocess.run(
            [sys.executable, str(PAYLOAD_ROOT / "scripts" / "lint-prompts.py"), "--root", str(root)],
            text=True,
            capture_output=True,
            env=env,
        )

    def write_prompts(
        self,
        root: Path,
        agent_override: Optional[Dict[str, str]] = None,
        en_override: Optional[Dict[str, str]] = None,
        command_override: Optional[Dict[str, str]] = None,
        en_command_override: Optional[Dict[str, str]] = None,
    ) -> None:
        agent_override = agent_override or {}
        en_override = en_override or {}
        command_override = command_override or {}
        en_command_override = en_command_override or {}
        for agent_name, command_name in REQUIRED_AGENT_PAIRS:
            agent_path = root / ".claude" / "agents" / f"{agent_name}.md"
            agent_path.parent.mkdir(parents=True, exist_ok=True)
            content = agent_override.get(agent_name, build_agent(agent_name))
            agent_path.write_text(content, encoding="utf-8")

            command_path = root / ".claude" / "commands" / f"{command_name}.md"
            command_path.parent.mkdir(parents=True, exist_ok=True)
            command_content = command_override.get(command_name, build_command(command_name))
            command_path.write_text(command_content, encoding="utf-8")

            en_agent_path = root / "prompts" / "en" / "agents" / f"{agent_name}.md"
            en_agent_path.parent.mkdir(parents=True, exist_ok=True)
            en_content = en_override.get(f"agent:{agent_name}", build_agent_en(agent_name))
            en_agent_path.write_text(en_content, encoding="utf-8")

            en_command_path = root / "prompts" / "en" / "commands" / f"{command_name}.md"
            en_command_path.parent.mkdir(parents=True, exist_ok=True)
            en_cmd = en_command_override.get(f"command:{command_name}", build_command_en(command_name))
            en_command_path.write_text(en_cmd, encoding="utf-8")

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

    def test_missing_en_locale_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root)
            # remove one EN prompt
            missing = root / "prompts" / "en" / "agents" / "analyst.md"
            missing.unlink()
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing EN agent", result.stderr)

    def test_lang_parity_skip_allows_missing_en(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skip_agent = build_agent("analyst").replace("model: inherit", "model: inherit\nLang-Parity: skip", 1)
            self.write_prompts(root, agent_override={"analyst": skip_agent})
            (root / "prompts" / "en" / "agents" / "analyst.md").unlink()
            result = self.run_lint(root)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_lang_parity_skip_required_when_missing_en(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root)
            (root / "prompts" / "en" / "commands" / "implement.md").unlink()
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing EN command", result.stderr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
