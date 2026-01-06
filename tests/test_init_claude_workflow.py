import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import PAYLOAD_ROOT, PROJECT_SUBDIR


SCRIPT = PAYLOAD_ROOT / "init-claude-workflow.sh"


class InitClaudeWorkflowTests(unittest.TestCase):
    def run_script(self, workdir: Path, *args: str) -> subprocess.CompletedProcess:
        """Run init-claude-workflow.sh inside workdir and return the completed process."""
        env = os.environ.copy()
        env.setdefault("CLAUDE_TEMPLATE_DIR", str(PAYLOAD_ROOT))
        project_root = workdir if workdir.name == PROJECT_SUBDIR else workdir / PROJECT_SUBDIR
        project_root.mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            env=env,
        )

    def make_tempdir(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="claude-init-test-"))
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_fresh_install_creates_expected_files(self):
        workdir = self.make_tempdir()

        result = self.run_script(workdir)
        self.assertEqual(result.returncode, 0, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")

        project_root = workdir / PROJECT_SUBDIR
        expected_paths = [
            "hooks/format-and-test.sh",
            "config/context_gc.json",
            "config/conventions.json",
            "docs/prd/template.md",
            "docs/cli-migration.md",
            "reports/prd/.gitkeep",
        ]
        for rel in expected_paths:
            with self.subTest(path=rel):
                self.assertTrue((project_root / rel).exists(), f"{rel} should exist after install")

        conventions = (project_root / "config/conventions.json").read_text(encoding="utf-8")
        self.assertIn('"mode": "ticket-prefix"', conventions)
        # workspace-root plugin files
        settings_root = workdir / ".claude" / "settings.json"
        marketplace_root = workdir / ".claude-plugin" / "marketplace.json"
        self.assertTrue(settings_root.exists(), "workspace/.claude/settings.json should be created")
        self.assertTrue(marketplace_root.exists(), "workspace/.claude-plugin/marketplace.json should be created")

    def test_dry_run_does_not_create_files(self):
        workdir = self.make_tempdir()

        result = self.run_script(workdir, "--dry-run")
        self.assertIn("Dry run completed", result.stdout)

        project_root = workdir / PROJECT_SUBDIR
        contents = list(project_root.rglob("*")) if project_root.exists() else []
        self.assertEqual(
            [p for p in contents if p.is_file()],
            [],
            "dry-run must not create files",
        )

    def test_force_overwrites_existing_files(self):
        workdir = self.make_tempdir()
        project_root = workdir / PROJECT_SUBDIR
        target = project_root / "AGENTS.md"

        project_root.mkdir(parents=True, exist_ok=True)
        target.write_text("custom placeholder", encoding="utf-8")

        # run without force: file should remain untouched
        result_no_force = self.run_script(workdir)
        combined_output = result_no_force.stderr + result_no_force.stdout
        self.assertTrue(
            "appended: AGENTS.md" in combined_output or "copied: AGENTS.md" in combined_output,
            "bootstrap should log touching AGENTS.md",
        )
        content = target.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("custom placeholder"))

        # run with force: file should be reset to template contents
        self.run_script(workdir, "--force")
        content = target.read_text(encoding="utf-8")
        payload_content = (PAYLOAD_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(content, payload_content)

if __name__ == "__main__":
    unittest.main()
