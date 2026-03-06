import os
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
import unittest

from .helpers import REPO_ROOT


RU_TEMPLATE_AGENT = dedent(
    """
    ---
    name: {name}
    description: ru
    lang: ru
    prompt_version: {version}
    source_version: {version}
    tools: Read
    model: inherit
    ---

    ## Контекст
    text

    ## Входные артефакты
    - item

    ## Автоматизация
    text

    ## Пошаговый план
    1. step

    ## Fail-fast и вопросы
    text

    ## Формат ответа
    text
    """
).strip() + "\n"


def write_prompt(root: Path, name: str, version: str = "1.0.0", kind: str = "agent") -> None:
    ru_dir = root / ("agents" if kind == "agent" else "commands")
    ru_dir.mkdir(parents=True, exist_ok=True)
    if kind == "agent":
        ru_text = RU_TEMPLATE_AGENT.format(name=name, version=version)
    else:
        ru_text = dedent(
            f"""
            ---
            description: "{name}"
            argument-hint: "<TICKET>"
            lang: ru
            prompt_version: {version}
            source_version: {version}
            allowed-tools: Read
            model: inherit
            ---

            ## Контекст
            text

            ## Входные артефакты
            - item

            ## Когда запускать
            text

            ## Автоматические хуки и переменные
            text

            ## Что редактируется
            text

            ## Пошаговый план
            1. step

            ## Fail-fast и вопросы
            text

            ## Ожидаемый вывод
            text

            ## Примеры CLI
            - `/cmd`
            """
        ).strip() + "\n"
    (ru_dir / f"{name}.md").write_text(ru_text, encoding="utf-8")


def write_stage_skill(root: Path, name: str, version: str = "1.0.0") -> None:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    text = dedent(
        f"""
        ---
        name: {name}
        description: "{name}"
        argument-hint: "<TICKET>"
        lang: ru
        prompt_version: {version}
        source_version: {version}
        allowed-tools: Read
        model: inherit
        disable-model-invocation: true
        user-invocable: true
        ---

        ## Steps
        1. do
        """
    ).strip() + "\n"
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")


class PromptVersioningTests(unittest.TestCase):
    def run_prompt_version(self, root: Path, name: str, kind: str, part: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        return subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "tests" / "repo_tools" / "prompt-version"),
                "bump",
                "--root",
                str(root),
                "--prompts",
                name,
                "--kind",
                kind,
                "--lang",
                "ru",
                "--part",
                part,
            ],
            text=True,
            capture_output=True,
            env=env,
            cwd=REPO_ROOT,
        )

    def test_bump_updates_ru_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prompt(root, "analyst")
            result = self.run_prompt_version(root, "analyst", "agent", "minor")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            ru_text = (root / "agents" / "analyst.md").read_text(encoding="utf-8")
            self.assertIn("prompt_version: 1.1.0", ru_text)
            self.assertIn("source_version: 1.1.0", ru_text)

    def test_bump_updates_ru_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prompt(root, "plan-new", kind="command")
            result = self.run_prompt_version(root, "plan-new", "command", "patch")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            ru_text = (root / "commands" / "plan-new.md").read_text(encoding="utf-8")
            self.assertIn("prompt_version: 1.0.1", ru_text)
            self.assertIn("source_version: 1.0.1", ru_text)

    def test_bump_updates_stage_skill_command_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_stage_skill(root, "review", version="1.0.44")
            result = self.run_prompt_version(root, "review", "command", "patch")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            ru_text = (root / "skills" / "review" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("prompt_version: 1.0.45", ru_text)
            self.assertIn("source_version: 1.0.45", ru_text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
