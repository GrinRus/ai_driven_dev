import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import cli_cmd, cli_env


REPO_ROOT = Path(__file__).resolve().parents[2]
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


class ResearchCommandTest(unittest.TestCase):
    def test_research_command_materializes_summary(self):
        with tempfile.TemporaryDirectory(prefix="aidd-research-") as tmpdir:
            project_root = Path(tmpdir) / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init", "--target", str(Path(tmpdir))),
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
                    "--target",
                    str(project_root),
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
                cli_cmd("init", "--target", str(workspace)),
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
                    "--target",
                    str(project_root),
                    "--ticket",
                    "WORK-1",
                    "--auto",
                    "--call-graph",
                    "--limit",
                    "5",
                ]
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                research.run(args)

            output = stdout.getvalue()
            self.assertIn("base=workspace", output, "CLI should log workspace base when scanning from parent")

            context_path = project_root / "reports" / "research" / "WORK-1-context.json"
            self.assertTrue(context_path.exists(), "research context JSON should be generated")
            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(payload.get("matches") or []), 1, "workspace code should be indexed")
            self.assertGreaterEqual(len(payload.get("call_graph") or []), 1, "call graph should include edges")
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
                cli_cmd("init", "--target", str(workspace)),
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
                    "--target",
                    str(project_root),
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
            with contextlib.redirect_stdout(stdout):
                research.run(args)

            context_path = project_root / "reports" / "research" / "FOO-7-context.json"
            self.assertTrue(context_path.exists(), "research context JSON should be generated for parent paths")
            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertTrue(any(p.get("path", "").startswith("foo") for p in payload.get("paths") or []))
            self.assertGreaterEqual(len(payload.get("matches") or []), 1, "manual parent path should be scanned")


if __name__ == "__main__":
    unittest.main()
