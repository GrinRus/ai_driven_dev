import subprocess
import tempfile
import unittest
import hashlib
import json
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, write_file


class PrdReadyCheckTests(unittest.TestCase):
    def test_prd_ready_passes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/prd/demo.prd.md", "# PRD\n\nStatus: READY\n")
            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("PRD ready", result.stdout)

    def test_prd_ready_allows_quoted_compact_answers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(
                root,
                "docs/prd/demo.prd.md",
                '# PRD\n\nStatus: READY\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1="короткий ответ с пробелами"\n\n## AIDD:OPEN_QUESTIONS\n- none\n',
            )
            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("PRD ready", result.stdout)

    def test_prd_ready_allows_quoted_compact_answers_for_q2(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(
                root,
                "docs/prd/demo.prd.md",
                '# PRD\n\nStatus: READY\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=A; Q2="нужен режим без кэша"\n\n## AIDD:OPEN_QUESTIONS\n- none\n',
            )
            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("PRD ready", result.stdout)

    def test_prd_ready_blocks_when_draft(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/prd/demo.prd.md", "# PRD\n\nStatus: draft\n")
            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BLOCK: PRD Status:", result.stderr)

    def test_prd_ready_docs_only_softens_draft_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/prd/demo.prd.md", "# PRD\n\nStatus: draft\n")
            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo", "--docs-only"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("WARN:", result.stderr)
            self.assertIn("docs_only_mode=1", result.stderr)

    def test_prd_ready_cache_hit_skips(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/prd/demo.prd.md", "# PRD\n\nStatus: READY\n")
            first = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(first.returncode, 0, msg=first.stderr)

            second = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            self.assertIn("cache hit", second.stderr.lower())

    def test_prd_ready_blocks_when_aidd_open_questions_not_empty(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(
                root,
                "docs/prd/demo.prd.md",
                "# PRD\n\nStatus: READY\n\n## AIDD:OPEN_QUESTIONS\n- Q1: pending\n",
            )
            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("AIDD:OPEN_QUESTIONS", result.stderr)

    def test_prd_ready_blocks_non_compact_answers_format(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(
                root,
                "docs/prd/demo.prd.md",
                "# PRD\n\nStatus: READY\n\n## AIDD:ANSWERS\n- свободный ответ вне compact формата\n",
            )
            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("должен быть в compact формате", result.stderr)

    def test_prd_ready_docs_only_softens_non_compact_answers_format(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(
                root,
                "docs/prd/demo.prd.md",
                "# PRD\n\nStatus: READY\n\n## AIDD:ANSWERS\n- свободный ответ вне compact формата\n",
            )
            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo", "--docs-only"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("WARN:", result.stderr)
            self.assertIn("answers_format_invalid", result.stderr)

    def test_prd_ready_manual_reinvoke_allowed_after_blocked_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/prd/demo.prd.md", "# PRD\n\nStatus: draft\n")
            first = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            second = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo", "--docs-only"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertNotEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            self.assertIn("reinvoke_allowed=1", second.stderr)

    def test_prd_ready_blocks_placeholder_answer_values(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(
                root,
                "docs/prd/demo.prd.md",
                "# PRD\n\nStatus: READY\n\n## AIDD:ANSWERS\nAIDD:ANSWERS Q1=<нужно заполнить>\n",
            )
            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("недопустимые значения", result.stderr)

    def test_prd_ready_ignores_nested_heading_after_none_open_questions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(
                root,
                "docs/prd/demo.prd.md",
                (
                    "# PRD\n\nStatus: READY\n\n"
                    "## AIDD:OPEN_QUESTIONS\n"
                    "- none\n"
                    "### Notes\n"
                    "- informational note\n\n"
                    "## AIDD:ANSWERS\n"
                    "AIDD:ANSWERS Q1=A\n"
                ),
            )
            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("PRD ready", result.stdout)

    def test_prd_ready_cache_hit_requires_cache_version(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            prd_text = (
                "# PRD\n\nStatus: READY\n\n"
                "## AIDD:OPEN_QUESTIONS\n"
                "- Q1: pending\n\n"
                "## AIDD:ANSWERS\n"
                "AIDD:ANSWERS Q1=A\n"
            )
            write_file(root, "docs/prd/demo.prd.md", prd_text)
            legacy_cache = {
                "ticket": "demo",
                "hash": hashlib.sha256(prd_text.encode("utf-8")).hexdigest(),
            }
            cache_path = root / "aidd" / ".cache" / "prd-check.hash"
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(legacy_cache, ensure_ascii=False) + "\n", encoding="utf-8")

            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("cache hit", result.stderr.lower())
            self.assertIn("AIDD:OPEN_QUESTIONS", result.stderr)


if __name__ == "__main__":
    unittest.main()
