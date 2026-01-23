import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import ensure_project_root, write_active_feature, write_json

from tools import rlm_links_build, reports_pack
from tools.rlm_config import file_id_for_path


class RlmLinksBuildTests(unittest.TestCase):
    def test_links_build_creates_calls_link(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-4"
            write_active_feature(project_root, ticket)

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("from b import Foo\nFoo()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

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
                    "summary": "",
                    "public_symbols": [],
                    "key_calls": ["Foo"],
                    "framework_roles": [],
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
                    "summary": "",
                    "public_symbols": ["Foo"],
                    "key_calls": [],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
            ]
            nodes_path.write_text("\n".join(json.dumps(item) for item in nodes) + "\n", encoding="utf-8")

            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-targets.json",
                {
                    "ticket": ticket,
                    "files": ["src/a.py", "src/b.py"],
                },
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_links_build.main(["--ticket", ticket])
            finally:
                os.chdir(old_cwd)

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            self.assertTrue(links_path.exists())
            lines = links_path.read_text(encoding="utf-8").splitlines()
            self.assertTrue(lines)
            payload = json.loads(lines[0])
            self.assertEqual(payload.get("type"), "calls")
            self.assertEqual(payload.get("src_file_id"), "file-a")
            self.assertEqual(payload.get("dst_file_id"), "file-b")

            stats_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
            self.assertTrue(stats_path.exists())
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertEqual(stats.get("links_total"), 1)

    def test_links_build_records_truncation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-trunc-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-5"
            write_active_feature(project_root, ticket)

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps({"rlm": {"max_links": 1, "max_symbols_per_file": 0}}, indent=2),
                encoding="utf-8",
            )

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("Foo()\nBar()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")
            (workspace / "src" / "c.py").write_text("class Bar:\n    pass\n", encoding="utf-8")

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
                    "summary": "",
                    "public_symbols": [],
                    "key_calls": ["Foo", "Bar"],
                    "framework_roles": [],
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
                    "summary": "",
                    "public_symbols": ["Foo"],
                    "key_calls": [],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
                {
                    "schema": "aidd.rlm_node.v1",
                    "schema_version": "v1",
                    "node_kind": "file",
                    "file_id": "file-c",
                    "id": "file-c",
                    "path": "src/c.py",
                    "rev_sha": "rev-c",
                    "lang": "py",
                    "prompt_version": "v1",
                    "summary": "",
                    "public_symbols": ["Bar"],
                    "key_calls": [],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
            ]
            nodes_path.write_text("\n".join(json.dumps(item) for item in nodes) + "\n", encoding="utf-8")

            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-targets.json",
                {
                    "ticket": ticket,
                    "files": ["src/a.py", "src/b.py", "src/c.py"],
                },
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_links_build.main(["--ticket", ticket])
            finally:
                os.chdir(old_cwd)

            stats_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertTrue(stats.get("links_truncated"))

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            pack_path = reports_pack.write_rlm_pack(
                nodes_path,
                links_path,
                ticket=ticket,
                slug_hint=ticket,
                root=project_root,
            )
            pack_payload = json.loads(pack_path.read_text(encoding="utf-8"))
            warnings = pack_payload.get("warnings") or []
            self.assertTrue(any("max_links" in warning for warning in warnings))

    def test_links_build_records_rg_timeout_warning(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-rg-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-6"
            write_active_feature(project_root, ticket)

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("print('no match')\n", encoding="utf-8")

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
                    "summary": "",
                    "public_symbols": [],
                    "key_calls": ["Foo"],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                }
            ]
            nodes_path.write_text("\n".join(json.dumps(item) for item in nodes) + "\n", encoding="utf-8")

            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-targets.json",
                {
                    "ticket": ticket,
                    "files": ["src/a.py"],
                },
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with patch("tools.rlm_links_build._rg_batch_find_matches", return_value=({}, "timeout")):
                    rlm_links_build.main(["--ticket", ticket])
            finally:
                os.chdir(old_cwd)

            stats_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertGreater(stats.get("rg_timeouts") or 0, 0)

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            pack_path = reports_pack.write_rlm_pack(
                nodes_path,
                links_path,
                ticket=ticket,
                slug_hint=ticket,
                root=project_root,
            )
            pack_payload = json.loads(pack_path.read_text(encoding="utf-8"))
            warnings = pack_payload.get("warnings") or []
            self.assertTrue(any("timeout" in warning for warning in warnings))

    def test_links_build_fails_when_nodes_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-missing-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-7"
            write_active_feature(project_root, ticket)

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with self.assertRaises(SystemExit) as exc:
                    rlm_links_build.main(["--ticket", ticket])
                self.assertIn("nodes.jsonl", str(exc.exception))
            finally:
                os.chdir(old_cwd)

    def test_links_build_fallbacks_to_manifest_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-manifest-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-8"
            write_active_feature(project_root, ticket)

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("Foo()\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                json.dumps(
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
                        "summary": "",
                        "public_symbols": [],
                        "key_calls": ["Foo"],
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

            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-targets.json",
                {"ticket": ticket, "paths_base": "workspace", "files": []},
            )
            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-manifest.json",
                {
                    "ticket": ticket,
                    "files": [
                        {
                            "file_id": "file-a",
                            "path": "src/a.py",
                            "rev_sha": "rev-a",
                            "lang": "py",
                            "size": 10,
                            "prompt_version": "v1",
                        }
                    ],
                },
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_links_build.main(["--ticket", ticket])
            finally:
                os.chdir(old_cwd)

            stats_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertEqual(stats.get("target_files_source"), "manifest")
            self.assertEqual(stats.get("target_files_total"), 1)

    def test_links_build_emits_unverified_link_without_dst_node(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-unverified-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-9"
            write_active_feature(project_root, ticket)

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("Foo()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                json.dumps(
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
                        "summary": "",
                        "public_symbols": [],
                        "key_calls": ["Foo"],
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

            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-targets.json",
                {"ticket": ticket, "files": ["src/a.py", "src/b.py"]},
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_links_build.main(["--ticket", ticket])
            finally:
                os.chdir(old_cwd)

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            lines = links_path.read_text(encoding="utf-8").splitlines()
            self.assertTrue(lines)
            payload = json.loads(lines[0])
            self.assertTrue(payload.get("unverified"))
            self.assertEqual(payload.get("dst_file_id"), file_id_for_path(Path("src/b.py")))

    def test_links_build_warns_when_targets_empty(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-empty-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-10"
            write_active_feature(project_root, ticket)

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                json.dumps(
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
                        "summary": "",
                        "public_symbols": [],
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

            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-targets.json",
                {"ticket": ticket, "files": []},
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_links_build.main(["--ticket", ticket])
            finally:
                os.chdir(old_cwd)

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            pack_path = reports_pack.write_rlm_pack(
                nodes_path,
                links_path,
                ticket=ticket,
                slug_hint=ticket,
                root=project_root,
            )
            pack_payload = json.loads(pack_path.read_text(encoding="utf-8"))
            warnings = pack_payload.get("warnings") or []
            self.assertTrue(any("targets empty" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
