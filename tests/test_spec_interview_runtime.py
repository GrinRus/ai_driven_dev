import sys
import unittest

from tests.helpers import REPO_ROOT


SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from aidd_runtime import spec_interview


class SpecInterviewRuntimeTests(unittest.TestCase):
    def test_parse_args_accepts_answers_alias(self) -> None:
        args = spec_interview.parse_args(
            [
                "--ticket",
                "DEMO-SPEC-ALIAS",
                "--answers",
                "AIDD:ANSWERS Q1=C; Q2=B",
            ]
        )
        self.assertEqual(args.ticket, "DEMO-SPEC-ALIAS")
        self.assertIn("AIDD:ANSWERS", str(args.answers or ""))


if __name__ == "__main__":
    unittest.main()
