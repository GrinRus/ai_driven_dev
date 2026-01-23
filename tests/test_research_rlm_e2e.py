import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature, write_json, write_tasklist_ready

from tools import rlm_links_build, rlm_manifest, rlm_nodes_build, rlm_slice, rlm_targets, reports_pack, tasks_derive
from tools.rlm_config import load_rlm_settings


class RlmPipelineE2ETests(unittest.TestCase):
    def test_rlm_pipeline_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-e2e-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-26"
            write_active_feature(project_root, ticket)

            src_dir = workspace / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "a.py").write_text("from b import Foo\nFoo()\n", encoding="utf-8")
            (src_dir / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

            write_json(
                project_root,
                f"reports/research/{ticket}-targets.json",
                {"paths": ["src"], "paths_discovered": [], "keywords": [], "docs": []},
            )
            settings = load_rlm_settings(project_root)
            targets_payload = rlm_targets.build_targets(project_root, ticket, settings=settings)
            targets_path = project_root / "reports" / "research" / f"{ticket}-rlm-targets.json"
            targets_path.parent.mkdir(parents=True, exist_ok=True)
            targets_path.write_text(json.dumps(targets_payload, indent=2), encoding="utf-8")

            manifest_payload = rlm_manifest.build_manifest(
                project_root,
                ticket,
                settings=settings,
                targets_path=targets_path,
            )
            manifest_path = project_root / "reports" / "research" / f"{ticket}-rlm-manifest.json"
            manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

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
                    "rev_sha": "rev-a",
                    "lang": "py",
                    "prompt_version": "v1",
                    "summary": "Calls Foo for checkout flow.",
                    "public_symbols": [],
                    "key_calls": ["Foo"],
                    "framework_roles": ["service"],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
                {
                    "schema": "aidd.rlm_node.v1",
                    "schema_version": "v1",
                    "node_kind": "file",
                    "file_id": "file-b",
                    "id": "file-b",
                    "path": "src/b.py",
                    "rev_sha": "rev-b",
                    "lang": "py",
                    "prompt_version": "v1",
                    "summary": "Defines Foo.",
                    "public_symbols": ["Foo"],
                    "key_calls": [],
                    "framework_roles": ["repo"],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
            ]
            nodes_path.write_text("\n".join(json.dumps(item) for item in nodes) + "\n", encoding="utf-8")

            worklist_pack = rlm_nodes_build.build_worklist_pack(
                project_root,
                ticket,
                manifest_path=manifest_path,
                nodes_path=nodes_path,
            )
            worklist_path = project_root / "reports" / "research" / f"{ticket}-rlm.worklist.pack.yaml"
            worklist_path.write_text(json.dumps(worklist_pack, indent=2), encoding="utf-8")

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_links_build.main(["--ticket", ticket])
                reports_pack.write_rlm_pack(
                    nodes_path,
                    project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl",
                    ticket=ticket,
                    slug_hint=ticket,
                    root=project_root,
                )
                rlm_slice.main(["--ticket", ticket, "--query", "Foo"])
                write_tasklist_ready(project_root, ticket)
                tasks_derive.main(["--source", "research", "--ticket", ticket])
            finally:
                os.chdir(old_cwd)

            pack_path = project_root / "reports" / "research" / f"{ticket}-rlm.pack.yaml"
            slice_path = project_root / "reports" / "context" / f"{ticket}-rlm-slice.latest.pack.yaml"
            self.assertTrue(pack_path.exists(), "RLM pack should be created")
            self.assertTrue(slice_path.exists(), "RLM slice should be created")

            tasklist_path = project_root / "docs" / "tasklist" / f"{ticket}.md"
            tasklist_text = tasklist_path.read_text(encoding="utf-8")
            self.assertIn("RLM integration", tasklist_text)


if __name__ == "__main__":
    unittest.main()
