import sys
import tempfile
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from claude_workflow_cli.tools.researcher_context import ResearcherContextBuilder


class FakeEngine:
    name = "fake"
    supported_languages = {"java", "kt"}
    supported_extensions = {".java", ".kt"}

    def build(self, files):
        return {
            "edges": [
                {"caller": "Caller", "callee": "Callee", "file": str(files[0]), "line": 1, "language": "kotlin"},
                {"caller": "Other", "callee": "OtherCallee", "file": str(files[0]), "line": 2, "language": "kotlin"},
            ],
            "imports": [{"file": str(files[0]), "imports": ["demo.Foo"]}],
        }


class ResearcherCallGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="callgraph-")
        self.root = Path(self._tmp.name)
        (self.root / "src").mkdir(parents=True, exist_ok=True)
        (self.root / "src" / "Main.kt").write_text("package demo\n\nfun caller() { callee() }\n", encoding="utf-8")

    def tearDown(self) -> None:  # noqa: D401
        self._tmp.cleanup()

    def test_collect_call_graph_with_custom_engine(self) -> None:
        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-ticket", slug_hint="demo-ticket")
        _, _, roots = builder.describe_targets(scope)
        graph = builder.collect_call_graph(
            scope,
            roots=roots,
            languages=["kt", "java"],
            engine_name="ts",
            engine=FakeEngine(),
            graph_filter="Caller",
        )
        self.assertEqual(graph.get("engine"), "fake")
        self.assertEqual(len(graph.get("edges") or []), 1)
        self.assertEqual(len(graph.get("imports") or []), 1)

    def test_collect_call_graph_without_engine_returns_warning(self) -> None:
        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-ticket", slug_hint="demo-ticket")
        _, _, roots = builder.describe_targets(scope)
        graph = builder.collect_call_graph(
            scope,
            roots=roots,
            languages=["kt", "java"],
            engine_name="ts",
            engine=None,
        )
        engine_name = graph.get("engine")
        if graph.get("warning"):
            self.assertIn(engine_name, ("ts", "tree-sitter"))
            self.assertEqual(graph.get("edges"), [])
        else:
            # engine доступен (tree-sitter установлен) — должен вернуть имя движка и какой-то результат/пустой список без warn
            self.assertIn(engine_name, ("tree-sitter", "ts"))
            self.assertIn("edges", graph)

    def test_collect_call_graph_trimmed_and_full(self) -> None:
        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-ticket", slug_hint="demo-ticket")
        _, _, roots = builder.describe_targets(scope)
        graph = builder.collect_call_graph(
            scope,
            roots=roots,
            languages=["kt"],
            engine_name="ts",
            engine=FakeEngine(),
            graph_limit=1,
        )
        self.assertEqual(len(graph.get("edges") or []), 1)
        self.assertEqual(len(graph.get("edges_full") or []), 2)
        self.assertTrue(graph.get("warning"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
