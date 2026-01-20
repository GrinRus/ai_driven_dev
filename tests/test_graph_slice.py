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
                    "file": "src/main/kotlin/App.kt",
                    "line": 12,
                    "language": "kotlin",
                },
                {
                    "schema": "aidd.call_graph_edge.v1",
                    "caller": "demo.Service",
                    "callee": "stop",
                    "file": "src/main/kotlin/App.kt",
                    "line": 22,
                    "language": "kotlin",
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


if __name__ == "__main__":
    unittest.main()
