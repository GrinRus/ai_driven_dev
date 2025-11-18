import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
import unittest


class PromptDiffTests(unittest.TestCase):
    def write_prompt_pair(self, root: Path, kind: str, name: str, ru_text: str, en_text: str) -> None:
        ru_dir = root / ".claude" / ("agents" if kind == "agent" else "commands")
        en_dir = root / "prompts" / "en" / ("agents" if kind == "agent" else "commands")
        ru_dir.mkdir(parents=True, exist_ok=True)
        en_dir.mkdir(parents=True, exist_ok=True)
        (ru_dir / f"{name}.md").write_text(ru_text, encoding="utf-8")
        (en_dir / f"{name}.md").write_text(en_text, encoding="utf-8")

    def test_diff_outputs_changes(self) -> None:
        ru_prompt = dedent(
            """
            ---
            name: analyst
            description: ru
            lang: ru
            prompt_version: 1.0.0
            source_version: 1.0.0
            tools: Read
            model: inherit
            ---

            ## Контекст
            RU text

            ## Входные артефакты
            - item

            ## Автоматизация
            RU

            ## Пошаговый план
            1. step

            ## Fail-fast и вопросы
            RU

            ## Формат ответа
            RU
            """
        ).strip() + "\n"
        en_prompt = dedent(
            """
            ---
            name: analyst
            description: en
            lang: en
            prompt_version: 1.0.0
            source_version: 1.0.0
            tools: Read
            model: inherit
            ---

            ## Context
            EN text

            ## Input Artifacts
            - item

            ## Automation
            EN

            ## Step-by-step Plan
            1. step

            ## Fail-fast & Questions
            EN

            ## Response Format
            EN
            """
        ).strip() + "\n"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompt_pair(root, "agent", "analyst", ru_prompt, en_prompt)
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/prompt_diff.py",
                    "--name",
                    "analyst",
                    "--kind",
                    "agent",
                    "--root",
                    str(root),
                    "--context",
                    "1",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("RU text", result.stdout)
            self.assertIn("EN text", result.stdout)

    def test_command_diff_outputs_changes(self) -> None:
        ru_prompt = dedent(
            """
            ---
            description: "cmd"
            argument-hint: "<TICKET>"
            lang: ru
            prompt_version: 1.0.0
            source_version: 1.0.0
            allowed-tools: Read
            model: inherit
            ---

            ## Контекст
            RU CMD

            ## Входные артефакты
            - item

            ## Когда запускать
            RU

            ## Автоматические хуки и переменные
            RU

            ## Что редактируется
            RU

            ## Пошаговый план
            1. step

            ## Fail-fast и вопросы
            RU

            ## Ожидаемый вывод
            RU

            ## Примеры CLI
            - `/cmd`
            """
        ).strip() + "\n"
        en_prompt = dedent(
            """
            ---
            description: "cmd"
            argument-hint: "<TICKET>"
            lang: en
            prompt_version: 1.0.0
            source_version: 1.0.0
            allowed-tools: Read
            model: inherit
            ---

            ## Context
            EN CMD

            ## Input Artifacts
            - item

            ## When to Run
            EN

            ## Automation & Hooks
            EN

            ## What is Edited
            EN

            ## Step-by-step Plan
            1. step

            ## Fail-fast & Questions
            EN

            ## Expected Output
            EN

            ## CLI Examples
            - `/cmd`
            """
        ).strip() + "\n"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompt_pair(root, "command", "plan-new", ru_prompt, en_prompt)
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/prompt_diff.py",
                    "--name",
                    "plan-new",
                    "--kind",
                    "command",
                    "--root",
                    str(root),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("RU CMD", result.stdout)
            self.assertIn("EN CMD", result.stdout)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
