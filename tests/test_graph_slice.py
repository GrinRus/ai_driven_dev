import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature, write_json

from tools import graph_slice


class GraphSliceTests(unittest.TestCase):
    def test_graph_slice_creates_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="graph-slice-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "DEMO-1"
            write_active_feature(project_root, ticket)
            edges_path = project_root / "reports" / "research" / f"{ticket}-call-graph.edges.jsonl"
            edges_path.parent.mkdir(parents=True, exist_ok=True)
            edges = [
                {
                    "schema": "aidd.call_graph_edge.v1",
                    "caller": "demo.Service",
                    "callee": "run",
                    "caller_file": "src/main/kotlin/App.kt",
                    "caller_line": 12,
                    "callee_file": "src/main/kotlin/App.kt",
                    "callee_line": 12,
                    "lang": "kotlin",
                    "type": "call",
                },
                {
                    "schema": "aidd.call_graph_edge.v1",
                    "caller": "demo.Service",
                    "callee": "stop",
                    "caller_file": "src/main/kotlin/App.kt",
                    "caller_line": 22,
                    "callee_file": "src/main/kotlin/App.kt",
                    "callee_line": 22,
                    "lang": "kotlin",
                    "type": "call",
                },
            ]
            edges_path.write_text("\n".join(json.dumps(item) for item in edges) + "\n", encoding="utf-8")
            write_json(
                project_root,
                f"reports/research/{ticket}-context.json",
                {
                    "ticket": ticket,
                    "generated_at": "2024-01-01T00:00:00Z",
                    "call_graph_edges_path": f"reports/research/{ticket}-call-graph.edges.jsonl",
                },
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                graph_slice.main(["--ticket", ticket, "--query", "Service", "--max-edges", "1"])
            finally:
                os.chdir(old_cwd)

            context_dir = project_root / "reports" / "context"
            packs = list(context_dir.glob(f"{ticket}-graph-slice-*.pack.yaml"))
            self.assertTrue(packs)
            latest = context_dir / f"{ticket}-graph-slice.latest.pack.yaml"
            self.assertTrue(latest.exists())
            payload = json.loads(latest.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("ticket"), ticket)
            self.assertLessEqual(len(payload.get("edges") or []), 1)

    def test_graph_slice_filters_by_lang_and_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="graph-slice-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "DEMO-2"
            write_active_feature(project_root, ticket)
            edges_path = project_root / "reports" / "research" / f"{ticket}-call-graph.edges.jsonl"
            edges_path.parent.mkdir(parents=True, exist_ok=True)
            edges = [
                {
                    "schema": "aidd.call_graph_edge.v1",
                    "caller": "demo.Service",
                    "callee": "run",
                    "caller_file": "src/main/kotlin/App.kt",
                    "caller_line": 12,
                    "callee_file": "src/main/kotlin/App.kt",
                    "callee_line": 12,
                    "lang": "kotlin",
                    "type": "call",
                },
                {
                    "schema": "aidd.call_graph_edge.v1",
                    "caller": "demo.Service",
                    "callee": "run",
                    "caller_file": "src/main/java/App.java",
                    "caller_line": 15,
                    "callee_file": "src/main/java/App.java",
                    "callee_line": 15,
                    "lang": "java",
                    "type": "call",
                },
            ]
            edges_path.write_text("\n".join(json.dumps(item) for item in edges) + "\n", encoding="utf-8")
            write_json(
                project_root,
                f"reports/research/{ticket}-context.json",
                {
                    "ticket": ticket,
                    "generated_at": "2024-01-01T00:00:00Z",
                    "call_graph_edges_path": f"reports/research/{ticket}-call-graph.edges.jsonl",
                },
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                graph_slice.main(
                    [
                        "--ticket",
                        ticket,
                        "--query",
                        "Service",
                        "--lang",
                        "java",
                        "--paths",
                        "src/main/java",
                    ]
                )
            finally:
                os.chdir(old_cwd)

            latest = project_root / "reports" / "context" / f"{ticket}-graph-slice.latest.pack.yaml"
            payload = json.loads(latest.read_text(encoding="utf-8"))
            edges_out = payload.get("edges") or []
            self.assertEqual(len(edges_out), 1)
            self.assertEqual(edges_out[0].get("lang"), "java")
            self.assertIn("src/main/java", edges_out[0].get("caller_file", ""))


if __name__ == "__main__":
    unittest.main()
