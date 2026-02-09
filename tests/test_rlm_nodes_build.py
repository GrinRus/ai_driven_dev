import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature

from aidd_runtime import rlm_nodes_build
from aidd_runtime import rlm_config


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

    def test_worklist_trims_entries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-worklist-trim-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-TRIM"
            write_active_feature(project_root, ticket)

            config_path = project_root / "config" / "conventions.json"
            config_path.write_text(json.dumps({"rlm": {"worklist_max_entries": 1}}, indent=2), encoding="utf-8")

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

            pack = rlm_nodes_build.build_worklist_pack(
                project_root,
                ticket,
                manifest_path=manifest_path,
                nodes_path=nodes_path,
            )
            entries = pack.get("entries") or []
            stats = pack.get("stats") or {}
            self.assertEqual(len(entries), 1)
            self.assertEqual(stats.get("entries_total"), 2)
            self.assertEqual(stats.get("entries_trimmed"), 1)
            self.assertEqual(stats.get("trim_reason"), "max_entries")

    def test_refresh_worklist_updates_context_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-worklist-refresh-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-REFRESH"
            write_active_feature(project_root, ticket)

            context_path = project_root / "reports" / "research" / f"{ticket}-context.json"
            context_path.parent.mkdir(parents=True, exist_ok=True)
            context_path.write_text(
                json.dumps({"ticket": ticket, "slug": ticket, "generated_at": "2024-01-01T00:00:00Z"}),
                encoding="utf-8",
            )

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
                    }
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

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_nodes_build.main(["--ticket", ticket, "--refresh-worklist"])
            finally:
                os.chdir(old_cwd)

            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("rlm_status"), "ready")
            self.assertTrue(payload.get("rlm_worklist_path"))

    def test_refresh_worklist_preserves_scope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-worklist-refresh-scope-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-REFRESH-SCOPE"
            write_active_feature(project_root, ticket)

            context_path = project_root / "reports" / "research" / f"{ticket}-context.json"
            context_path.parent.mkdir(parents=True, exist_ok=True)
            context_path.write_text(
                json.dumps({"ticket": ticket, "slug": ticket, "generated_at": "2024-01-01T00:00:00Z"}),
                encoding="utf-8",
            )

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
                        "file_id": rlm_config.file_id_for_path(Path("lib/b.py")),
                        "path": "lib/b.py",
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

            worklist_pack = rlm_nodes_build.build_worklist_pack(
                project_root,
                ticket,
                manifest_path=manifest_path,
                nodes_path=nodes_path,
                worklist_paths=["src"],
            )
            worklist_path = project_root / "reports" / "research" / f"{ticket}-rlm.worklist.pack.json"
            worklist_path.parent.mkdir(parents=True, exist_ok=True)
            worklist_path.write_text(
                json.dumps(worklist_pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_nodes_build.main(["--ticket", ticket, "--refresh-worklist"])
            finally:
                os.chdir(old_cwd)

            payload = json.loads(worklist_path.read_text(encoding="utf-8"))
            scope = payload.get("worklist_scope") or {}
            self.assertEqual(scope.get("paths"), ["src"])
            entries = payload.get("entries") or []
            self.assertEqual([entry.get("path") for entry in entries], ["src/a.py"])

    def test_worklist_filters_by_paths_and_keywords(self) -> None:
        if not shutil.which("rg"):
            self.skipTest("rg not installed")
        with tempfile.TemporaryDirectory(prefix="rlm-worklist-scope-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-SCOPE"
            write_active_feature(project_root, ticket)

            (project_root / "src").mkdir(parents=True, exist_ok=True)
            (project_root / "lib").mkdir(parents=True, exist_ok=True)
            (project_root / "src" / "a.py").write_text("alpha\n", encoding="utf-8")
            (project_root / "src" / "b.py").write_text("beta\n", encoding="utf-8")
            (project_root / "lib" / "c.py").write_text("alpha\n", encoding="utf-8")

            targets_path = project_root / "reports" / "research" / f"{ticket}-rlm-targets.json"
            targets_path.parent.mkdir(parents=True, exist_ok=True)
            targets_path.write_text(json.dumps({"paths_base": "aidd"}), encoding="utf-8")

            manifest_path = project_root / "reports" / "research" / f"{ticket}-rlm-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest = {
                "ticket": ticket,
                "targets_path": f"reports/research/{ticket}-rlm-targets.json",
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
                    {
                        "file_id": rlm_config.file_id_for_path(Path("lib/c.py")),
                        "path": "lib/c.py",
                        "rev_sha": "sha-c",
                        "lang": "py",
                        "size": 1,
                        "prompt_version": "v1",
                    },
                ],
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)

            pack = rlm_nodes_build.build_worklist_pack(
                project_root,
                ticket,
                manifest_path=manifest_path,
                nodes_path=nodes_path,
                worklist_paths=["src"],
                worklist_keywords=["alpha"],
            )
            entries = pack.get("entries") or []
            self.assertEqual([entry.get("path") for entry in entries], ["src/a.py"])
            scope = pack.get("worklist_scope") or {}
            self.assertEqual(scope.get("paths"), ["src"])
            self.assertEqual(scope.get("keywords"), ["alpha"])
            counts = scope.get("counts") or {}
            self.assertEqual(counts.get("manifest_total"), 3)
            self.assertEqual(counts.get("paths_matched"), 2)
            self.assertEqual(counts.get("keyword_matches"), 1)
            self.assertEqual(counts.get("entries_selected"), 1)

    def test_build_dir_nodes_from_files(self) -> None:
        nodes = [
            {
                "node_kind": "file",
                "file_id": "file-a",
                "id": "file-a",
                "path": "src/app.py",
                "summary": "App entry",
                "public_symbols": ["App"],
                "type_refs": [],
                "framework_roles": ["web"],
            },
            {
                "node_kind": "file",
                "file_id": "file-b",
                "id": "file-b",
                "path": "src/lib/util.py",
                "summary": "Helpers",
                "public_symbols": ["Util"],
                "type_refs": [],
                "framework_roles": [],
            },
        ]
        dir_nodes = rlm_nodes_build.build_dir_nodes(nodes, max_children=10, max_chars=200)
        dir_paths = {node.get("path") for node in dir_nodes}
        self.assertIn("src", dir_paths)
        self.assertIn("src/lib", dir_paths)


if __name__ == "__main__":
    unittest.main()
