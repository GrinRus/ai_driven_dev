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

STAGE_SKILLS = [
    "aidd-init",
    "idea-new",
    "researcher",
    "plan-new",
    "review-spec",
    "spec-interview",
    "tasks-new",
    "implement",
    "review",
    "qa",
    "status",
]

FORK_STAGE_AGENT = {
    "idea-new": "analyst",
    "researcher": "researcher",
    "tasks-new": "tasklist-refiner",
    "implement": "implementer",
    "review": "reviewer",
    "qa": "qa",
}

AGENT_NAMES = [
    "analyst",
    "researcher",
    "planner",
    "validator",
    "plan-reviewer",
    "prd-reviewer",
    "spec-interview-writer",
    "tasklist-refiner",
    "implementer",
    "reviewer",
    "qa",
]

CRITICAL_TEMPLATE_FILES = [
    "AGENTS.md",
    "docs/prompting/conventions.md",
    "reports/context/template.context-pack.md",
    "docs/loops/template.loop-pack.md",
    "docs/prd/template.md",
    "docs/plan/template.md",
    "docs/research/template.md",
    "docs/tasklist/template.md",
]


def build_agent(name: str) -> str:
    loop_skill = "" if name not in {"implementer", "reviewer", "qa"} else "\n  - feature-dev-aidd:aidd-loop"
    tools = "Read, Edit, Write"
    return (
        dedent(
            f"""
            ---
            name: {name}
            description: test agent
            lang: ru
            prompt_version: 1.0.0
            source_version: 1.0.0
            tools: {tools}
            skills:
              - feature-dev-aidd:aidd-core{loop_skill}
            model: inherit
            permissionMode: inherit
            ---

            ## Контекст
            Output follows aidd-core skill.

            ## Входные артефакты
            - item

            ## Автоматизация
            Text.

            ## Пошаговый план
            1. step

            ## Fail-fast и вопросы
            Text.

            ## Формат ответа
            Output follows aidd-core skill.
            """
        ).strip()
        + "\n"
    )


def build_stage_skill(stage: str, *, lang: str = "ru") -> str:
    description = f"Test skill for {stage}."
    argument_hint = "<TICKET>"
    prompt_version = "1.0.0"
    source_version = "1.0.0"
    allowed_tools = ["Read"]
    disable_invocation = "false" if stage == "status" else "true"
    context = "fork" if stage in FORK_STAGE_AGENT else ""
    agent = FORK_STAGE_AGENT.get(stage, "")
    loop_ref = " and `feature-dev-aidd:aidd-loop`" if stage in {"implement", "review", "qa"} else ""

    lines = [
        "---",
        f"name: {stage}",
        f"description: {description}",
        f"argument-hint: {argument_hint}",
        f"lang: {lang}",
        f"prompt_version: {prompt_version}",
        f"source_version: {source_version}",
        "allowed-tools:",
        "  - Read",
        "model: inherit",
        f"disable-model-invocation: {disable_invocation}",
        "user-invocable: true",
    ]
    if context:
        lines.append(f"context: {context}")
    if agent:
        lines.append(f"agent: {agent}")
    lines.append("---")
    lines.append("")
    lines.append(f"Follow `feature-dev-aidd:aidd-core`{loop_ref}.")
    lines.append("")
    lines.append("## Steps")
    if stage in {"implement", "review", "qa"}:
        lines.append(f"1. Preflight reference: `skills/{stage}/scripts/preflight.sh`.")
        lines.append(
            f"2. Fill actions.json: create `aidd/reports/actions/<ticket>/<scope_key>/{stage}.actions.json`."
        )
        lines.append(f"3. Postflight reference: `skills/{stage}/scripts/postflight.sh`.")
    else:
        lines.append("1. Do the work.")
    lines.append("")
    return "\n".join(lines)


def build_core_skill() -> str:
    return (
        dedent(
            """
            ---
            name: aidd-core
            description: Core runtime policy for skills.
            lang: en
            model: inherit
            user-invocable: false
            ---

            ## Output contract
            - Status: ...
            - Work item key: ...
            - Artifacts updated: ...
            - Tests: ...
            - Blockers/Handoff: ...
            - Next actions: ...
            - AIDD:READ_LOG: ...
            - AIDD:ACTIONS_LOG: ...
            """
        ).strip()
        + "\n"
    )


def build_loop_skill() -> str:
    return (
        dedent(
            """
            ---
            name: aidd-loop
            description: Loop discipline for implement/review/qa.
            lang: en
            model: inherit
            user-invocable: false
            ---

            Follow `feature-dev-aidd:aidd-core`.
            """
        ).strip()
        + "\n"
    )


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
        skill_override: Optional[Dict[str, str]] = None,
    ) -> None:
        agent_override = agent_override or {}
        skill_override = skill_override or {}

        for agent_name in AGENT_NAMES:
            agent_path = root / "agents" / f"{agent_name}.md"
            agent_path.parent.mkdir(parents=True, exist_ok=True)
            content = agent_override.get(agent_name, build_agent(agent_name))
            agent_path.write_text(content, encoding="utf-8")

        skills_root = root / "skills"
        skills_root.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-core" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-loop" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-core" / "SKILL.md").write_text(build_core_skill(), encoding="utf-8")
        (skills_root / "aidd-loop" / "SKILL.md").write_text(build_loop_skill(), encoding="utf-8")

        for stage in STAGE_SKILLS:
            skill_path = skills_root / stage / "SKILL.md"
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            content = skill_override.get(stage, build_stage_skill(stage))
            skill_path.write_text(content, encoding="utf-8")

        self.write_baseline(root)
        self.write_policy(root)
        self.write_docs(root)
        self.write_plugin_manifest(root)

    def write_baseline(self, root: Path) -> None:
        rows = []
        for stage in STAGE_SKILLS:
            rows.append(
                {
                    "stage": stage,
                    "command_path": f"commands/{stage}.md",
                    "skill_path": f"skills/{stage}/SKILL.md",
                    "frontmatter": {
                        "allowed-tools": ["Read"],
                        "model": "inherit",
                        "prompt_version": "1.0.0",
                        "source_version": "1.0.0",
                        "lang": "ru",
                        "argument-hint": "<TICKET>",
                    },
                }
            )
        payload = {
            "schema": "aidd.commands_to_skills_frontmatter.v1",
            "rows": rows,
        }
        out_dir = root / "dev" / "reports" / "migrations"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "commands_to_skills_frontmatter.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    def write_policy(self, root: Path) -> None:
        policy_path = root / "docs" / "skill-language.md"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text("Skills are EN-only.\n", encoding="utf-8")

    def write_plugin_manifest(self, root: Path) -> None:
        skills = sorted(
            f"./skills/{path.parent.name}" for path in (root / "skills").glob("*/SKILL.md")
        )
        agents = sorted(f"./agents/{path.name}" for path in (root / "agents").glob("*.md"))
        manifest = {
            "name": "test-plugin",
            "skills": skills,
            "agents": agents,
        }
        plugin_manifest = root / ".claude-plugin" / "plugin.json"
        plugin_manifest.parent.mkdir(parents=True, exist_ok=True)
        plugin_manifest.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    def write_docs(self, root: Path) -> None:
        templates_root = root / "templates" / "aidd"
        for rel_path in CRITICAL_TEMPLATE_FILES:
            target = templates_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel_path.endswith("conventions.md"):
                content = "# Conventions\n\n## Evidence read policy (pack-first, rolling)\n"
            elif rel_path.endswith("template.context-pack.md"):
                content = "# Context Pack Template\n"
            elif rel_path.endswith("template.loop-pack.md"):
                content = "# Loop Pack Template\n"
            elif rel_path.endswith("AGENTS.md"):
                content = "# AGENTS\n"
            else:
                content = "# Template\n"
            target.write_text(content, encoding="utf-8")

        index_schema_path = templates_root / "docs" / "index" / "schema.json"
        index_schema_path.parent.mkdir(parents=True, exist_ok=True)
        index_schema_path.write_text(
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
            tools: Read, Edit, Write
            skills:
              - feature-dev-aidd:aidd-core
              - feature-dev-aidd:aidd-loop
            model: inherit
            permissionMode: inherit
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
            Output follows aidd-core skill.
            """
        ).strip() + "\n"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"implementer": broken_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing section", result.stderr)

    def test_missing_user_invocable_fails(self) -> None:
        bad_skill = build_stage_skill("idea-new").replace("user-invocable: true", "", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"idea-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("user-invocable", result.stderr)

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
        bad_skill = build_stage_skill("plan-new").replace(
            "## Steps\n1. Do the work.",
            "## Steps\nStatus: approved",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"plan-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown status", result.stderr)

    def test_html_ticket_escape_fails(self) -> None:
        bad_skill = build_stage_skill("plan-new").replace("Do the work", "Do &lt;ticket&gt; work", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"plan-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("replace HTML escape", result.stderr)

    def test_parity_fails(self) -> None:
        bad_skill = build_stage_skill("review").replace("- Read", "- Edit", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"review": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("allowed-tools does not match baseline", result.stderr)

    def test_skill_length_limit_fails(self) -> None:
        long_tail = "\n".join([f"Extra line {idx}" for idx in range(340)])
        long_skill = build_stage_skill("qa") + "\n" + long_tail + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"qa": long_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exceeds max skill length", result.stderr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
