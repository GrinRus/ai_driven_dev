import json
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tests.helpers import ensure_project_root, write_active_feature

from aidd_runtime import rlm_finalize


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

    def test_finalize_bootstrap_if_missing_emits_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-finalize-bootstrap-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-FINALIZE-BOOTSTRAP"
            write_active_feature(project_root, ticket)

            manifest_path = project_root / "reports" / "research" / f"{ticket}-rlm-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "ticket": ticket,
                        "files": [
                            {
                                "file_id": "file-a",
                                "path": "src/a.py",
                                "rev_sha": "rev-a",
                                "lang": "py",
                                "size": 1,
                                "prompt_version": "v1",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"

            def _nodes_side_effect(argv: list[str]) -> int:
                if "--bootstrap" in argv:
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
                return 0

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with (
                    patch.object(rlm_finalize.rlm_verify, "main") as verify_mock,
                    patch.object(rlm_finalize.rlm_links_build, "main") as links_mock,
                    patch.object(rlm_finalize.rlm_jsonl_compact, "main") as compact_mock,
                    patch.object(rlm_finalize.rlm_nodes_build, "main", side_effect=_nodes_side_effect) as nodes_mock,
                    patch.object(rlm_finalize.reports_pack, "main") as pack_mock,
                ):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        code = rlm_finalize.main(
                            ["--ticket", ticket, "--bootstrap-if-missing", "--emit-json"]
                        )
            finally:
                os.chdir(old_cwd)

            self.assertEqual(code, 0)
            verify_mock.assert_called()
            links_mock.assert_called()
            compact_mock.assert_called()
            pack_mock.assert_called()
            calls = [list(call.args[0]) for call in nodes_mock.call_args_list]
            self.assertIn(["--ticket", ticket, "--bootstrap"], calls)
            self.assertIn(["--ticket", ticket, "--refresh-worklist"], calls)
            payload = json.loads(stdout.getvalue().strip().splitlines()[-1])
            self.assertEqual(payload.get("status"), "done")
            self.assertEqual(payload.get("bootstrap_attempted"), True)
            self.assertEqual(payload.get("finalize_attempted"), True)

    def test_finalize_emit_json_includes_links_empty_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-finalize-empty-links-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-FINALIZE-EMPTY-LINKS"
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
            (project_root / "reports" / "research").mkdir(parents=True, exist_ok=True)
            (project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json").write_text(
                json.dumps({"links_total": 0, "empty_reason": "no_matches"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with (
                    patch.object(rlm_finalize.rlm_verify, "main"),
                    patch.object(rlm_finalize.rlm_links_build, "main"),
                    patch.object(rlm_finalize.rlm_jsonl_compact, "main"),
                    patch.object(rlm_finalize.rlm_nodes_build, "main"),
                    patch.object(rlm_finalize.reports_pack, "main"),
                ):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        code = rlm_finalize.main(["--ticket", ticket, "--emit-json"])
            finally:
                os.chdir(old_cwd)

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue().strip().splitlines()[-1])
            self.assertEqual(payload.get("status"), "done")
            self.assertEqual(payload.get("reason_code"), "rlm_links_empty_warn")
            self.assertEqual(payload.get("empty_reason"), "no_matches")
            self.assertIn("rlm_links_build.py --ticket", str(payload.get("next_action") or ""))


if __name__ == "__main__":
    unittest.main()
