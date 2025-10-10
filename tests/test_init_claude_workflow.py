import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "init-claude-workflow.sh"


class InitClaudeWorkflowTests(unittest.TestCase):
    def run_script(self, workdir: Path, *args: str) -> subprocess.CompletedProcess:
        """Run init-claude-workflow.sh inside workdir and return the completed process."""
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

    def make_tempdir(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="claude-init-test-"))
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_fresh_install_creates_expected_files(self):
        workdir = self.make_tempdir()

        result = self.run_script(workdir)
        self.assertEqual(result.returncode, 0, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")

        expected_paths = [
            ".claude/settings.json",
            ".claude/hooks/format-and-test.sh",
            "config/conventions.json",
            "scripts/commit_msg.py",
            "docs/prd.template.md",
        ]
        for rel in expected_paths:
            with self.subTest(path=rel):
                self.assertTrue((workdir / rel).exists(), f"{rel} should exist after install")

        conventions = (workdir / "config/conventions.json").read_text(encoding="utf-8")
        self.assertIn('"mode": "ticket-prefix"', conventions)

    def test_dry_run_does_not_create_files(self):
        workdir = self.make_tempdir()

        result = self.run_script(workdir, "--dry-run")
        self.assertIn("Dry run completed", result.stdout)

        self.assertFalse(any(workdir.iterdir()), "dry-run must not create files or directories")

    def test_force_overwrites_existing_files(self):
        workdir = self.make_tempdir()
        target = workdir / "CLAUDE.md"

        workdir.mkdir(parents=True, exist_ok=True)
        target.write_text("custom placeholder", encoding="utf-8")

        # run without force: file should remain untouched
        result_no_force = self.run_script(workdir)
        self.assertIn("skip: CLAUDE.md", result_no_force.stderr + result_no_force.stdout)
        self.assertEqual(target.read_text(encoding="utf-8"), "custom placeholder")

        # run with force: file should be reset to template contents
        self.run_script(workdir, "--force")
        content = target.read_text(encoding="utf-8")
        self.assertTrue(
            content.startswith("# Claude Code Workflow"),
            "force flag must overwrite existing files",
        )


if __name__ == "__main__":
    unittest.main()
