import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT


class ImplementerPromptTests(unittest.TestCase):
    def test_prompt_includes_test_scope_and_cadence(self) -> None:
        path = REPO_ROOT / "agents" / "implementer.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("Test policy (IMPLEMENT = NO TESTS)", text)
        self.assertIn("AIDD_TEST_PROFILE", text)


if __name__ == "__main__":
    unittest.main()
