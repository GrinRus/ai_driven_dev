import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import ensure_project_root, write_active_feature

from tools import rlm_finalize


class RlmFinalizeTests(unittest.TestCase):
    def test_finalize_refreshes_worklist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-finalize-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-FINALIZE"
            write_active_feature(project_root, ticket)

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                json.dumps(
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
                        "type_refs": [],
                        "key_calls": [],
                        "framework_roles": [],
                        "test_hooks": [],
                        "risks": [],
                        "verification": "passed",
                        "missing_tokens": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with (
                    patch.object(rlm_finalize.rlm_verify, "main") as verify_mock,
                    patch.object(rlm_finalize.rlm_links_build, "main") as links_mock,
                    patch.object(rlm_finalize.rlm_jsonl_compact, "main") as compact_mock,
                    patch.object(rlm_finalize.rlm_nodes_build, "main") as nodes_mock,
                    patch.object(rlm_finalize.reports_pack, "main") as pack_mock,
                ):
                    rlm_finalize.main(["--ticket", ticket])
                    verify_mock.assert_called()
                    links_mock.assert_called()
                    compact_mock.assert_called()
                    nodes_mock.assert_called_with(["--ticket", ticket, "--refresh-worklist"])
                    pack_mock.assert_called()
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
