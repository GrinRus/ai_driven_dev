import sys
import unittest

from tests.helpers import REPO_ROOT


SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from aidd_runtime import spec_interview


class SpecInterviewRuntimeTests(unittest.TestCase):
    def test_parse_args_rejects_removed_answers_alias(self) -> None:
        with self.assertRaises(SystemExit):
            spec_interview.parse_args(
                [
                    "--ticket",
                    "DEMO-SPEC-ALIAS",
                    "--answers",
                    "AIDD:ANSWERS Q1=C; Q2=B",
                ]
            )


if __name__ == "__main__":
    unittest.main()
