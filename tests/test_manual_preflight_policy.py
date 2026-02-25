import unittest
from pathlib import Path
import re

from tests.helpers import REPO_ROOT

LOOP_POLICY_MARKERS = (
    "[AIDD_LOOP_POLICY:MANUAL_STAGE_RESULT_FORBIDDEN]",
    "[AIDD_LOOP_POLICY:CANONICAL_STAGE_RESULT_PATH]",
    "[AIDD_LOOP_POLICY:NON_CANONICAL_STAGE_RESULT_FORBIDDEN]",
)
INTERNAL_PREFLIGHT_SCRIPT_RE = re.compile(r"preflight_prepare\.py", re.IGNORECASE)


class ManualPreflightPolicyTests(unittest.TestCase):
    def _skill_text(self, relative_path: str) -> str:
        return (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    def _assert_loop_stage_skill_policy(self, relative_path: str) -> None:
        text = self._skill_text(relative_path)
        self.assertNotRegex(text, INTERNAL_PREFLIGHT_SCRIPT_RE)
        for marker in LOOP_POLICY_MARKERS:
            self.assertIn(marker, text)
        self.assertIn("internal preflight", text.lower())
        self.assertIn(
            "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py",
            text,
        )
        self.assertNotIn(
            "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/stage_result.py --ticket",
            text,
        )

    def test_qa_skill_loop_policy(self) -> None:
        self._assert_loop_stage_skill_policy("skills/qa/SKILL.md")

    def test_review_skill_loop_policy(self) -> None:
        self._assert_loop_stage_skill_policy("skills/review/SKILL.md")

    def test_implement_skill_loop_policy(self) -> None:
        self._assert_loop_stage_skill_policy("skills/implement/SKILL.md")


if __name__ == "__main__":
    unittest.main()
