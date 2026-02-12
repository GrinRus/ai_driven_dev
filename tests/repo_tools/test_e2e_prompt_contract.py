from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PROMPT_PATH = REPO_ROOT / "aidd_test_flow_prompt_ralph_script_full.txt"

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

FORBIDDEN_MANUAL_RECOVERY_PATTERNS = [
    r"manual[^\n]{0,120}preflight_prepare\.py",
    r"напрямую[^\n]{0,120}preflight_prepare\.py",
    r"ручн[^\n]{0,120}preflight_prepare\.py",
    r"manual[^\n]{0,120}stage\.[a-z0-9_.-]*result\.json",
    r"ручн[^\n]{0,120}stage\.[a-z0-9_.-]*result\.json",
]


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"missing contract file: {path}")
    return path.read_text(encoding="utf-8")


class E2EPromptContractTests(unittest.TestCase):
    def test_audit_prompt_contains_env_and_drift_contracts(self) -> None:
        text = _read(AUDIT_PROMPT_PATH)
        self.assertIn("ENV_BLOCKER(plugin_not_loaded)", text)
        self.assertIn("prompt-flow drift (non-canonical stage orchestration)", text)
        self.assertIn("legacy stage aliases (`/feature-dev-aidd:planner`", text)
        self.assertIn("manual preflight/debug path", text)

    def test_loop_stage_skills_do_not_promote_manual_preflight_recovery(self) -> None:
        for skill_path in LOOP_STAGE_SKILLS:
            text = _read(skill_path)
            lower = text.lower()
            self.assertIn("preflight_prepare.py", lower)
            self.assertIn("actions_apply.py", lower)
            for pattern in FORBIDDEN_MANUAL_RECOVERY_PATTERNS:
                self.assertIsNone(
                    re.search(pattern, lower),
                    msg=f"{skill_path}: forbidden manual-recovery pattern matched: {pattern}",
                )

    def test_stage_skill_guidance_avoids_legacy_stage_aliases(self) -> None:
        for skill_path in STAGE_SKILLS_FOR_ALIAS_GUARD:
            text = _read(skill_path)
            for alias in LEGACY_STAGE_ALIASES:
                self.assertNotIn(alias, text, msg=f"{skill_path}: contains legacy alias {alias}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
