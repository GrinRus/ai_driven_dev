import json
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import aidd_schemas
from aidd_runtime import reports_pack


class AstPackSchemaTests(unittest.TestCase):
    def test_schema_registry_contains_ast_pack_schema(self) -> None:
        self.assertIn("aidd.ast.pack.v1", aidd_schemas.SCHEMA_FILES)
        path = aidd_schemas.schema_path("aidd.ast.pack.v1")
        self.assertTrue(path.exists())
        schema = aidd_schemas.load_schema("aidd.ast.pack.v1")
        self.assertEqual(schema.get("schema_version"), "aidd.ast.pack.v1")

    def test_build_ast_pack_sorts_rows_deterministically(self) -> None:
        payload = reports_pack.build_ast_pack(
            [
                {"symbol": "CheckoutService", "kind": "class", "path": "src/z.kt", "line": 10, "column": 1},
                {"symbol": "App", "kind": "class", "path": "src/a.kt", "line": 2, "column": 1},
            ],
            ticket="AST-1",
            source_path="aidd/reports/research/AST-1-rlm.pack.json",
            query="checkout",
        )
        self.assertEqual(payload.get("schema"), "aidd.ast.pack.v1")
        matches = payload.get("matches") or {}
        rows = matches.get("rows") or []
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "App")
        self.assertEqual(rows[1][0], "CheckoutService")

    def test_write_ast_pack_is_stable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ast-pack-schema-") as tmpdir:
            out = Path(tmpdir) / "AST-1-ast.pack.json"
            entries = [
                {"symbol": "CheckoutService", "kind": "class", "path": "src/z.kt", "line": 10},
                {"symbol": "App", "kind": "class", "path": "src/a.kt", "line": 2},
            ]
            reports_pack.write_ast_pack(
                entries,
                output=out,
                ticket="AST-1",
                source_path="aidd/reports/research/AST-1-rlm.pack.json",
                query="checkout",
            )
            first = out.read_text(encoding="utf-8")
            reports_pack.write_ast_pack(
                entries,
                output=out,
                ticket="AST-1",
                source_path="aidd/reports/research/AST-1-rlm.pack.json",
                query="checkout",
            )
            second = out.read_text(encoding="utf-8")
            self.assertEqual(first, second)
            payload = json.loads(first)
            self.assertEqual(payload.get("schema"), "aidd.ast.pack.v1")


if __name__ == "__main__":
    unittest.main()

