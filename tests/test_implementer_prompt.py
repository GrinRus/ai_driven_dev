import unittest

from tests.helpers import REPO_ROOT


class ImplementerPromptTests(unittest.TestCase):
    def test_prompt_preloads_core_and_loop_skills(self) -> None:
        path = REPO_ROOT / "agents" / "implementer.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("feature-dev-aidd:aidd-core", text)
        self.assertIn("feature-dev-aidd:aidd-loop", text)
        self.assertIn("Output follows aidd-core skill", text)

    def test_prompt_enforces_single_scope_hard_stop_and_env_dependency_fail_fast(self) -> None:
        agent_text = (REPO_ROOT / "agents" / "implementer.md").read_text(encoding="utf-8")
        skill_text = (REPO_ROOT / "skills" / "implement" / "SKILL.md").read_text(encoding="utf-8")
        for text in (agent_text, skill_text):
            self.assertIn("seed_scope_cascade_detected", text)
            self.assertIn("tests_env_dependency_missing", text)
        self.assertIn("один work_item", agent_text)
        self.assertIn("one scoped work item", skill_text.lower())


if __name__ == "__main__":
    unittest.main()
