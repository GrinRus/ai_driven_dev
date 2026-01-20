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


if __name__ == "__main__":
    unittest.main()
