import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root

from aidd_runtime import rlm_verify


class RlmVerifyTests(unittest.TestCase):
    def _write_nodes(self, path: Path, nodes: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(item) for item in nodes) + "\n", encoding="utf-8")

    def test_verify_fails_when_type_refs_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-verify-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            src_path = workspace / "src" / "a.py"
            src_path.parent.mkdir(parents=True, exist_ok=True)
            src_path.write_text("class Present:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / "RLM-VERIFY-rlm.nodes.jsonl"
            self._write_nodes(
                nodes_path,
                [
                    {
                        "schema": "aidd.rlm_node.v2",
                        "schema_version": "v2",
                        "node_kind": "file",
                        "file_id": "file-a",
                        "id": "file-a",
                        "path": "src/a.py",
                        "rev_sha": "rev-a",
                        "lang": "py",
                        "prompt_version": "v1",
                        "summary": "",
                        "public_symbols": [],
                        "type_refs": ["MissingType"],
                        "key_calls": [],
                        "framework_roles": [],
                        "test_hooks": [],
                        "risks": [],
                        "verification": "pending",
                        "missing_tokens": [],
                    }
                ],
            )

            rlm_verify.verify_nodes(
                project_root,
                workspace,
                nodes_path,
                max_file_bytes=0,
            )

            payload = json.loads(nodes_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload.get("verification"), "failed")
            self.assertIn("MissingType", payload.get("missing_tokens") or [])

    def test_verify_passes_when_type_refs_present(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-verify-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            src_path = workspace / "src" / "a.py"
            src_path.parent.mkdir(parents=True, exist_ok=True)
            src_path.write_text("class Present:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / "RLM-VERIFY2-rlm.nodes.jsonl"
            self._write_nodes(
                nodes_path,
                [
                    {
                        "schema": "aidd.rlm_node.v2",
                        "schema_version": "v2",
                        "node_kind": "file",
                        "file_id": "file-a",
                        "id": "file-a",
                        "path": "src/a.py",
                        "rev_sha": "rev-a",
                        "lang": "py",
                        "prompt_version": "v1",
                        "summary": "",
                        "public_symbols": [],
                        "type_refs": ["Present"],
                        "key_calls": [],
                        "framework_roles": [],
                        "test_hooks": [],
                        "risks": [],
                        "verification": "pending",
                        "missing_tokens": [],
                    }
                ],
            )

            rlm_verify.verify_nodes(
                project_root,
                workspace,
                nodes_path,
                max_file_bytes=0,
            )

            payload = json.loads(nodes_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload.get("verification"), "passed")
            self.assertEqual(payload.get("missing_tokens"), [])


if __name__ == "__main__":
    unittest.main()
