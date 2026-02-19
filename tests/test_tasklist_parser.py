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

    def test_parse_test_execution_marks_non_command_entry_as_malformed(self) -> None:
        section = [
            "- profile: targeted",
            '- tasks: ["per-iteration test commands listed below", "pytest -q tests/test_ok.py"]',
            "- filters: []",
        ]

        parsed = tasklist_parser.parse_test_execution(section)
        self.assertEqual(parsed["tasks"], ["pytest -q tests/test_ok.py"])
        malformed = parsed.get("malformed_tasks") or []
        self.assertEqual(len(malformed), 1)
        self.assertEqual(malformed[0].get("reason_code"), "tasklist_non_command_entry")
        self.assertEqual(malformed[0].get("token"), "")

    def test_parse_test_execution_allows_pattern_argument_command(self) -> None:
        section = [
            "- profile: targeted",
            '- tasks: ["python3 -m pytest -k pattern tests/test_ok.py"]',
            "- filters: []",
        ]

        parsed = tasklist_parser.parse_test_execution(section)
        self.assertEqual(parsed["tasks"], ["python3 -m pytest -k pattern tests/test_ok.py"])
        malformed = parsed.get("malformed_tasks") or []
        self.assertEqual(malformed, [])

    def test_parse_test_execution_allows_relative_script_paths(self) -> None:
        section = [
            "- profile: targeted",
            '- tasks: ["tests/repo_tools/ci-lint.sh", "scripts/test.sh --quick"]',
            "- filters: []",
        ]

        parsed = tasklist_parser.parse_test_execution(section)
        self.assertEqual(parsed["tasks"], ["tests/repo_tools/ci-lint.sh", "scripts/test.sh --quick"])
        malformed = parsed.get("malformed_tasks") or []
        self.assertEqual(malformed, [])

    def test_build_compact_answers_extracts_question_numbers(self) -> None:
        text = "\n".join(
            [
                "Вопрос 1 (Blocker): выбрать профиль запуска",
                "Вопрос 2 (Clarification): выбрать режим проверок",
            ]
        )
        self.assertEqual(
            tasklist_parser.build_compact_answers(text),
            "AIDD:ANSWERS Q1=C; Q2=C",
        )

    def test_build_compact_answers_prefers_default_option_codes(self) -> None:
        text = "\n".join(
            [
                "Question 1: pick runner mode",
                "Options: A) strict B) fast C) mixed",
                "Default: B",
                "Question 2: pick budget",
                "Варианты: A) short B) medium C) long",
                "По умолчанию: C",
            ]
        )
        self.assertEqual(
            tasklist_parser.build_compact_answers(text),
            "AIDD:ANSWERS Q1=B; Q2=C",
        )

    def test_build_compact_answers_returns_empty_without_question_markers(self) -> None:
        self.assertEqual(tasklist_parser.build_compact_answers("status: blocked"), "")


if __name__ == "__main__":
    unittest.main()
