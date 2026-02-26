import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aidd_runtime import ast_index


def _completed(*, rc: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["ast-index"], returncode=rc, stdout=stdout, stderr=stderr)


class AstIndexAdapterTests(unittest.TestCase):
    def test_run_json_success_normalizes_results(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ast-index-success-") as tmpdir:
            root = Path(tmpdir)
            config = ast_index.AstIndexConfig(max_results=5)
            stats_json = '{"status":"ok","indexed_files":2}'
            query_json = (
                '{"results":['
                '{"name":"CheckoutService","kind":"class","path":"src/z.kt","line":8,"column":1},'
                '{"name":"App","kind":"class","path":"src/a.kt","line":2,"column":1}'
                "]}"
            )
            with mock.patch.object(ast_index.shutil, "which", return_value="/usr/local/bin/ast-index"):
                with mock.patch.object(
                    ast_index.subprocess,
                    "run",
                    side_effect=[
                        _completed(stdout=stats_json),
                        _completed(stdout=query_json),
                    ],
                ):
                    result = ast_index.run_json(root, config, ["search", "Checkout"])

            self.assertTrue(result.ok)
            self.assertEqual(result.reason_code, "")
            self.assertIsNotNone(result.normalized)
            normalized = result.normalized or []
            self.assertEqual([row["symbol"] for row in normalized], ["App", "CheckoutService"])

    def test_run_json_binary_missing_returns_fallback_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ast-index-missing-") as tmpdir:
            root = Path(tmpdir)
            config = ast_index.AstIndexConfig()
            with mock.patch.object(ast_index.shutil, "which", return_value=None):
                result = ast_index.run_json(root, config, ["search", "Checkout"])

            self.assertFalse(result.ok)
            self.assertEqual(result.reason_code, ast_index.REASON_BINARY_MISSING)
            self.assertEqual(result.fallback_reason_code, ast_index.REASON_FALLBACK_RG)

    def test_run_json_timeout_from_stats(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ast-index-timeout-") as tmpdir:
            root = Path(tmpdir)
            config = ast_index.AstIndexConfig()
            with mock.patch.object(ast_index.shutil, "which", return_value="/usr/local/bin/ast-index"):
                with mock.patch.object(
                    ast_index.subprocess,
                    "run",
                    side_effect=subprocess.TimeoutExpired(cmd=["ast-index", "stats"], timeout=3),
                ):
                    result = ast_index.run_json(root, config, ["search", "Checkout"])

            self.assertFalse(result.ok)
            self.assertEqual(result.reason_code, ast_index.REASON_TIMEOUT)
            self.assertEqual(result.fallback_reason_code, ast_index.REASON_FALLBACK_RG)

    def test_run_json_invalid_json_marks_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ast-index-json-") as tmpdir:
            root = Path(tmpdir)
            config = ast_index.AstIndexConfig()
            with mock.patch.object(ast_index.shutil, "which", return_value="/usr/local/bin/ast-index"):
                with mock.patch.object(
                    ast_index.subprocess,
                    "run",
                    side_effect=[
                        _completed(stdout='{"status":"ok"}'),
                        _completed(stdout="{not-json}"),
                    ],
                ):
                    result = ast_index.run_json(root, config, ["search", "Checkout"])

            self.assertFalse(result.ok)
            self.assertEqual(result.reason_code, ast_index.REASON_JSON_INVALID)
            self.assertEqual(result.fallback_reason_code, ast_index.REASON_FALLBACK_RG)

    def test_ensure_index_reports_missing_index_without_auto_rebuild(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ast-index-index-missing-") as tmpdir:
            root = Path(tmpdir)
            config = ast_index.AstIndexConfig(auto_ensure_index=False)
            with mock.patch.object(ast_index.shutil, "which", return_value="/usr/local/bin/ast-index"):
                with mock.patch.object(ast_index.subprocess, "run", return_value=_completed(rc=2, stderr="no index")):
                    result = ast_index.ensure_index(root, config)

            self.assertFalse(result.ok)
            self.assertEqual(result.reason_code, ast_index.REASON_INDEX_MISSING)
            self.assertEqual(result.fallback_reason_code, ast_index.REASON_FALLBACK_RG)

    def test_normalize_accepts_multiple_payload_shapes(self) -> None:
        payload = {
            "items": [
                {"symbol": "B", "path": "b.py", "line": 7},
                {"name": "A", "file": "a.py", "line_start": 1},
            ]
        }
        rows = ast_index.normalize(payload, max_results=10)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["symbol"], "A")
        self.assertEqual(rows[1]["symbol"], "B")


if __name__ == "__main__":
    unittest.main()

