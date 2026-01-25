import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature

from tools import rlm_jsonl_compact


class RlmJsonlCompactTests(unittest.TestCase):
    def test_compact_dedupes_nodes_and_links(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-compact-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-6"
            write_active_feature(project_root, ticket)

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes = [
                {"id": "file-a", "node_kind": "file", "path": "src/a.py"},
                {"id": "file-a", "node_kind": "file", "path": "src/a.py"},
                {"id": "dir-1", "node_kind": "dir", "path": "src"},
            ]
            nodes_path.write_text("\n".join(json.dumps(item) for item in nodes) + "\n", encoding="utf-8")

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            links = [
                {"link_id": "l1", "src_file_id": "file-a", "dst_file_id": "file-b", "type": "calls"},
                {"link_id": "l1", "src_file_id": "file-a", "dst_file_id": "file-b", "type": "calls"},
            ]
            links_path.write_text("\n".join(json.dumps(item) for item in links) + "\n", encoding="utf-8")

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_jsonl_compact.main(["--ticket", ticket])
            finally:
                os.chdir(old_cwd)

            compact_nodes = nodes_path.read_text(encoding="utf-8").splitlines()
            compact_links = links_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(compact_nodes), 2)
            self.assertEqual(len(compact_links), 1)


if __name__ == "__main__":
    unittest.main()
