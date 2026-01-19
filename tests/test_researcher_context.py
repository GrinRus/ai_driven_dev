import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tools.researcher_context import (
    ResearcherContextBuilder,
    _columnar_call_graph,
)

from .helpers import TEMPLATES_ROOT, cli_cmd, cli_env, write_file


class MissingEngine:
    name = "tree-sitter"
    supported_languages = {"kt", "kts", "java"}
    supported_extensions = {".kt", ".kts", ".java"}

    def build(self, files):
        return {"edges": [], "imports": [], "warning": "tree-sitter not available: missing parser"}


class ResearcherContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="researcher-context-")
        self.workspace = Path(self._tmp.name)
        self.root = self.workspace / "aidd"
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "research").mkdir(parents=True, exist_ok=True)
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        template_src = (TEMPLATES_ROOT / "docs" / "prd" / "template.md").read_text(encoding="utf-8")
        write_file(self.root, "docs/prd/template.md", template_src)
        (self.root / "src" / "main" / "kotlin").mkdir(parents=True, exist_ok=True)

        config_payload = {
            "commit": {},
            "branch": {},
            "researcher": {
                "defaults": {
                    "paths": ["src/main"],
                    "docs": ["docs/research"],
                    "keywords": ["checkout"],
                },
                "tags": {
                    "checkout": {
                        "paths": ["src/main/kotlin"],
                        "docs": ["docs/research/demo-checkout.md"],
                        "keywords": ["order", "payment"],
                    }
                },
                "features": {
                    "demo-checkout": ["checkout"]
                },
            },
        }
        (self.root / "config" / "conventions.json").write_text(
            json.dumps(config_payload, indent=2),
            encoding="utf-8",
        )

        # Sample code file so the context search finds matches.
        sample_code = (
            "package demo\n\n" "class CheckoutFeature { fun run() = \"checkout flow\" }\n"
        )
        write_file(self.root, "src/main/kotlin/CheckoutFeature.kt", sample_code)

        # Existing research doc stub.
        write_file(
            self.root,
            "docs/research/demo-checkout.md",
            "# Research Summary\n\nStatus: pending\n",
        )


    def tearDown(self) -> None:  # noqa: D401
        self._tmp.cleanup()

    def test_builder_creates_targets_and_context(self) -> None:
        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-checkout", slug_hint="demo-checkout")
        self.assertEqual(scope.ticket, "demo-checkout")
        self.assertEqual(scope.slug_hint, "demo-checkout")
        self.assertIn("src/main/kotlin", scope.paths)
        self.assertIn("docs/research/demo-checkout.md", scope.docs)

        targets_path = builder.write_targets(scope)
        self.assertTrue(targets_path.exists())

        context = builder.collect_context(scope, limit=5)
        context_path = builder.write_context(scope, context)

        payload = json.loads(context_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["ticket"], "demo-checkout")
        self.assertGreaterEqual(len(payload["matches"]), 1)
        self.assertIn("profile", payload)
        self.assertIn("manual_notes", payload)

    def test_builder_handles_slug_without_tags(self) -> None:
        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-untagged", slug_hint="demo-untagged")
        self.assertEqual(scope.ticket, "demo-untagged")
        self.assertEqual(scope.slug_hint, "demo-untagged")
        self.assertEqual(scope.tags, [])
        self.assertIn("src/main", scope.paths)
        self.assertIn("docs/research", scope.docs)

    def test_columnar_call_graph_format(self) -> None:
        edges = [
            {
                "caller": "demo.Service",
                "callee": "run",
                "file": "src/main/kotlin/App.kt",
                "line": 12,
                "language": "kotlin",
                "caller_raw": "Service",
            }
        ]
        payload = _columnar_call_graph(edges, [{"file": "src/main/kotlin/App.kt", "imports": ["demo"]}])
        self.assertEqual(payload.get("cols"), ["caller", "callee", "file", "line", "language", "caller_raw"])
        self.assertEqual(payload.get("rows")[0][0], "demo.Service")

    def test_builder_merges_multiple_tags(self) -> None:
        config_path = self.root / "config" / "conventions.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["researcher"]["tags"]["payments"] = {
            "paths": ["src/payments"],
            "docs": ["docs/research/payments.md"],
            "keywords": ["payments"],
        }
        config["researcher"]["features"]["demo-checkout"] = ["checkout", "payments"]
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        (self.root / "src" / "payments").mkdir(parents=True, exist_ok=True)
        write_file(
            self.root,
            "docs/research/payments.md",
            "# Payments\n\nStatus: pending\n",
        )

        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-checkout", slug_hint="demo-checkout")
        self.assertIn("checkout", scope.tags)
        self.assertIn("payments", scope.tags)
        self.assertIn("src/payments", scope.paths)
        self.assertIn("docs/research/payments.md", scope.docs)
        self.assertIn("payments", scope.keywords)

    def test_builder_captures_manual_notes_and_profile(self) -> None:
        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-checkout", slug_hint="demo-checkout")
        scope = builder.extend_scope(scope, extra_notes=["Свободное наблюдение"])
        context = builder.collect_context(scope, limit=5)
        self.assertIn("Свободное наблюдение", context["manual_notes"])
        profile = context["profile"]
        self.assertIn("recommendations", profile)
        self.assertIn("is_new_project", profile)

    def test_deep_mode_collects_code_index_and_reuse(self) -> None:
        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-checkout", slug_hint="demo-checkout")
        _, _, roots = builder.describe_targets(scope)
        code_index, reuse_candidates = builder.collect_deep_context(
            scope,
            roots=roots,
            keywords=scope.keywords,
            languages=["kt", "py"],
            limit=5,
        )
        self.assertGreaterEqual(len(code_index), 1, "code_index should contain parsed symbols")
        self.assertIn("path", code_index[0])
        self.assertIn("symbols", code_index[0])
        self.assertGreaterEqual(len(reuse_candidates), 1, "reuse candidates should be suggested")
        self.assertIn("score", reuse_candidates[0])

    @mock.patch("tools.researcher_context._load_callgraph_engine")
    def test_call_graph_warns_when_tree_sitter_missing(self, mock_engine) -> None:
        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-checkout", slug_hint="demo-checkout")
        _, _, roots = builder.describe_targets(scope)
        mock_engine.return_value = MissingEngine()

        graph = builder.collect_call_graph(
            scope,
            roots=roots,
            languages=["kt"],
            engine_name="ts",
        )

        self.assertIn("tree-sitter", graph.get("warning", ""))
        self.assertIn("edges_full", graph)

    def test_set_active_feature_refreshes_targets(self) -> None:
        env = cli_env()
        result = subprocess.run(
            cli_cmd("set-active-feature", "demo-checkout"),
            text=True,
            capture_output=True,
            cwd=self.workspace,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        ticket_file = self.root / "docs" / ".active_ticket"
        self.assertEqual(ticket_file.read_text(encoding="utf-8"), "demo-checkout")
        slug_file = self.root / "docs" / ".active_feature"
        self.assertEqual(slug_file.read_text(encoding="utf-8"), "demo-checkout")

        targets_path = self.root / "reports" / "research" / "demo-checkout-targets.json"
        self.assertTrue(targets_path.exists(), "Researcher targets should be generated")
        targets = json.loads(targets_path.read_text(encoding="utf-8"))
        self.assertIn("src/main/kotlin", targets["paths"])

        prd_path = self.root / "docs" / "prd" / "demo-checkout.prd.md"
        self.assertTrue(prd_path.exists(), "PRD scaffold should be created automatically")
        prd_body = prd_path.read_text(encoding="utf-8")
        self.assertIn("Status: draft", prd_body)
        self.assertIn("docs/research/demo-checkout.md", prd_body)

        index_path = self.root / "docs" / "index" / "demo-checkout.yaml"
        self.assertTrue(index_path.exists(), "Index should be generated on set-active-feature")
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(index_payload.get("ticket"), "demo-checkout")

    def test_slug_hint_persists_without_repeating_argument(self) -> None:
        env = cli_env()
        first = subprocess.run(
            cli_cmd(
                "set-active-feature",
                "--slug-note",
                "checkout-lite",
                "demo-checkout",
            ),
            text=True,
            capture_output=True,
            cwd=self.workspace,
            env=env,
            check=True,
        )
        self.assertEqual(first.returncode, 0, msg=first.stderr)

        second = subprocess.run(
            cli_cmd("set-active-feature", "demo-checkout"),
            text=True,
            capture_output=True,
            cwd=self.workspace,
            env=env,
            check=True,
        )
        self.assertEqual(second.returncode, 0, msg=second.stderr)

        slug_file = self.root / "docs" / ".active_feature"
        self.assertEqual(slug_file.read_text(encoding="utf-8"), "checkout-lite")

        targets_path = self.root / "reports" / "research" / "demo-checkout-targets.json"
        targets = json.loads(targets_path.read_text(encoding="utf-8"))
        self.assertEqual(targets["slug"], "checkout-lite")

    def test_workspace_relative_paths_find_code_outside_aidd(self) -> None:
        workspace = Path(self._tmp.name) / "workspace2"
        project_root = workspace / "aidd"
        project_root.mkdir(parents=True, exist_ok=True)
        config = {
            "researcher": {
                "defaults": {
                    "paths": ["src/main"],
                    "docs": ["docs/research"],
                    "workspace_relative": True,
                }
            }
        }
        (project_root / "config").mkdir(parents=True, exist_ok=True)
        (project_root / "config" / "conventions.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        code_path = workspace / "src" / "main" / "kotlin"
        code_path.mkdir(parents=True, exist_ok=True)
        demo_file = code_path / "WorkspaceDemo.kt"
        demo_file.write_text("package demo\n// workspace-ticket demo\n", encoding="utf-8")

        builder = ResearcherContextBuilder(project_root, config_path=project_root / "config" / "conventions.json")
        scope = builder.build_scope("workspace-ticket", slug_hint="workspace-ticket")
        self.assertIn("src/main", scope.paths)
        context = builder.collect_context(scope, limit=5)
        self.assertGreaterEqual(len(context["matches"]), 1, "workspace-relative paths should find code outside aidd")
