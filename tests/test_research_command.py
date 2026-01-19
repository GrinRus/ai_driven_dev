import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import REPO_ROOT, cli_cmd, cli_env


SRC_ROOT = REPO_ROOT

if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tools import research


class FakeEngine:
    name = "fake"
    supported_languages = {"kt", "kts", "java"}
    supported_extensions = {".kt", ".kts", ".java"}

    def build(self, files):
        return {
            "edges": [
                {"caller": "WorkspaceCaller", "callee": "WorkspaceCallee", "file": str(files[0]), "line": 1, "language": "kotlin"}
            ],
            "imports": [],
        }


class FakeMultiEdgeEngine:
    name = "fake"
    supported_languages = {"kt", "kts", "java"}
    supported_extensions = {".kt", ".kts", ".java"}

    def build(self, files):
        return {
            "edges": [
                {"caller": "MatchCaller", "callee": "Hit", "file": str(files[0]), "line": 1, "language": "kotlin"},
                {"caller": "OtherCaller", "callee": "Miss", "file": str(files[0]), "line": 2, "language": "kotlin"},
            ],
            "imports": [],
        }


class MissingEngine:
    name = "tree-sitter"
    supported_languages = {"kt", "kts", "java"}
    supported_extensions = {".kt", ".kts", ".java"}

    def build(self, files):
        return {"edges": [], "imports": [], "warning": "tree-sitter not available: missing parser"}


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

    @mock.patch("tools.researcher_context._load_callgraph_engine")
    def test_research_command_uses_workspace_root_and_call_graph(self, mock_engine):
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

            mock_engine.return_value = FakeEngine()
            args = research.parse_args(
                [
                    "--ticket",
                    "WORK-1",
                    "--auto",
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
            self.assertIn("base=workspace", output, "CLI should log workspace base when scanning from parent")

            context_path = project_root / "reports" / "research" / "WORK-1-context.json"
            self.assertTrue(context_path.exists(), "research context JSON should be generated")
            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(payload.get("matches") or []), 1, "workspace code should be indexed")
            self.assertGreaterEqual(len(payload.get("call_graph") or []), 1, "call graph should include edges")
            self.assertTrue(payload.get("deep_mode"), "auto JVM scan should enable deep mode")
            self.assertIn("call_graph_filter", payload)
            self.assertIn("call_graph_limit", payload)
            self.assertIn("call_graph_warning", payload)
            full_graph_rel = payload.get("call_graph_full_path")
            self.assertTrue(full_graph_rel, "call graph full path should be recorded")
            full_graph_path = project_root / full_graph_rel
            self.assertTrue(full_graph_path.exists(), "call graph full file should be saved")
            full_graph = json.loads(full_graph_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(full_graph.get("edges") or []), 1)
            self.assertTrue(
                any(match.get("file", "").startswith("src/") for match in payload.get("matches") or []),
                "matches should be reported relative to workspace root",
            )

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

            context_path = project_root / "reports" / "research" / "FOO-7-context.json"
            self.assertTrue(context_path.exists(), "research context JSON should be generated for parent paths")
            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertTrue(any(p.get("path", "").startswith("foo") for p in payload.get("paths") or []))
            self.assertGreaterEqual(len(payload.get("matches") or []), 1, "manual parent path should be scanned")

    @mock.patch("tools.researcher_context._load_callgraph_engine")
    def test_research_command_auto_fast_scan_non_jvm(self, mock_engine):
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

            self.assertIn("auto profile: fast-scan", stdout.getvalue())
            mock_engine.assert_not_called()

            context_path = project_root / "reports" / "research" / "PY-1-context.json"
            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertFalse(payload.get("deep_mode"), "non-JVM auto scan should remain fast")
            self.assertEqual(payload.get("call_graph"), [])

    @mock.patch("tools.researcher_context._load_callgraph_engine")
    def test_research_command_warns_on_missing_tree_sitter(self, mock_engine):
        with tempfile.TemporaryDirectory(prefix="aidd-research-missing-ts-") as tmpdir:
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
            demo_file = code_dir / "MissingTs.kt"
            demo_file.write_text(
                "package demo\n\nfun missingTs() { /* TS-1 */ }\n", encoding="utf-8"
            )

            mock_engine.return_value = MissingEngine()
            args = research.parse_args(
                [
                    "--ticket",
                    "TS-1",
                    "--auto",
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

            err_text = stderr.getvalue()
            self.assertIn("INSTALL_HINT", err_text)
            self.assertIn("tree-sitter not available", err_text)

            context_path = project_root / "reports" / "research" / "TS-1-context.json"
            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertIn("tree-sitter", payload.get("call_graph_warning", ""))

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

            self.assertIn("0 matches", stderr.getvalue())
            self.assertIn("сузить paths/keywords", stderr.getvalue())
            context_path = project_root / "reports" / "research" / "ZERO-1-context.json"
            self.assertTrue(context_path.exists())

    @mock.patch("tools.researcher_context._load_callgraph_engine")
    def test_research_command_graph_mode_full(self, mock_engine):
        with tempfile.TemporaryDirectory(prefix="aidd-research-graph-mode-") as tmpdir:
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
            demo_file = code_dir / "GraphMode.kt"
            demo_file.write_text("package demo\n\nfun graphMode() { /* GRAPH-1 */ }\n", encoding="utf-8")

            mock_engine.return_value = FakeMultiEdgeEngine()
            args = research.parse_args(
                [
                    "--ticket",
                    "GRAPH-1",
                    "--call-graph",
                    "--graph-mode",
                    "full",
                    "--graph-filter",
                    "Caller",
                    "--graph-limit",
                    "1",
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

            context_path = project_root / "reports" / "research" / "GRAPH-1-context.json"
            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload.get("call_graph") or []), 2, "full graph mode should keep all edges")
            self.assertNotIn("trimmed", payload.get("call_graph_warning", ""))


if __name__ == "__main__":
    unittest.main()
