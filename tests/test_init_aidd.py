import json
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
            "docs/architecture/profile.md",
            "docs/architecture/README.md",
            "docs/loops/README.md",
            "docs/sdlc-flow.md",
            "docs/status-machine.md",
            "reports/prd/.gitkeep",
            "reports/loops/.gitkeep",
            "AGENTS.md",
        ]
        for rel in expected_paths:
            with self.subTest(path=rel):
                self.assertTrue((project_root / rel).exists(), f"{rel} should exist after install")

        root_expected = [
            "AGENTS.md",
            "CLAUDE.md",
            ".cursor/rules/aidd.md",
            ".github/copilot-instructions.md",
        ]
        for rel in root_expected:
            with self.subTest(path=rel):
                self.assertTrue((workdir / rel).exists(), f"{rel} should exist in workspace root")

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
        root_agents = workdir / "AGENTS.md"

        project_root.mkdir(parents=True, exist_ok=True)
        target.write_text("custom placeholder", encoding="utf-8")
        root_agents.write_text("root placeholder", encoding="utf-8")

        # run without force: file should remain untouched
        result_no_force = self.run_script(workdir)
        content = target.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("custom placeholder"))
        root_content = root_agents.read_text(encoding="utf-8")
        self.assertTrue(root_content.startswith("root placeholder"))

        # run with force: file should be reset to template contents
        self.run_script(workdir, "--force")
        content = target.read_text(encoding="utf-8")
        template_content = (TEMPLATES_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(content, template_content)
        root_template = (TEMPLATES_ROOT.parent / "root" / "AGENTS.md").read_text(encoding="utf-8")
        root_content = root_agents.read_text(encoding="utf-8")
        self.assertEqual(root_content, root_template)

    def test_detect_build_tools_populates_settings(self):
        workdir = self.make_tempdir()
        (workdir / "package.json").write_text('{"name": "demo"}', encoding="utf-8")

        result = self.run_script(workdir, "--detect-build-tools")
        self.assertEqual(result.returncode, 0, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")

        settings_path = workdir / ".claude" / "settings.json"
        self.assertTrue(settings_path.exists(), "settings.json should be created")
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        tests_cfg = payload.get("automation", {}).get("tests", {})
        self.assertIn("commonPatterns", tests_cfg)
        self.assertIn("**/package.json", tests_cfg["commonPatterns"])
        self.assertIn("codePaths", tests_cfg)
        self.assertIn("codeExtensions", tests_cfg)

if __name__ == "__main__":
    unittest.main()
