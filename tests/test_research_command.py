import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, cli_cmd, cli_env


SRC_ROOT = REPO_ROOT

if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from aidd_runtime import research


class ResearchCommandTest(unittest.TestCase):
    def test_research_command_materializes_summary(self):
        with tempfile.TemporaryDirectory(prefix="aidd-research-") as tmpdir:
            project_root = Path(tmpdir) / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=Path(tmpdir),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )

            command_env = cli_env()
            subprocess.run(
                cli_cmd(
                    "research",
                    "--ticket",
                    "TEST-123",
                    "--keywords",
                    "test",
                    "--limit",
                    "1",
                ),
                cwd=project_root,
                env=command_env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            summary_path = project_root / "docs" / "research" / "TEST-123.md"
            self.assertTrue(summary_path.exists(), "Research summary should be materialised")

    def test_research_command_blocks_without_research_hints(self):
        with tempfile.TemporaryDirectory(prefix="aidd-research-hints-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )

            args = research.parse_args(
                [
                    "--ticket",
                    "HINTS-0",
                    "--auto",
                    "--limit",
                    "1",
                ]
            )
            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with self.assertRaises(RuntimeError) as exc:
                    research.run(args)
            finally:
                os.chdir(old_cwd)
            self.assertIn("AIDD:RESEARCH_HINTS", str(exc.exception))

    def test_research_command_uses_workspace_root_with_deep_code(self):
        with tempfile.TemporaryDirectory(prefix="aidd-research-ws-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )

            code_dir = workspace / "src" / "main" / "kotlin"
            code_dir.mkdir(parents=True, exist_ok=True)
            demo_file = code_dir / "WorkspaceDemo.kt"
            demo_file.write_text(
                "package demo\n\nfun workspaceCaller() { /* WORK-1: workspace demo */ }\n", encoding="utf-8"
            )

            args = research.parse_args(
                [
                    "--ticket",
                    "WORK-1",
                    "--auto",
                    "--deep-code",
                    "--keywords",
                    "workspace",
                    "--limit",
                    "5",
                ]
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    research.run(args)
            finally:
                os.chdir(old_cwd)

            output = stdout.getvalue()
            self.assertIn("rlm targets saved", output)
            targets_path = project_root / "reports" / "research" / "WORK-1-rlm-targets.json"
            self.assertTrue(targets_path.exists(), "RLM targets JSON should be generated")
            payload = json.loads(targets_path.read_text(encoding="utf-8"))
            files = [str(item) for item in payload.get("files") or []]
            self.assertTrue(any(item.endswith("WorkspaceDemo.kt") for item in files))

    def test_research_command_syncs_rlm_paths_when_paths_missing(self):
        with tempfile.TemporaryDirectory(prefix="aidd-research-sync-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )

            frontend_dir = workspace / "frontend"
            frontend_dir.mkdir(parents=True, exist_ok=True)
            (frontend_dir / "package.json").write_text('{"name": "frontend"}\n', encoding="utf-8")

            backend_dir = workspace / "backend" / "src" / "main" / "java"
            backend_dir.mkdir(parents=True, exist_ok=True)
            (backend_dir / "Focus.java").write_text("package demo;\nclass Focus {}\n", encoding="utf-8")

            args = research.parse_args(
                [
                    "--ticket",
                    "SYNC-1",
                    "--rlm-paths",
                    "backend/src/main/java",
                    "--targets-mode",
                    "explicit",
                    "--limit",
                    "5",
                ]
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                research.run(args)
            finally:
                os.chdir(old_cwd)

            targets_path = project_root / "reports" / "research" / "SYNC-1-rlm-targets.json"
            payload = json.loads(targets_path.read_text(encoding="utf-8"))
            paths = [str(item) for item in payload.get("paths") or []]
            self.assertTrue(paths)
            self.assertTrue(all(path.startswith("backend/src/main/java") for path in paths), paths)
            self.assertFalse(any("frontend" in path for path in paths))
            files = [str(item) for item in payload.get("files") or []]
            self.assertFalse(any("frontend" in path for path in files))

    def test_research_command_suppresses_missing_paths_with_discovery(self):
        with tempfile.TemporaryDirectory(prefix="aidd-research-paths-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )

            code_dir = workspace / "backend" / "src" / "main" / "kotlin"
            code_dir.mkdir(parents=True, exist_ok=True)
            (code_dir / "BackendDemo.kt").write_text("package demo\n\nclass BackendDemo {}\n", encoding="utf-8")

            args = research.parse_args(
                [
                    "--ticket",
                    "backend-demo",
                    "--keywords",
                    "backend",
                    "--limit",
                    "1",
                ]
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    research.run(args)
            finally:
                os.chdir(old_cwd)

            self.assertNotIn("missing research paths", stderr.getvalue())
            targets_path = project_root / "reports" / "research" / "backend-demo-rlm-targets.json"
            payload = json.loads(targets_path.read_text(encoding="utf-8"))
            self.assertNotIn("src/main", payload.get("paths") or [])

    def test_research_command_respects_parent_paths_argument(self):
        with tempfile.TemporaryDirectory(prefix="aidd-research-parent-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )

            extra_dir = workspace / "foo"
            extra_dir.mkdir(parents=True, exist_ok=True)
            extra_file = extra_dir / "Extra.kt"
            extra_file.write_text("// FOO-7 integration point", encoding="utf-8")

            args = research.parse_args(
                [
                    "--ticket",
                    "FOO-7",
                    "--paths",
                    "../foo",
                    "--auto",
                    "--limit",
                    "5",
                ]
            )
            stdout = io.StringIO()
            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with contextlib.redirect_stdout(stdout):
                    research.run(args)
            finally:
                os.chdir(old_cwd)

            targets_path = project_root / "reports" / "research" / "FOO-7-rlm-targets.json"
            self.assertTrue(targets_path.exists(), "RLM targets JSON should be generated for parent paths")
            payload = json.loads(targets_path.read_text(encoding="utf-8"))
            all_paths = [str(item) for item in (payload.get("paths") or []) + (payload.get("paths_discovered") or [])]
            self.assertTrue(any("foo" in p for p in all_paths), all_paths)
            files = [str(item) for item in payload.get("files") or []]
            self.assertTrue(any(item.endswith("Extra.kt") for item in files), files)

    def test_research_command_syncs_prd_overrides(self):
        with tempfile.TemporaryDirectory(prefix="aidd-research-overrides-") as tmpdir:
            project_root = Path(tmpdir) / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=Path(tmpdir),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )

            prd_text = "\n".join(
                [
                    "# PRD",
                    "",
                    "## Decisions",
                    "- USER OVERRIDE: timezone=UTC",
                    "- USER OVERRIDE: test filtering=enabled",
                ]
            )
            (project_root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "prd" / "OVR-1.prd.md").write_text(prd_text, encoding="utf-8")

            subprocess.run(
                cli_cmd(
                    "research",
                    "--ticket",
                    "OVR-1",
                    "--keywords",
                    "overrides",
                    "--limit",
                    "1",
                ),
                cwd=project_root,
                env=cli_env(),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            research_path = project_root / "docs" / "research" / "OVR-1.md"
            self.assertTrue(research_path.exists(), "Research summary should be materialised")
            research_text = research_path.read_text(encoding="utf-8")
            self.assertIn("## AIDD:PRD_OVERRIDES", research_text)
            self.assertIn("USER OVERRIDE: timezone=UTC", research_text)
            self.assertIn("USER OVERRIDE: test filtering=enabled", research_text)

    def test_research_command_auto_fast_scan_non_jvm(self):
        with tempfile.TemporaryDirectory(prefix="aidd-research-fast-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )

            code_dir = workspace / "src" / "main"
            code_dir.mkdir(parents=True, exist_ok=True)
            demo_file = code_dir / "App.py"
            demo_file.write_text("# PY-1 marker\n", encoding="utf-8")

            args = research.parse_args(
                [
                    "--ticket",
                    "PY-1",
                    "--auto",
                    "--keywords",
                    "py",
                    "--limit",
                    "5",
                ]
            )

            stdout = io.StringIO()
            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with contextlib.redirect_stdout(stdout):
                    research.run(args)
            finally:
                os.chdir(old_cwd)

            self.assertIn("rlm worklist saved", stdout.getvalue())
            worklist_path = project_root / "reports" / "research" / "PY-1-rlm.worklist.pack.json"
            self.assertTrue(worklist_path.exists())
            payload = json.loads(worklist_path.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"pending", "ready"})

    def test_research_command_warns_on_zero_matches(self):
        with tempfile.TemporaryDirectory(prefix="aidd-research-zero-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )
            config_path = project_root / "config" / "conventions.json"
            config_payload = json.loads(config_path.read_text(encoding="utf-8"))
            config_payload["researcher"]["defaults"]["paths"] = []
            config_payload["researcher"]["defaults"]["docs"] = []
            config_payload["researcher"]["defaults"]["keywords"] = []
            config_payload["researcher"]["tags"] = {}
            config_payload["researcher"]["features"] = {}
            config_path.write_text(json.dumps(config_payload, indent=2), encoding="utf-8")

            args = research.parse_args(
                [
                    "--ticket",
                    "ZERO-1",
                    "--auto",
                    "--keywords",
                    "zero",
                    "--limit",
                    "5",
                ]
            )

            stderr = io.StringIO()
            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with contextlib.redirect_stderr(stderr):
                    research.run(args)
            finally:
                os.chdir(old_cwd)

            self.assertIn("shared RLM API owner", stderr.getvalue())
            targets_path = project_root / "reports" / "research" / "ZERO-1-rlm-targets.json"
            self.assertTrue(targets_path.exists())



if __name__ == "__main__":
    unittest.main()
