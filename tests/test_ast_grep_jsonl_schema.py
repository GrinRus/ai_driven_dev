import unittest

from tools import ast_grep_scan


class AstGrepSchemaTests(unittest.TestCase):
    def test_normalized_match_schema(self) -> None:
        payload = ast_grep_scan._normalize_match(
            {
                "rule_id": "demo-rule",
                "path": "src/main/kotlin/App.kt",
                "line": 12,
                "col": 3,
                "snippet": "class Demo {}",
                "message": "demo",
                "tags": ["jvm"],
            }
        )
        for key in ("schema", "rule_id", "path", "line", "col", "snippet", "message", "tags"):
            self.assertIn(key, payload)
        self.assertEqual(payload["schema"], ast_grep_scan.AST_GREP_SCHEMA)

    def test_split_ruleset_into_rule_blocks(self) -> None:
        ruleset = """---
rules:
  - id: demo-rule
    language: Java
    rule:
      pattern: "@RestController"
    message: "demo"
  - id: second-rule
    language: Kotlin
    rule:
      pattern: "@Controller"
    message: "demo-kt"
"""
        blocks = ast_grep_scan._split_ruleset(ruleset)
        self.assertEqual(len(blocks), 2)
        self.assertTrue(blocks[0].lstrip().startswith("id: demo-rule"))
        self.assertTrue(blocks[1].lstrip().startswith("id: second-rule"))


if __name__ == "__main__":
    unittest.main()
