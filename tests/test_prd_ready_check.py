import subprocess
import tempfile
import unittest
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

    def test_prd_ready_blocks_legacy_answers_format(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            write_file(
                root,
                "docs/prd/demo.prd.md",
                "# PRD\n\nStatus: READY\n\n## AIDD:ANSWERS\n- Answer 1: A\n",
            )
            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("неканоничный формат", result.stderr)


if __name__ == "__main__":
    unittest.main()
