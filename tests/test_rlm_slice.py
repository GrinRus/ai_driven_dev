import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature

from tools import rlm_slice


class RlmSliceTests(unittest.TestCase):
    def test_rlm_slice_creates_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-slice-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-5"
            write_active_feature(project_root, ticket)

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes = [
                {
                    "schema": "aidd.rlm_node.v1",
                    "schema_version": "v1",
                    "node_kind": "file",
                    "file_id": "file-a",
                    "id": "file-a",
                    "path": "src/a.py",
                    "summary": "Foo entrypoint",
                    "lang": "py",
                }
            ]
            nodes_path.write_text("\n".join(json.dumps(item) for item in nodes) + "\n", encoding="utf-8")

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            links = [
                {
                    "schema": "aidd.rlm_link.v1",
                    "schema_version": "v1",
                    "link_id": "link-1",
                    "src_file_id": "file-a",
                    "dst_file_id": "file-a",
                    "type": "calls",
                    "evidence_ref": {
                        "path": "src/a.py",
                        "line_start": 1,
                        "line_end": 1,
                        "extractor": "regex",
                        "match_hash": "hash",
                    },
                    "unverified": False,
                }
            ]
            links_path.write_text("\n".join(json.dumps(item) for item in links) + "\n", encoding="utf-8")

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_slice.main(["--ticket", ticket, "--query", "Foo"])
            finally:
                os.chdir(old_cwd)

            latest = project_root / "reports" / "context" / f"{ticket}-rlm-slice.latest.pack.yaml"
            self.assertTrue(latest.exists())
            payload = json.loads(latest.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("ticket"), ticket)
            self.assertTrue(payload.get("nodes"))


if __name__ == "__main__":
    unittest.main()
