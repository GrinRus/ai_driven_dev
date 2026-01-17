import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from tests.helpers import PROJECT_SUBDIR, TEMPLATES_ROOT, cli_cmd, cli_env


class InitAiddTests(unittest.TestCase):
    def run_script(self, workdir: Path, *args: str) -> subprocess.CompletedProcess:
        """Run tools/init.sh for the workspace root and return the completed process."""
        project_root = workdir if workdir.name == PROJECT_SUBDIR else workdir / PROJECT_SUBDIR
        project_root.mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            cli_cmd("init", *args),
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            env=cli_env(),
        )

    def make_tempdir(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="aidd-init-test-"))
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_fresh_install_creates_expected_files(self):
        workdir = self.make_tempdir()

        result = self.run_script(workdir)
        self.assertEqual(result.returncode, 0, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")

        project_root = workdir / PROJECT_SUBDIR
        expected_paths = [
            "config/context_gc.json",
            "config/conventions.json",
            "docs/prd/template.md",
            "reports/prd/.gitkeep",
            "AGENTS.md",
            ".markdownlint.yaml",
        ]
        for rel in expected_paths:
            with self.subTest(path=rel):
                self.assertTrue((project_root / rel).exists(), f"{rel} should exist after install")

        conventions = (project_root / "config/conventions.json").read_text(encoding="utf-8")
        self.assertIn('"mode": "ticket-prefix"', conventions)

    def test_idempotent_run_does_not_overwrite(self):
        workdir = self.make_tempdir()

        first = self.run_script(workdir)
        self.assertIn("[aidd:init]", first.stdout)

        project_root = workdir / PROJECT_SUBDIR
        before = (project_root / "config" / "conventions.json").read_text(encoding="utf-8")
        second = self.run_script(workdir)
        self.assertIn("no changes", second.stdout)
        after = (project_root / "config" / "conventions.json").read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_force_overwrites_existing_files(self):
        workdir = self.make_tempdir()
        project_root = workdir / PROJECT_SUBDIR
        target = project_root / "AGENTS.md"

        project_root.mkdir(parents=True, exist_ok=True)
        target.write_text("custom placeholder", encoding="utf-8")

        # run without force: file should remain untouched
        result_no_force = self.run_script(workdir)
        content = target.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("custom placeholder"))

        # run with force: file should be reset to template contents
        self.run_script(workdir, "--force")
        content = target.read_text(encoding="utf-8")
        template_content = (TEMPLATES_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(content, template_content)

if __name__ == "__main__":
    unittest.main()
