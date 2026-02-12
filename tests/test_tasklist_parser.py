from __future__ import annotations

import unittest

from aidd_runtime import tasklist_parser


class TasklistParserTests(unittest.TestCase):
    def test_parse_test_execution_supports_inline_json_lists(self) -> None:
        section = [
            "- profile: targeted",
            '- tasks: ["./gradlew test --tests \'*GitHubAnalysis*\'", "npm test -- --githubAnalysis"]',
            '- filters: ["*GitHubAnalysis*IntegrationTest", "*GitHubAnalysis*.test.tsx"]',
            "- when: on_stop",
            "- reason: targeted checks only",
        ]

        parsed = tasklist_parser.parse_test_execution(section)

        self.assertEqual(parsed["profile"], "targeted")
        self.assertEqual(
            parsed["tasks"],
            ["./gradlew test --tests '*GitHubAnalysis*'", "npm test -- --githubAnalysis"],
        )
        self.assertEqual(
            parsed["filters"],
            ["*GitHubAnalysis*IntegrationTest", "*GitHubAnalysis*.test.tsx"],
        )

    def test_parse_test_execution_keeps_scalar_fallback(self) -> None:
        section = [
            "- profile: fast",
            "- tasks: pytest -q tests/test_one.py; pytest -q tests/test_two.py",
            "- filters: *test_one*,*test_two*",
        ]

        parsed = tasklist_parser.parse_test_execution(section)

        self.assertEqual(
            parsed["tasks"],
            ["pytest -q tests/test_one.py", "pytest -q tests/test_two.py"],
        )
        self.assertEqual(parsed["filters"], ["*test_one*", "*test_two*"])

    def test_parse_test_execution_normalizes_prefixed_commands(self) -> None:
        section = [
            "- profile: targeted",
            '- tasks: ["Backend: ./gradlew test --tests \'*Controller*\'", "Frontend: npm test -- --watch=false"]',
            "- filters: []",
        ]

        parsed = tasklist_parser.parse_test_execution(section)

        self.assertEqual(
            parsed["tasks"],
            ["./gradlew test --tests '*Controller*'", "npm test -- --watch=false"],
        )

    def test_parse_test_execution_marks_shell_chain_single_entry_as_malformed(self) -> None:
        section = [
            "- profile: targeted",
            '- tasks: ["echo smoke && echo next", "pytest -q tests/test_ok.py"]',
            "- filters: []",
        ]

        parsed = tasklist_parser.parse_test_execution(section)
        self.assertEqual(parsed["tasks"], ["pytest -q tests/test_ok.py"])
        malformed = parsed.get("malformed_tasks") or []
        self.assertEqual(len(malformed), 1)
        self.assertEqual(malformed[0].get("reason_code"), "tasklist_shell_chain_single_entry")
        self.assertEqual(malformed[0].get("token"), "&&")


if __name__ == "__main__":
    unittest.main()
