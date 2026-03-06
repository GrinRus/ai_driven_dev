import hashlib
import json
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

    def test_prd_ready_invalidates_legacy_cache_without_version(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-check-") as tmpdir:
            root = Path(tmpdir)
            text = "# PRD\n\nStatus: READY\n"
            write_file(root, "docs/prd/demo.prd.md", text)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            write_file(
                root,
                ".cache/prd-check.hash",
                json.dumps({"ticket": "demo", "hash": digest}, ensure_ascii=False, indent=2) + "\n",
            )

            result = subprocess.run(
                cli_cmd("prd-check", "--ticket", "demo"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertNotIn("cache hit", result.stderr.lower())

            payload = json.loads((root / "aidd" / ".cache" / "prd-check.hash").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("cache_version"), "2")


if __name__ == "__main__":
    unittest.main()
