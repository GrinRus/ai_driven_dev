import os
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
import unittest

from .helpers import PAYLOAD_ROOT, REPO_ROOT


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


EN_TEMPLATE_AGENT = dedent(
    """
    ---
    name: {name}
    description: en
    lang: en
    prompt_version: {version}
    source_version: {source}
    tools: Read
    model: inherit
    ---

    ## Context
    text

    ## Input Artifacts
    - item

    ## Automation
    text

    ## Step-by-step Plan
    1. step

    ## Fail-fast & Questions
    text

    ## Response Format
    text
    """
).strip() + "\n"


class PromptVersioningTests(unittest.TestCase):
    def write_pair(
        self,
        root: Path,
        name: str,
        version: str = "1.0.0",
        kind: str = "agent",
        lang_skip: bool = False,
    ) -> None:
        ru_dir = root / ".claude" / ("agents" if kind == "agent" else "commands")
        en_dir = root / "prompts" / "en" / ("agents" if kind == "agent" else "commands")
        ru_dir.mkdir(parents=True, exist_ok=True)
        en_dir.mkdir(parents=True, exist_ok=True)
        if kind == "agent":
            ru_text = RU_TEMPLATE_AGENT.format(name=name, version=version)
            en_text = EN_TEMPLATE_AGENT.format(name=name, version=version, source=version)
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
            en_text = dedent(
                f"""
                ---
                description: "{name}"
                argument-hint: "<TICKET>"
                lang: en
                prompt_version: {version}
                source_version: {version}
                allowed-tools: Read
                model: inherit
                ---

                ## Context
                text

                ## Input Artifacts
                - item

                ## When to Run
                text

                ## Automation & Hooks
                text

                ## What is Edited
                text

                ## Step-by-step Plan
                1. step

                ## Fail-fast & Questions
                text

                ## Expected Output
                text

                ## CLI Examples
                - `/cmd`
                """
            ).strip() + "\n"
        if lang_skip:
            ru_text = ru_text.replace("model: inherit", "model: inherit\nLang-Parity: skip", 1)
        (ru_dir / f"{name}.md").write_text(ru_text, encoding="utf-8")
        (en_dir / f"{name}.md").write_text(en_text, encoding="utf-8")

    def test_bump_updates_ru_and_en_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_pair(root, "analyst")
            env = os.environ.copy()
            pythonpath = os.pathsep.join(filter(None, [str(REPO_ROOT / "src"), env.get("PYTHONPATH")]))
            env["PYTHONPATH"] = pythonpath
            result = subprocess.run(
                [
                    sys.executable,
                    str(PAYLOAD_ROOT / "scripts" / "prompt-version"),
                    "bump",
                    "--root",
                    str(root),
                    "--prompts",
                    "analyst",
                    "--kind",
                    "agent",
                    "--lang",
                    "ru,en",
                    "--part",
                    "minor",
                ],
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            ru_text = (root / ".claude" / "agents" / "analyst.md").read_text(encoding="utf-8")
            en_text = (root / "prompts" / "en" / "agents" / "analyst.md").read_text(encoding="utf-8")
            self.assertIn("prompt_version: 1.1.0", ru_text)
            self.assertIn("source_version: 1.1.0", ru_text)
            self.assertIn("prompt_version: 1.1.0", en_text)
            self.assertIn("source_version: 1.1.0", en_text)

    def test_bump_updates_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_pair(root, "plan-new", kind="command")
            env = os.environ.copy()
            pythonpath = os.pathsep.join(filter(None, [str(REPO_ROOT / "src"), env.get("PYTHONPATH")]))
            env["PYTHONPATH"] = pythonpath
            result = subprocess.run(
                [
                    sys.executable,
                    str(PAYLOAD_ROOT / "scripts" / "prompt-version"),
                    "bump",
                    "--root",
                    str(root),
                    "--prompts",
                    "plan-new",
                    "--kind",
                    "command",
                    "--lang",
                    "ru,en",
                    "--part",
                    "patch",
                ],
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            ru_text = (root / ".claude" / "commands" / "plan-new.md").read_text(encoding="utf-8")
            en_text = (root / "prompts" / "en" / "commands" / "plan-new.md").read_text(encoding="utf-8")
            self.assertIn("prompt_version: 1.0.1", ru_text)
            self.assertIn("source_version: 1.0.1", en_text)

    def test_lang_specific_bump_updates_source_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_pair(root, "analyst")
            env = os.environ.copy()
            pythonpath = os.pathsep.join(filter(None, [str(REPO_ROOT / "src"), env.get("PYTHONPATH")]))
            env["PYTHONPATH"] = pythonpath
            result = subprocess.run(
                [
                    sys.executable,
                    str(PAYLOAD_ROOT / "scripts" / "prompt-version"),
                    "bump",
                    "--root",
                    str(root),
                    "--prompts",
                    "analyst",
                    "--kind",
                    "agent",
                    "--lang",
                    "ru",
                    "--part",
                    "patch",
                ],
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            en_text = (root / "prompts" / "en" / "agents" / "analyst.md").read_text(encoding="utf-8")
            self.assertIn("source_version: 1.0.1", en_text)
            self.assertIn("prompt_version: 1.0.0", en_text)

    def test_bump_respects_lang_parity_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_pair(root, "analyst", lang_skip=True)
            (root / "prompts" / "en" / "agents" / "analyst.md").unlink()
            env = os.environ.copy()
            pythonpath = os.pathsep.join(filter(None, [str(REPO_ROOT / "src"), env.get("PYTHONPATH")]))
            env["PYTHONPATH"] = pythonpath
            result = subprocess.run(
                [
                    sys.executable,
                    str(PAYLOAD_ROOT / "scripts" / "prompt-version"),
                    "bump",
                    "--root",
                    str(root),
                    "--prompts",
                    "analyst",
                    "--kind",
                    "agent",
                    "--lang",
                    "ru",
                    "--part",
                    "minor",
                ],
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            ru_text = (root / ".claude" / "agents" / "analyst.md").read_text(encoding="utf-8")
            self.assertIn("prompt_version: 1.1.0", ru_text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
