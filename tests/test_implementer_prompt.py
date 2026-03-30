import unittest

from tests.helpers import REPO_ROOT


class ImplementerPromptTests(unittest.TestCase):
    def test_prompt_preloads_core_and_loop_skills(self) -> None:
        path = REPO_ROOT / "agents" / "implementer.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("feature-dev-aidd:aidd-core", text)
        self.assertIn("feature-dev-aidd:aidd-loop", text)
        self.assertIn("Output follows aidd-core skill", text)
        self.assertIn("set_active_feature -> set_active_stage(implement) -> loop_pack --stage implement --pick-next", text)
        self.assertIn("Skill(:status)", text)
        self.assertIn("Bash(:status ...)", text)
        self.assertIn("seed_stage_non_converging_command", text)
        self.assertIn("implement_run.py -> actions_apply.py -> stage_result.py", text)


if __name__ == "__main__":
    unittest.main()
