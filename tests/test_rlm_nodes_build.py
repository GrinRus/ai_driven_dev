import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature

from tools import rlm_nodes_build
from tools import rlm_config


class RlmNodesBuildTests(unittest.TestCase):
    def test_worklist_marks_missing_and_outdated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-worklist-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-3"
            write_active_feature(project_root, ticket)

            manifest_path = project_root / "reports" / "research" / f"{ticket}-rlm-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest = {
                "ticket": ticket,
                "files": [
                    {
                        "file_id": rlm_config.file_id_for_path(Path("src/a.py")),
                        "path": "src/a.py",
                        "rev_sha": "sha-a",
                        "lang": "py",
                        "size": 1,
                        "prompt_version": "v1",
                    },
                    {
                        "file_id": rlm_config.file_id_for_path(Path("src/b.py")),
                        "path": "src/b.py",
                        "rev_sha": "sha-b",
                        "lang": "py",
                        "size": 1,
                        "prompt_version": "v1",
                    },
                ],
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                json.dumps(
                    {
                        "node_kind": "file",
                        "file_id": rlm_config.file_id_for_path(Path("src/a.py")),
                        "path": "src/a.py",
                        "rev_sha": "sha-a",
                        "prompt_version": "v1",
                        "verification": "passed",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            pack = rlm_nodes_build.build_worklist_pack(
                project_root,
                ticket,
                manifest_path=manifest_path,
                nodes_path=nodes_path,
            )
            entries = pack.get("entries") or []
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["path"], "src/b.py")
            self.assertEqual(entries[0]["reason"], "missing")

    def test_build_dir_nodes_from_files(self) -> None:
        nodes = [
            {
                "node_kind": "file",
                "file_id": "file-a",
                "id": "file-a",
                "path": "src/app.py",
                "summary": "App entry",
                "public_symbols": ["App"],
                "framework_roles": ["web"],
            },
            {
                "node_kind": "file",
                "file_id": "file-b",
                "id": "file-b",
                "path": "src/lib/util.py",
                "summary": "Helpers",
                "public_symbols": ["Util"],
                "framework_roles": [],
            },
        ]
        dir_nodes = rlm_nodes_build.build_dir_nodes(nodes, max_children=10, max_chars=200)
        dir_paths = {node.get("path") for node in dir_nodes}
        self.assertIn("src", dir_paths)
        self.assertIn("src/lib", dir_paths)


if __name__ == "__main__":
    unittest.main()
