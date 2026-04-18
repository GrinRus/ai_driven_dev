import os
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
import unittest

from .helpers import REPO_ROOT


EN_TEMPLATE_AGENT = dedent(
    """
    ---
    name: {name}
    description: en
    lang: en
    prompt_version: {version}
    source_version: {version}
    tools: Read
    model: inherit
    ---

    ## Context
    text

    ## Input Artifacts
    - item

    ## Automation
    text

    ## Steps
    1. step

    ## Fail-fast and Questions
    text

    ## Response Format
    text
    """
).strip() + "\n"


def write_prompt(root: Path, name: str, version: str = "1.0.0") -> None:
    prompt_dir = root / "agents"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_text = EN_TEMPLATE_AGENT.format(name=name, version=version)
    (prompt_dir / f"{name}.md").write_text(prompt_text, encoding="utf-8")


def write_stage_skill(root: Path, name: str, version: str = "1.0.0") -> None:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    text = dedent(
        f"""
        ---
        name: {name}
        description: "{name}"
        argument-hint: "<TICKET>"
        lang: en
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
                "en",
                "--part",
                part,
            ],
            text=True,
            capture_output=True,
            env=env,
            cwd=REPO_ROOT,
        )

    def test_bump_updates_en_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prompt(root, "analyst")
            result = self.run_prompt_version(root, "analyst", "agent", "minor")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            prompt_text = (root / "agents" / "analyst.md").read_text(encoding="utf-8")
            self.assertIn("prompt_version: 1.1.0", prompt_text)
            self.assertIn("source_version: 1.1.0", prompt_text)

    def test_bump_updates_en_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_stage_skill(root, "plan-new")
            result = self.run_prompt_version(root, "plan-new", "command", "patch")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            prompt_text = (root / "skills" / "plan-new" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("prompt_version: 1.0.1", prompt_text)
            self.assertIn("source_version: 1.0.1", prompt_text)

    def test_bump_updates_stage_skill_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_stage_skill(root, "review", version="1.0.44")
            result = self.run_prompt_version(root, "review", "command", "patch")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            prompt_text = (root / "skills" / "review" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("prompt_version: 1.0.45", prompt_text)
            self.assertIn("source_version: 1.0.45", prompt_text)

    def test_bump_fails_when_stage_skill_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_prompt_version(root, "qa", "command", "patch")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("skills/qa/SKILL.md", result.stderr)
            self.assertNotIn("fallback", result.stderr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
