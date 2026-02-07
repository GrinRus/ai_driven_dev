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
            "config/gates.json",
            "docs/prd/template.md",
            "docs/plan/template.md",
            "docs/tasklist/template.md",
            "docs/research/template.md",
            "docs/spec/template.spec.yaml",
            "docs/prompting/conventions.md",
            "docs/loops/template.loop-pack.md",
            "reports/prd/.gitkeep",
            "reports/loops/.gitkeep",
            "reports/context/template.context-pack.md",
            "AGENTS.md",
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

    def test_detect_stack_alias_maps_to_detect_build_tools(self):
        workdir = self.make_tempdir()
        (workdir / "package.json").write_text('{"name": "demo"}', encoding="utf-8")

        result = self.run_script(workdir, "--detect-stack")
        self.assertEqual(result.returncode, 0, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")

        settings_path = workdir / ".claude" / "settings.json"
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        tests_cfg = payload.get("automation", {}).get("tests", {})
        self.assertIn("**/package.json", tests_cfg.get("commonPatterns", []))

    def test_dry_run_does_not_modify_filesystem(self):
        workdir = self.make_tempdir()
        (workdir / "package.json").write_text('{"name":"demo"}', encoding="utf-8")

        result = self.run_script(workdir, "--dry-run", "--detect-build-tools", "--enable-ci")
        self.assertEqual(result.returncode, 0, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self.assertIn("dry-run", result.stdout)
        self.assertFalse((workdir / PROJECT_SUBDIR).exists(), "dry-run must not create project root")
        self.assertFalse((workdir / ".claude" / "settings.json").exists(), "dry-run must not write settings")
        self.assertFalse((workdir / ".github" / "workflows" / "aidd-manual.yml").exists(), "dry-run must not write CI")

    def test_enable_ci_writes_manual_workflow(self):
        workdir = self.make_tempdir()

        result = self.run_script(workdir, "--enable-ci")
        self.assertEqual(result.returncode, 0, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        workflow = workdir / ".github" / "workflows" / "aidd-manual.yml"
        self.assertTrue(workflow.exists(), "enable-ci must create workflow file")
        content = workflow.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch", content)
        self.assertIn("AIDD CI scaffold is enabled", content)

    def test_help_lists_supported_init_flags(self):
        result = subprocess.run(
            cli_cmd("init", "--help"),
            cwd=self.make_tempdir(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            env=cli_env(),
        )
        self.assertIn("--enable-ci", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--detect-build-tools", result.stdout)
        self.assertNotIn("--detect-stack", result.stdout)

if __name__ == "__main__":
    unittest.main()
