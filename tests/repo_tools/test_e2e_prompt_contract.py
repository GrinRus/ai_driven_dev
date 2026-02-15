from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PROMPT_FULL = REPO_ROOT / "aidd_test_flow_prompt_ralph_script_full.txt"
AUDIT_PROMPT_SMOKE = REPO_ROOT / "aidd_test_flow_prompt_ralph_script.txt"

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


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"missing contract file: {path}")
    return path.read_text(encoding="utf-8")


def _front_matter(path: Path) -> str:
    text = _read(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:idx])
    return ""


def _body(path: Path) -> str:
    text = _read(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[idx + 1 :])
    return text


class E2EPromptContractTests(unittest.TestCase):
    def test_full_prompt_contains_retry_seed_and_drift_guards(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn("retry-триггер разрешён только по текущему stage-return", text)
        self.assertIn("question retry для шага 6 запрещён", text)
        self.assertIn("prompt-flow drift (non-canonical stage orchestration)", text)
        self.assertIn("manual preflight/debug path", text)

    def test_prompt_policy_uses_stage_return_only_signal_extraction(self) -> None:
        for prompt in (AUDIT_PROMPT_FULL, AUDIT_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertIn(
                "не считать trigger-ом `Q*`/`AIDD:ANSWERS`/`Question` внутри вложенных артефактов",
                text,
                msg=f"{prompt}: missing nested-artifact trigger guard",
            )
            self.assertRegex(
                text.lower(),
                r"stage-level классификац|stage-return",
                msg=f"{prompt}: missing stage-return-only extraction policy",
            )

    def test_prompt_policy_has_stream_liveness_contract(self) -> None:
        full_text = _read(AUDIT_PROMPT_FULL).lower()
        smoke_text = _read(AUDIT_PROMPT_SMOKE).lower()
        for text, label in ((full_text, "full"), (smoke_text, "smoke")):
            self.assertIn("active_stream", text, msg=f"{label}: missing active_stream policy")
            self.assertIn("main log", text, msg=f"{label}: missing main log probe policy")
            self.assertRegex(
                text,
                r"stream.*jsonl|stream-jsonl",
                msg=f"{label}: missing stream jsonl probe policy",
            )

    def test_prompt_launcher_policy_enforces_cwd_plugin_dir_and_verbose(self) -> None:
        for prompt in (AUDIT_PROMPT_FULL, AUDIT_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertIn('cd "$PROJECT_DIR"', text, msg=f"{prompt}: missing cwd launcher invariant")
            self.assertIn('--plugin-dir "$PLUGIN_DIR"', text, msg=f"{prompt}: missing plugin-dir launcher invariant")
            self.assertIn("--verbose --output-format stream-json", text, msg=f"{prompt}: missing stream-json verbose flags")

    def test_prompt_ralph_blocked_policy_parity(self) -> None:
        full_text = _read(AUDIT_PROMPT_FULL)
        smoke_text = _read(AUDIT_PROMPT_SMOKE)
        for text, label in ((full_text, "full"), (smoke_text, "smoke")):
            self.assertIn("BLOCKED_POLICY=strict|ralph", text, msg=f"{label}: missing blocked policy variable")
            self.assertIn("RECOVERABLE_BLOCK_RETRIES", text, msg=f"{label}: missing recoverable retry variable")
        self.assertIn("--blocked-policy $BLOCKED_POLICY", full_text)
        self.assertIn("--recoverable-block-retries $RECOVERABLE_BLOCK_RETRIES", full_text)
        self.assertIn("recoverable_blocked", full_text)
        self.assertIn("recovery_path", full_text)
        self.assertIn("retry_attempt", full_text)

    def test_prompt_retry_contract_mentions_runtime_arg_compat_guards(self) -> None:
        for prompt in (AUDIT_PROMPT_FULL, AUDIT_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertIn("--answers", text, msg=f"{prompt}: missing spec-interview retry arg guard")
            self.assertIn("--plan-path", text, msg=f"{prompt}: missing plan-review-gate retry arg guard")
            self.assertRegex(
                text.lower(),
                r"backward-compatible aliases|compat",
                msg=f"{prompt}: missing runtime arg compatibility guard",
            )

    def test_full_prompt_cwd_recovery_stays_on_project_dir(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn("refusing to use plugin repository as workspace root", text)
        self.assertIn("исправь `cwd` на `PROJECT_DIR`", text)

    def test_loop_stage_skills_enforce_wrapper_only_policy(self) -> None:
        for skill_path in LOOP_STAGE_SKILLS:
            text = _read(skill_path)
            lower = text.lower()
            body_lower = _body(skill_path).lower()
            frontmatter_lower = _front_matter(skill_path).lower()
            stage = skill_path.parent.name
            self.assertIn("forbidden", lower)
            self.assertIn("preflight_prepare.py", lower)
            self.assertRegex(lower, r"stage\." + re.escape(stage) + r"\.result\.json")
            self.assertIn("wrapper", lower)
            self.assertIn("actions_apply.py", lower)
            self.assertNotIn(f"### `/feature-dev-aidd:{stage}", body_lower)
            self.assertNotRegex(
                body_lower,
                rf"python3\s+\$\{{claude_plugin_root\}}/skills/{re.escape(stage)}/runtime/",
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
            text = _read(skill_path)
            for alias in LEGACY_STAGE_ALIASES:
                self.assertNotIn(alias, text, msg=f"{skill_path}: contains legacy alias {alias}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
