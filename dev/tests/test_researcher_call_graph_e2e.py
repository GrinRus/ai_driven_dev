import sys
import tempfile
import unittest
from pathlib import Path

try:  # optional dependency
    import tree_sitter_language_pack  # noqa: F401
except Exception:
    TREE_SITTER_AVAILABLE = False
else:
    TREE_SITTER_AVAILABLE = True

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tools.researcher_context import ResearcherContextBuilder


@unittest.skipUnless(TREE_SITTER_AVAILABLE, "tree-sitter not installed")
class ResearcherCallGraphE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="callgraph-e2e-")
        self.root = Path(self._tmp.name)
        (self.root / "src" / "main" / "java" / "demo").mkdir(parents=True, exist_ok=True)
        (self.root / "src" / "main" / "kotlin" / "demo").mkdir(parents=True, exist_ok=True)
        (self.root / "src" / "main" / "java" / "demo" / "App.java").write_text(
            "package demo;\n"
            "public class App {\n"
            "  void callee() {}\n"
            "  void caller() { callee(); }\n"
            "}\n",
            encoding="utf-8",
        )
        (self.root / "src" / "main" / "kotlin" / "demo" / "App.kt").write_text(
            "package demo\n\n"
            "class AppKt {\n"
            "  fun callee() {}\n"
            "  fun caller() { callee() }\n"
            "}\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:  # noqa: D401
        self._tmp.cleanup()

    def test_call_graph_contains_edges_with_tree_sitter(self) -> None:
        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-ticket", slug_hint="demo-ticket")
        _, _, roots = builder.describe_targets(scope)
        graph = builder.collect_call_graph(
            scope,
            roots=roots,
            languages=["java", "kt"],
            engine_name="ts",
        )
        self.assertEqual(graph.get("engine"), "tree-sitter")
        self.assertFalse(graph.get("warning"))
        edges = graph.get("edges") or []
        self.assertGreaterEqual(len(edges), 2, "call graph should contain edges for java and kotlin")
        langs = {edge.get("language") for edge in edges}
        self.assertTrue({"java", "kotlin"} & langs)
        self.assertTrue(any(edge.get("caller") and "demo" in edge.get("caller", "") for edge in edges))
        # imports may be empty for minimal fixtures; ensure no warnings when engine present
        self.assertIsInstance(graph.get("imports"), list)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
