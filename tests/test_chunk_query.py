import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_file


def _chunk_pack_from_stdout(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("chunk_pack="):
            return line.split("=", 1)[1].strip()
    raise AssertionError(f"chunk_pack not found in stdout: {stdout}")


def _resolve_report_path(project_root: Path, raw: str) -> Path:
    value = raw.strip()
    if value.startswith("aidd/"):
        value = value[len("aidd/") :]
    return project_root / value


class ChunkQueryTests(unittest.TestCase):
    def test_chunk_query_slice_markdown_selector(self) -> None:
        with tempfile.TemporaryDirectory(prefix="chunk-query-") as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            write_file(
                project_root,
                "docs/tasklist/demo.md",
                "\n".join(
                    [
                        "# Demo",
                        "",
                        "## AIDD:PROGRESS_LOG",
                        "- entry one",
                        "- entry two",
                        "",
                        "## AIDD:NEXT_3",
                        "- [ ] I1",
                    ]
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "chunk-query",
                    "--path",
                    "docs/tasklist/demo.md",
                    "--op",
                    "slice",
                    "--selector",
                    "AIDD:PROGRESS_LOG",
                    "--ticket",
                    "DEMO",
                ),
                cwd=project_root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            chunk_rel = _chunk_pack_from_stdout(result.stdout)
            self.assertTrue(Path(chunk_rel).name.startswith("DEMO-chunk-"))
            self.assertTrue(Path(chunk_rel).name.endswith(".pack.json"))
            chunk_path = _resolve_report_path(project_root, chunk_rel)
            self.assertTrue(chunk_path.exists(), f"chunk pack not found: {chunk_path}")

            payload = json.loads(chunk_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "aidd.report.pack.v1")
            self.assertEqual(payload.get("type"), "context-chunk")
            self.assertEqual(payload.get("backend"), "markdown")
            self.assertEqual(payload.get("op"), "slice")
            content = payload.get("result", {}).get("content", "")
            self.assertIn("## AIDD:PROGRESS_LOG", content)
            self.assertIn("- entry one", content)
            self.assertNotIn("## AIDD:NEXT_3", content)

    def test_chunk_query_search_jsonl(self) -> None:
        with tempfile.TemporaryDirectory(prefix="chunk-query-") as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            lines = [
                {"id": "n1", "path": "src/checkout.py", "summary": "CheckoutService validates idempotency."},
                {"id": "n2", "path": "src/payments.py", "summary": "PaymentService handles capture."},
            ]
            write_file(
                project_root,
                "reports/research/demo-rlm.nodes.jsonl",
                "\n".join(json.dumps(item, ensure_ascii=False) for item in lines) + "\n",
            )

            result = subprocess.run(
                cli_cmd(
                    "chunk-query",
                    "--path",
                    "reports/research/demo-rlm.nodes.jsonl",
                    "--op",
                    "search",
                    "--query",
                    "checkoutservice|idempotency",
                    "--ticket",
                    "DEMO",
                    "--max-results",
                    "5",
                ),
                cwd=project_root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            chunk_path = _resolve_report_path(project_root, _chunk_pack_from_stdout(result.stdout))
            payload = json.loads(chunk_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("backend"), "jsonl")
            self.assertEqual(payload.get("op"), "search")
            result_block = payload.get("result", {})
            self.assertGreaterEqual(int(result_block.get("match_count", 0)), 1)
            matches = result_block.get("matches") or []
            self.assertTrue(matches)
            self.assertIn("CheckoutService", matches[0].get("text", ""))

    def test_chunk_query_split_and_get_chunk_for_log(self) -> None:
        with tempfile.TemporaryDirectory(prefix="chunk-query-") as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            log_lines = [f"line {idx:02d}" for idx in range(1, 13)]
            write_file(project_root, "reports/logs/app.log", "\n".join(log_lines) + "\n")

            split_result = subprocess.run(
                cli_cmd(
                    "chunk-query",
                    "--path",
                    "reports/logs/app.log",
                    "--op",
                    "split",
                    "--chunk-lines",
                    "5",
                    "--ticket",
                    "DEMO",
                ),
                cwd=project_root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(split_result.returncode, 0, msg=split_result.stderr)
            split_pack = _resolve_report_path(project_root, _chunk_pack_from_stdout(split_result.stdout))
            split_payload = json.loads(split_pack.read_text(encoding="utf-8"))
            split_block = split_payload.get("result", {})
            self.assertEqual(split_payload.get("backend"), "log")
            self.assertEqual(int(split_block.get("chunk_count_total", 0)), 3)
            chunks = split_block.get("chunks") or []
            self.assertEqual(chunks[0].get("line_start"), 1)
            self.assertEqual(chunks[0].get("line_end"), 5)

            get_chunk_result = subprocess.run(
                cli_cmd(
                    "chunk-query",
                    "--path",
                    "reports/logs/app.log",
                    "--op",
                    "get_chunk",
                    "--chunk-lines",
                    "5",
                    "--chunk-index",
                    "1",
                    "--ticket",
                    "DEMO",
                ),
                cwd=project_root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(get_chunk_result.returncode, 0, msg=get_chunk_result.stderr)
            get_chunk_pack = _resolve_report_path(project_root, _chunk_pack_from_stdout(get_chunk_result.stdout))
            get_chunk_payload = json.loads(get_chunk_pack.read_text(encoding="utf-8"))
            result_block = get_chunk_payload.get("result", {})
            self.assertEqual(result_block.get("line_start"), 6)
            self.assertEqual(result_block.get("line_end"), 10)
            content = result_block.get("content", "")
            self.assertIn("line 06", content)
            self.assertIn("line 10", content)
            self.assertNotIn("line 11", content)

    def test_chunk_query_search_requires_query(self) -> None:
        with tempfile.TemporaryDirectory(prefix="chunk-query-") as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            write_file(project_root, "docs/notes.txt", "hello\nworld\n")

            result = subprocess.run(
                cli_cmd("chunk-query", "--path", "docs/notes.txt", "--op", "search", "--ticket", "DEMO"),
                cwd=project_root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("search requires --query", result.stderr)


if __name__ == "__main__":
    unittest.main()
