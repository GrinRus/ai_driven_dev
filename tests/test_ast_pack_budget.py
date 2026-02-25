import json
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import reports_pack


def _entries(count: int) -> list[dict]:
    rows = []
    for idx in range(count):
        rows.append(
            {
                "symbol": f"Symbol{idx:03d}",
                "kind": "function",
                "path": f"src/module_{idx % 5}.py",
                "line": idx + 1,
                "column": 1,
                "snippet": "x" * 120,
                "score": 0.5,
            }
        )
    return rows


class AstPackBudgetTests(unittest.TestCase):
    def test_write_ast_pack_respects_max_items(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ast-pack-budget-") as tmpdir:
            out = Path(tmpdir) / "AST-2-ast.pack.json"
            reports_pack.write_ast_pack(
                _entries(20),
                output=out,
                ticket="AST-2",
                source_path="aidd/reports/research/AST-2-rlm.pack.json",
                query="Symbol",
                limits={"max_items": 5, "snippet_chars": 40, "max_chars": 8000, "max_lines": 220},
            )
            payload = json.loads(out.read_text(encoding="utf-8"))
            rows = payload.get("matches", {}).get("rows", [])
            self.assertEqual(len(rows), 5)
            self.assertEqual(payload.get("stats", {}).get("matches_trimmed"), 15)

    def test_write_ast_pack_enforce_raises_when_budget_too_small(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ast-pack-budget-enforce-") as tmpdir:
            out = Path(tmpdir) / "AST-3-ast.pack.json"
            with self.assertRaises(ValueError):
                reports_pack.write_ast_pack(
                    _entries(3),
                    output=out,
                    ticket="AST-3",
                    source_path="aidd/reports/research/AST-3-rlm.pack.json",
                    query="Symbol",
                    limits={"max_items": 3, "snippet_chars": 20, "max_chars": 120, "max_lines": 10},
                    enforce=True,
                )


if __name__ == "__main__":
    unittest.main()

