import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT


class ImplementerPromptTests(unittest.TestCase):
    def test_prompt_preloads_core_and_loop_skills(self) -> None:
        path = REPO_ROOT / "agents" / "implementer.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("feature-dev-aidd:aidd-core", text)
        self.assertIn("feature-dev-aidd:aidd-loop", text)
        self.assertIn("Output follows aidd-core skill", text)


if __name__ == "__main__":
    unittest.main()
