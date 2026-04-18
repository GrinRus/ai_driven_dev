from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.repo_tools.prompt_contract_support import assert_prompt_contract, load_prompt_contracts, read_text


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PROMPT_FULL = "aidd_test_flow_prompt_ralph_script_full.txt"
AUDIT_PROMPT_SMOKE = "aidd_test_flow_prompt_ralph_script.txt"
PROMPT_BUILDER = REPO_ROOT / "tests" / "repo_tools" / "build_e2e_prompts.py"
PROMPT_FRAGMENTS_DIR = REPO_ROOT / "tests" / "repo_tools" / "e2e_prompt"
PROMPT_SPECS = PROMPT_FRAGMENTS_DIR / "prompt_specs.json"
RESEARCHER_AGENT = REPO_ROOT / "agents" / "researcher.md"
RESEARCHER_SKILL = REPO_ROOT / "skills" / "researcher" / "SKILL.md"
SMOKE_WORKFLOW = REPO_ROOT / "tests" / "repo_tools" / "smoke-workflow.sh"

LOOP_STAGE_SKILLS = [
    REPO_ROOT / "skills" / "implement" / "SKILL.md",
    REPO_ROOT / "skills" / "review" / "SKILL.md",
    REPO_ROOT / "skills" / "qa" / "SKILL.md",
]

STAGE_SKILLS_FOR_ALIAS_GUARD = [
    REPO_ROOT / "skills" / "review-spec" / "SKILL.md",
    REPO_ROOT / "skills" / "tasks-new" / "SKILL.md",
    REPO_ROOT / "skills" / "qa" / "SKILL.md",
]

LEGACY_STAGE_ALIASES = [
    "/feature-dev-aidd:planner",
    "/feature-dev-aidd:tasklist-refiner",
    "/feature-dev-aidd:implementer",
    "/feature-dev-aidd:reviewer",
]

FORBIDDEN_DIRECT_MANUAL_RECOVERY_PATTERNS = [
    r"`python3\s+\$\{claude_plugin_root\}/skills/aidd-loop/runtime/preflight_prepare\.py`",
    r"(?:cat|tee|echo).{0,120}stage\.[a-z0-9_.-]*result\.json",
]
FORBIDDEN_LOOP_ALLOWED_TOOL_SURFACES = [
    "skills/aidd-loop/runtime/preflight_prepare.py",
    "skills/aidd-flow-state/runtime/stage_result.py",
]


def _front_matter(path: Path) -> str:
    text = read_text(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:idx])
    return ""


def _body(path: Path) -> str:
    text = read_text(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[idx + 1 :])
    return text


class E2EPromptContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contracts = load_prompt_contracts()
        cls._prompt_dir_ctx = tempfile.TemporaryDirectory()
        cls.prompt_dir = Path(cls._prompt_dir_ctx.name)
        result = subprocess.run(
            [sys.executable, str(PROMPT_BUILDER), "--output-dir", str(cls.prompt_dir)],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                "prompt builder failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._prompt_dir_ctx.cleanup()

    def test_prompt_builder_and_fragments_exist(self) -> None:
        self.assertTrue(PROMPT_BUILDER.exists(), msg=f"missing prompt builder: {PROMPT_BUILDER}")
        self.assertTrue(PROMPT_SPECS.exists(), msg=f"missing prompt specs: {PROMPT_SPECS}")
        self.assertTrue((PROMPT_FRAGMENTS_DIR / "prompt_contracts.json").exists())
        for rel in ("base_contract.md", "profile_full.md", "profile_smoke.md", "must_read_manifest.md"):
            path = PROMPT_FRAGMENTS_DIR / rel
            self.assertTrue(path.exists(), msg=f"missing prompt fragment: {path}")

    def test_prompt_builder_outputs_are_up_to_date(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PROMPT_BUILDER), "--check"],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"builder check failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_flow_prompt_contracts_are_data_driven(self) -> None:
        flow = self.contracts["flow"]
        texts = {
            "FULL": read_text(self.prompt_dir / AUDIT_PROMPT_FULL),
            "SMOKE": read_text(self.prompt_dir / AUDIT_PROMPT_SMOKE),
        }
        for profile, text in texts.items():
            assert_prompt_contract(self, text=text, contract=flow["ALL"], label=f"TST-001 {profile}")
            assert_prompt_contract(self, text=text, contract=flow[profile], label=f"TST-001 {profile}")

    def test_review_surfaces_enforce_canonical_plan_path_without_alias(self) -> None:
        review_skill = read_text(REPO_ROOT / "skills" / "review-spec" / "SKILL.md")
        plan_reviewer = read_text(REPO_ROOT / "agents" / "plan-reviewer.md")
        for text, label in (
            (review_skill, "skills/review-spec/SKILL.md"),
            (plan_reviewer, "agents/plan-reviewer.md"),
        ):
            self.assertIn("aidd/docs/plan/<ticket>.md", text, msg=f"{label}: missing canonical plan path")
            if ".plan.md" in text:
                self.assertRegex(
                    text,
                    r"forbidden|запрещ",
                    msg=f"{label}: alias .plan.md may only appear as a forbidden path",
                )

    def test_smoke_script_blocks_legacy_shadow_artifacts_in_workspace_root(self) -> None:
        text = read_text(SMOKE_WORKFLOW)
        self.assertIn("for shadow in docs reports config .cache; do", text)
        self.assertIn("non-canonical root artifact created at workspace root", text)

    def test_full_prompt_loop_step_command_uses_supported_flags_only(self) -> None:
        text = read_text(self.prompt_dir / AUDIT_PROMPT_FULL)
        match = re.search(r"python3 \$PLUGIN_DIR/skills/aidd-loop/runtime/loop_step\.py[^\n`]*", text)
        self.assertIsNotNone(match, msg="missing loop_step.py command in full prompt step 7")
        command = str(match.group(0))
        self.assertNotIn("--max-iterations", command)
        self.assertNotIn("--blocked-policy", command)
        self.assertNotIn("--recoverable-block-retries", command)

    def test_researcher_contract_prefers_reviewed_and_plan_new(self) -> None:
        agent_text = read_text(RESEARCHER_AGENT)
        skill_text = read_text(RESEARCHER_SKILL)
        self.assertIn("Status: reviewed|pending|warn", agent_text)
        self.assertIn("/feature-dev-aidd:plan-new <ticket>", agent_text)
        self.assertIn("/feature-dev-aidd:plan-new <ticket>", skill_text)
        self.assertNotIn("/feature-dev-aidd:planner", agent_text)
        self.assertNotIn("/feature-dev-aidd:planner", skill_text)

    def test_loop_stage_skills_enforce_stage_chain_only_policy(self) -> None:
        for skill_path in LOOP_STAGE_SKILLS:
            text = read_text(skill_path)
            lower = text.lower()
            body_lower = _body(skill_path).lower()
            frontmatter_lower = _front_matter(skill_path).lower()
            stage = skill_path.parent.name
            self.assertIn("internal preflight", lower)
            self.assertRegex(lower, r"stage\." + re.escape(stage) + r"\.result\.json")
            self.assertIn("stage-chain", lower)
            self.assertIn("actions_apply.py", lower)
            self.assertIn(
                "python3 ${claude_plugin_root}/skills/aidd-flow-state/runtime/stage_result.py",
                lower,
            )
            self.assertNotIn(
                "python3 ${claude_plugin_root}/skills/aidd-loop/runtime/stage_result.py",
                lower,
            )
            self.assertNotIn(f"### `/feature-dev-aidd:{stage}", body_lower)
            self.assertRegex(
                body_lower,
                rf"python3\s+\$\{{claude_plugin_root\}}/skills/{re.escape(stage)}/runtime/",
            )
            self.assertNotRegex(
                body_lower,
                rf"python3\s+(?:\./)?skills/{re.escape(stage)}/runtime/",
            )
            for forbidden_surface in FORBIDDEN_LOOP_ALLOWED_TOOL_SURFACES:
                self.assertNotIn(
                    forbidden_surface,
                    frontmatter_lower,
                    msg=f"{skill_path}: frontmatter allowed-tools must not include {forbidden_surface}",
                )
            for pattern in FORBIDDEN_DIRECT_MANUAL_RECOVERY_PATTERNS:
                self.assertIsNone(
                    re.search(pattern, lower),
                    msg=f"{skill_path}: direct manual recovery pattern matched: {pattern}",
                )

    def test_stage_skill_guidance_avoids_legacy_stage_aliases(self) -> None:
        for skill_path in STAGE_SKILLS_FOR_ALIAS_GUARD:
            text = read_text(skill_path)
            for alias in LEGACY_STAGE_ALIASES:
                self.assertNotIn(alias, text, msg=f"{skill_path}: contains legacy alias {alias}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
