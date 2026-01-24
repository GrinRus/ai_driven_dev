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
            (workspace / "src" / "a.py").write_text("Foo()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes = [
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
                    "key_calls": ["Foo"],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
                {
                    "schema": "aidd.rlm_node.v2",
                    "schema_version": "v2",
                    "node_kind": "file",
                    "file_id": "file-b",
                    "id": "file-b",
                    "path": "src/b.py",
                    "rev_sha": "rev-b",
                    "lang": "py",
                    "prompt_version": "v1",
                    "summary": "",
                    "public_symbols": ["Foo"],
                    "type_refs": [],
                    "key_calls": ["Foo"],
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

    def test_links_build_classifies_imports(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-imports-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-IMPORTS"
            write_active_feature(project_root, ticket)

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("from b import Foo\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes = [
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
                    "key_calls": ["Foo"],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
                {
                    "schema": "aidd.rlm_node.v2",
                    "schema_version": "v2",
                    "node_kind": "file",
                    "file_id": "file-b",
                    "id": "file-b",
                    "path": "src/b.py",
                    "rev_sha": "rev-b",
                    "lang": "py",
                    "prompt_version": "v1",
                    "summary": "",
                    "public_symbols": ["Foo"],
                    "type_refs": [],
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
            payload = json.loads(links_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload.get("type"), "imports")

    def test_links_build_classifies_extends_implements(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-extends-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-EXTENDS"
            write_active_feature(project_root, ticket)

            src_root = workspace / "src"
            src_root.mkdir(parents=True, exist_ok=True)
            (src_root / "A.java").write_text("public class A {}\n", encoding="utf-8")
            (src_root / "I.java").write_text("public interface I {}\n", encoding="utf-8")
            (src_root / "B.java").write_text("public class B extends A {}\n", encoding="utf-8")
            (src_root / "C.java").write_text("public class C implements I {}\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes = [
                {
                    "schema": "aidd.rlm_node.v2",
                    "schema_version": "v2",
                    "node_kind": "file",
                    "file_id": "file-a",
                    "id": "file-a",
                    "path": "src/A.java",
                    "rev_sha": "rev-a",
                    "lang": "java",
                    "prompt_version": "v1",
                    "summary": "",
                    "public_symbols": ["A"],
                    "type_refs": [],
                    "key_calls": [],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
                {
                    "schema": "aidd.rlm_node.v2",
                    "schema_version": "v2",
                    "node_kind": "file",
                    "file_id": "file-i",
                    "id": "file-i",
                    "path": "src/I.java",
                    "rev_sha": "rev-i",
                    "lang": "java",
                    "prompt_version": "v1",
                    "summary": "",
                    "public_symbols": ["I"],
                    "type_refs": [],
                    "key_calls": [],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
                {
                    "schema": "aidd.rlm_node.v2",
                    "schema_version": "v2",
                    "node_kind": "file",
                    "file_id": "file-b",
                    "id": "file-b",
                    "path": "src/B.java",
                    "rev_sha": "rev-b",
                    "lang": "java",
                    "prompt_version": "v1",
                    "summary": "",
                    "public_symbols": ["B"],
                    "type_refs": ["A"],
                    "key_calls": [],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
                {
                    "schema": "aidd.rlm_node.v2",
                    "schema_version": "v2",
                    "node_kind": "file",
                    "file_id": "file-c",
                    "id": "file-c",
                    "path": "src/C.java",
                    "rev_sha": "rev-c",
                    "lang": "java",
                    "prompt_version": "v1",
                    "summary": "",
                    "public_symbols": ["C"],
                    "type_refs": ["I"],
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
                    "files": ["src/A.java", "src/I.java", "src/B.java", "src/C.java"],
                },
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_links_build.main(["--ticket", ticket])
            finally:
                os.chdir(old_cwd)

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            types = {json.loads(line).get("type") for line in links_path.read_text(encoding="utf-8").splitlines()}
            self.assertIn("extends", types)
            self.assertIn("implements", types)
    def test_links_build_uses_key_calls_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-keycalls-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-KEYCALLS"
            write_active_feature(project_root, ticket)

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps(
                    {
                        "rlm": {
                            "link_key_calls_source": "key_calls",
                            "link_fallback_mode": "types_only",
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("Foo()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes = [
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
                    "public_symbols": ["notType"],
                    "type_refs": [],
                    "key_calls": ["Foo"],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
                {
                    "schema": "aidd.rlm_node.v2",
                    "schema_version": "v2",
                    "node_kind": "file",
                    "file_id": "file-b",
                    "id": "file-b",
                    "path": "src/b.py",
                    "rev_sha": "rev-b",
                    "lang": "py",
                    "prompt_version": "v1",
                    "summary": "",
                    "public_symbols": ["Foo"],
                    "type_refs": [],
                    "key_calls": ["Foo"],
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
            payload = json.loads(links_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload.get("dst_file_id"), "file-b")
            self.assertFalse(payload.get("unverified"))

            stats_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertIn("key_calls", stats.get("symbols_source") or "")
            self.assertEqual(stats.get("fallback_nodes"), 0)

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
                    "key_calls": ["Foo", "Bar"],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
                {
                    "schema": "aidd.rlm_node.v2",
                    "schema_version": "v2",
                    "node_kind": "file",
                    "file_id": "file-b",
                    "id": "file-b",
                    "path": "src/b.py",
                    "rev_sha": "rev-b",
                    "lang": "py",
                    "prompt_version": "v1",
                    "summary": "",
                    "public_symbols": ["Foo"],
                    "type_refs": [],
                    "key_calls": [],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
                },
                {
                    "schema": "aidd.rlm_node.v2",
                    "schema_version": "v2",
                    "node_kind": "file",
                    "file_id": "file-c",
                    "id": "file-c",
                    "path": "src/c.py",
                    "rev_sha": "rev-c",
                    "lang": "py",
                    "prompt_version": "v1",
                    "summary": "",
                    "public_symbols": ["Bar"],
                    "type_refs": [],
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
            evidence_path = payload.get("evidence_ref", {}).get("path")
            self.assertEqual(payload.get("dst_file_id"), file_id_for_path(Path(evidence_path)))

    def test_links_build_rg_verifies_when_dst_node_exists(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-rg-verify-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-RG-VERIFY"
            write_active_feature(project_root, ticket)

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps({"rlm": {"link_rg_verify": "auto"}}, indent=2),
                encoding="utf-8",
            )

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("Foo()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

            file_a_id = file_id_for_path(Path("src/a.py"))
            file_b_id = file_id_for_path(Path("src/b.py"))

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in [
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": file_a_id,
                            "id": file_a_id,
                            "path": "src/a.py",
                            "rev_sha": "rev-a",
                            "lang": "py",
                            "prompt_version": "v1",
                            "summary": "",
                            "public_symbols": [],
                            "type_refs": [],
                            "key_calls": ["Foo"],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": file_b_id,
                            "id": file_b_id,
                            "path": "src/b.py",
                            "rev_sha": "rev-b",
                            "lang": "py",
                            "prompt_version": "v1",
                            "summary": "",
                            "public_symbols": [],
                            "type_refs": [],
                            "key_calls": ["Foo"],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-targets.json",
                {"ticket": ticket, "files": ["src/b.py", "src/a.py"]},
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rlm_links_build.main(["--ticket", ticket])
            finally:
                os.chdir(old_cwd)

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            payload = json.loads(links_path.read_text(encoding="utf-8").splitlines()[0])
            evidence_path = payload.get("evidence_ref", {}).get("path")
            self.assertEqual(payload.get("dst_file_id"), file_id_for_path(Path(evidence_path)))
            self.assertFalse(payload.get("unverified"))

    def test_links_build_filters_type_refs_by_prefix(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-type-prefix-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-TYPE-FILTER"
            write_active_feature(project_root, ticket)

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps(
                    {
                        "rlm": {
                            "link_type_refs_mode": "only",
                            "type_refs_exclude_prefixes": ["java."],
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("Foo()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in [
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
                            "type_refs": ["java.util.List", "Foo"],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": "file-b",
                            "id": "file-b",
                            "path": "src/b.py",
                            "rev_sha": "rev-b",
                            "lang": "py",
                            "prompt_version": "v1",
                            "summary": "",
                            "public_symbols": ["Foo"],
                            "type_refs": [],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                    ]
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

            stats_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertEqual(stats.get("type_refs_total"), 1)
            self.assertEqual(stats.get("type_refs_used"), 1)

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            payload = json.loads(links_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload.get("dst_file_id"), "file-b")

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

    def test_links_build_falls_back_to_public_symbols(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-fallback-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-11"
            write_active_feature(project_root, ticket)

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps({"rlm": {"link_key_calls_source": "key_calls"}}, indent=2),
                encoding="utf-8",
            )

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("Foo()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in [
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
                            "public_symbols": ["Foo"],
                            "type_refs": [],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": "file-b",
                            "id": "file-b",
                            "path": "src/b.py",
                            "rev_sha": "rev-b",
                            "lang": "py",
                            "prompt_version": "v1",
                            "summary": "",
                            "public_symbols": ["Foo"],
                            "type_refs": [],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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

            stats_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertEqual(stats.get("symbols_source"), "public_symbols")
            self.assertGreater(stats.get("fallback_nodes") or 0, 0)

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            payload = json.loads(links_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload.get("dst_file_id"), "file-b")
            self.assertTrue(payload.get("unverified"))

    def test_links_build_prefers_type_refs_over_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-typerefs-prefer-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-TYPE-PREFER"
            write_active_feature(project_root, ticket)

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps(
                    {
                        "rlm": {
                            "link_key_calls_source": "key_calls",
                            "link_type_refs_mode": "additive",
                            "link_type_refs_priority": "prefer",
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("Foo()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in [
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
                            "public_symbols": ["Foo"],
                            "type_refs": ["Foo"],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": "file-b",
                            "id": "file-b",
                            "path": "src/b.py",
                            "rev_sha": "rev-b",
                            "lang": "py",
                            "prompt_version": "v1",
                            "summary": "",
                            "public_symbols": ["Foo"],
                            "type_refs": [],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
            payload = json.loads(links_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload.get("dst_file_id"), "file-b")
            self.assertFalse(payload.get("unverified"))

            stats_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertIn("type_refs", stats.get("symbols_source") or "")
            self.assertGreater(stats.get("fallback_nodes") or 0, 0)

    def test_links_build_uses_type_refs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-typerefs-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-TYPE"
            write_active_feature(project_root, ticket)

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps({"rlm": {"link_type_refs_mode": "only"}}, indent=2),
                encoding="utf-8",
            )

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("from b import Bar\nBar()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Bar:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in [
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
                            "type_refs": ["Bar"],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": "file-b",
                            "id": "file-b",
                            "path": "src/b.py",
                            "rev_sha": "rev-b",
                            "lang": "py",
                            "prompt_version": "v1",
                            "summary": "",
                            "public_symbols": ["Bar"],
                            "type_refs": [],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
            payload = json.loads(links_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload.get("src_file_id"), "file-a")
            self.assertEqual(payload.get("dst_file_id"), "file-b")
            self.assertFalse(payload.get("unverified"))

            stats_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertEqual(stats.get("symbols_source"), "type_refs")

    def test_links_build_prefers_keyword_hits_when_trimming(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-keywords-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-12"
            write_active_feature(project_root, ticket)

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps({"rlm": {"max_files": 1}}, indent=2),
                encoding="utf-8",
            )

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("Foo()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")
            (workspace / "src" / "c.py").write_text("print('c')\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in [
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
                            "key_calls": ["Foo"],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": "file-b",
                            "id": "file-b",
                            "path": "src/b.py",
                            "rev_sha": "rev-b",
                            "lang": "py",
                            "prompt_version": "v1",
                            "summary": "",
                            "public_symbols": ["Foo"],
                            "type_refs": [],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": "file-c",
                            "id": "file-c",
                            "path": "src/c.py",
                            "rev_sha": "rev-c",
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
                        },
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-targets.json",
                {
                    "ticket": ticket,
                    "files": ["src/a.py", "src/b.py", "src/c.py"],
                    "keyword_hits": ["src/a.py", "src/b.py", "src/c.py"],
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
            self.assertEqual(stats.get("target_files_source"), "keyword_hits")
            self.assertEqual(stats.get("target_files_total"), 3)
            self.assertEqual(stats.get("target_files_trimmed"), 2)

    def test_links_build_ignores_non_type_symbols_in_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-types-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-13"
            write_active_feature(project_root, ticket)

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("def listAgents():\n    pass\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("def listAgents():\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in [
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
                            "public_symbols": ["listAgents"],
                            "type_refs": [],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": "file-b",
                            "id": "file-b",
                            "path": "src/b.py",
                            "rev_sha": "rev-b",
                            "lang": "py",
                            "prompt_version": "v1",
                            "summary": "",
                            "public_symbols": ["listAgents"],
                            "type_refs": [],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                    ]
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
            self.assertTrue(links_path.exists())
            self.assertEqual(links_path.read_text(encoding="utf-8").strip(), "")

    def test_links_build_prefers_keyword_hits_when_threshold_exceeded(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-threshold-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-14"
            write_active_feature(project_root, ticket)

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps({"rlm": {"link_target_threshold": 2}}, indent=2),
                encoding="utf-8",
            )

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("Foo()\n", encoding="utf-8")
            (workspace / "src" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in [
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
                            "key_calls": ["Foo"],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": "file-b",
                            "id": "file-b",
                            "path": "src/b.py",
                            "rev_sha": "rev-b",
                            "lang": "py",
                            "prompt_version": "v1",
                            "summary": "",
                            "public_symbols": ["Foo"],
                            "type_refs": [],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-targets.json",
                {
                    "ticket": ticket,
                    "files": ["src/a.py", "src/b.py"],
                    "keyword_hits": ["src/a.py"],
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
            self.assertEqual(stats.get("target_files_source"), "keyword_hits")
            self.assertEqual(stats.get("target_files_total"), 1)

    def test_links_build_scopes_targets_with_worklist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-links-scope-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-15"
            write_active_feature(project_root, ticket)

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "other").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "a.py").write_text("Foo()\n", encoding="utf-8")
            (workspace / "other" / "b.py").write_text("class Foo:\n    pass\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in [
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
                            "key_calls": ["Foo"],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": "file-b",
                            "id": "file-b",
                            "path": "other/b.py",
                            "rev_sha": "rev-b",
                            "lang": "py",
                            "prompt_version": "v1",
                            "summary": "",
                            "public_symbols": ["Foo"],
                            "type_refs": [],
                            "key_calls": [],
                            "framework_roles": [],
                            "test_hooks": [],
                            "risks": [],
                            "verification": "passed",
                            "missing_tokens": [],
                        },
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-targets.json",
                {
                    "ticket": ticket,
                    "paths_base": "workspace",
                    "files": ["src/a.py", "other/b.py"],
                    "keyword_hits": ["src/a.py", "other/b.py"],
                },
            )
            write_json(
                workspace,
                f"reports/research/{ticket}-rlm.worklist.pack.yaml",
                {
                    "type": "rlm-worklist",
                    "worklist_scope": {
                        "paths": ["src"],
                        "keywords": [],
                        "counts": {"entries_selected": 1},
                    },
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
            self.assertEqual(stats.get("target_files_scope"), "worklist")
            self.assertEqual(stats.get("target_files_total"), 1)
            self.assertEqual(stats.get("target_files_scope_total"), 1)


if __name__ == "__main__":
    unittest.main()
