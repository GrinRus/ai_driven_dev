import json
import tempfile
import unittest
from pathlib import Path

from tools import call_graph_views


class CallGraphEdgesSchemaTests(unittest.TestCase):
    def test_edges_jsonl_schema(self) -> None:
        edges = [
            {
                "caller": "demo.Service",
                "callee": "run",
                "caller_file": "src/main/kotlin/App.kt",
                "caller_line": 12,
                "callee_file": "src/main/kotlin/App.kt",
                "callee_line": 12,
                "lang": "kotlin",
                "type": "call",
            }
        ]
        with tempfile.TemporaryDirectory(prefix="call-graph-edges-") as tmpdir:
            output = Path(tmpdir) / "edges.jsonl"
            count, truncated = call_graph_views.write_edges_jsonl(edges, output)
            self.assertEqual(count, 1)
            self.assertFalse(truncated)
            line = output.read_text(encoding="utf-8").splitlines()[0]
            payload = json.loads(line)
            for key in (
                "schema",
                "caller",
                "callee",
                "caller_file",
                "caller_line",
                "callee_file",
                "callee_line",
                "lang",
                "type",
            ):
                self.assertIn(key, payload)
            self.assertEqual(payload["schema"], call_graph_views.EDGE_SCHEMA)


if __name__ == "__main__":
    unittest.main()
