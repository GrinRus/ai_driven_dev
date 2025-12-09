import unittest
from pathlib import Path

from .helpers import PAYLOAD_ROOT


class PlannerAgentTests(unittest.TestCase):
    def test_planner_mandates_patterns_and_reuse(self) -> None:
        text = (PAYLOAD_ROOT / "agents" / "planner.md").read_text(encoding="utf-8")
        lower = text.lower()
        for token in ["kiss", "yagni", "dry", "solid"]:
            self.assertIn(token, lower, msg=f"Expected '{token}' in planner prompt")
        self.assertIn("service layer", lower)
        self.assertIn("adapters", lower)
        self.assertIn("reuse", lower)
        self.assertIn("Architecture & Patterns".lower(), lower)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
