import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import REPO_ROOT, ensure_project_root

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tools import reports_pack


def _write_context(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class ReportsPackTests(unittest.TestCase):
    def test_research_context_pack_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            context_path = tmp_path / "reports" / "research" / "demo-context.json"
            payload = {
                "ticket": "DEMO-1",
                "slug": "demo-1",
                "generated_at": "2024-01-01T00:00:00Z",
                "profile": {
                    "is_new_project": False,
                    "src_layers": ["src/main"],
                    "tests_detected": True,
                    "config_detected": True,
                    "logging_artifacts": ["logback.xml"],
                    "recommendations": ["Use baseline"],
                },
            }
            _write_context(context_path, payload)

            pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)
            first = pack_path.read_text(encoding="utf-8")
            second = pack_path.read_text(encoding="utf-8")
            self.assertEqual(first, second)

            packed = json.loads(first)
            errors = reports_pack.check_budget(
                first,
                max_chars=reports_pack.RESEARCH_BUDGET["max_chars"],
                max_lines=reports_pack.RESEARCH_BUDGET["max_lines"],
                label="research",
            )
            self.assertFalse(errors)
            self.assertEqual(packed["type"], "research")
            self.assertEqual(packed["kind"], "context")
            self.assertEqual(packed["ticket"], "DEMO-1")

    def test_research_context_pack_truncates_matches(self) -> None:
        matches = [
            {"token": "checkout", "file": f"src/{idx}.kt", "line": idx + 1, "snippet": "x" * 300}
            for idx in range(25)
        ]
        payload = {
            "ticket": "DEMO-4",
            "slug": "demo-4",
            "generated_at": "2024-01-08T00:00:00Z",
            "matches": matches,
        }
        pack = reports_pack.build_research_context_pack(payload, source_path="aidd/reports/research/demo-4-context.json")
        match_rows = pack["matches"]["rows"]
        self.assertEqual(len(match_rows), reports_pack.RESEARCH_LIMITS["matches"])
        self.assertLessEqual(len(match_rows[0][4]), reports_pack.RESEARCH_LIMITS["match_snippet_chars"])

    def test_pack_format_toon_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            context_path = tmp_path / "reports" / "research" / "demo-context.json"
            payload = {"ticket": "DEMO-2", "slug": "demo-2", "generated_at": "2024-01-02T00:00:00Z"}
            _write_context(context_path, payload)

            with patch.dict(os.environ, {"AIDD_PACK_FORMAT": "toon"}, clear=False):
                pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)

            self.assertTrue(pack_path.name.endswith(".pack.toon"))
            packed = json.loads(pack_path.read_text(encoding="utf-8"))
            self.assertEqual(packed["ticket"], "DEMO-2")

    def test_qa_pack_includes_id_column(self) -> None:
        payload = {
            "ticket": "QA-1",
            "slug_hint": "qa-1",
            "generated_at": "2024-01-04T00:00:00Z",
            "findings": [
                {
                    "id": "qa-issue-1",
                    "severity": "major",
                    "scope": "tests",
                    "title": "Missing tests",
                    "details": "No tests run",
                    "recommendation": "Add smoke tests",
                }
            ],
        }
        pack = reports_pack.build_qa_pack(payload, source_path="aidd/reports/qa/QA-1.json")
        self.assertEqual(pack["findings"]["cols"][0], "id")
        self.assertIn("blocking", pack["findings"]["cols"])
        self.assertEqual(pack["findings"]["rows"][0][0], "qa-issue-1")

    def test_prd_pack_includes_id_column(self) -> None:
        payload = {
            "ticket": "PRD-1",
            "slug": "prd-1",
            "generated_at": "2024-01-05T00:00:00Z",
            "findings": [
                {
                    "id": "prd-issue-1",
                    "severity": "major",
                    "title": "Placeholder",
                    "details": "TBD present in PRD",
                }
            ],
        }
        pack = reports_pack.build_prd_pack(payload, source_path="aidd/reports/prd/PRD-1.json")
        self.assertEqual(pack["findings"]["cols"][0], "id")
        self.assertEqual(pack["findings"]["rows"][0][0], "prd-issue-1")

    def test_ast_grep_pack_auto_trim_meets_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            jsonl_path = tmp_path / "AG-1-ast-grep.jsonl"
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            lines = []
            for idx in range(40):
                lines.append(
                    json.dumps(
                        {
                            "schema": "aidd.ast_grep_match.v1",
                            "rule_id": f"rule-{idx % 3}",
                            "path": f"src/Main{idx}.java",
                            "line": idx + 1,
                            "col": 1,
                            "snippet": "x" * 400,
                            "message": "demo",
                            "tags": ["jvm"],
                        }
                    )
                )
            jsonl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            pack_path = reports_pack.write_ast_grep_pack(
                jsonl_path,
                ticket="AG-1",
                slug_hint="ag-1",
                root=tmp_path,
            )
            pack_text = pack_path.read_text(encoding="utf-8")
            errors = reports_pack.check_budget(
                pack_text,
                max_chars=reports_pack.AST_GREP_BUDGET["max_chars"],
                max_lines=reports_pack.AST_GREP_BUDGET["max_lines"],
                label="ast-grep",
            )
            self.assertFalse(errors)
            payload = json.loads(pack_text)
            self.assertLessEqual(len(payload.get("rules") or []), reports_pack.AST_GREP_LIMITS["rules"])

    def test_research_pack_budget_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            context_path = tmp_path / "reports" / "research" / "tiny-context.json"
            payload = {"ticket": "DEMO-3", "slug": "demo-3", "generated_at": "2024-01-03T00:00:00Z"}
            _write_context(context_path, payload)

            pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)
            pack_text = pack_path.read_text(encoding="utf-8")

            errors = reports_pack.check_budget(
                pack_text,
                max_chars=reports_pack.RESEARCH_BUDGET["max_chars"],
                max_lines=reports_pack.RESEARCH_BUDGET["max_lines"],
                label="research",
            )
            self.assertFalse(errors)

    def test_research_pack_auto_trim_meets_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            context_path = tmp_path / "reports" / "research" / "trim-context.json"
            matches = [
                {"token": "match", "file": f"src/{idx}.py", "line": idx + 1, "snippet": "x" * 400}
                for idx in range(50)
            ]
            payload = {
                "ticket": "TRIM-1",
                "slug": "trim-1",
                "generated_at": "2024-01-07T00:00:00Z",
                "matches": matches,
            }
            _write_context(context_path, payload)

            pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)
            pack_text = pack_path.read_text(encoding="utf-8")

            errors = reports_pack.check_budget(
                pack_text,
                max_chars=reports_pack.RESEARCH_BUDGET["max_chars"],
                max_lines=reports_pack.RESEARCH_BUDGET["max_lines"],
                label="research",
            )
            self.assertFalse(errors)

            packed = json.loads(pack_text)
            matches_section = packed.get("matches")
            if matches_section:
                self.assertLess(len(matches_section["rows"]), reports_pack.RESEARCH_LIMITS["matches"])

    def test_research_pack_budget_override_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "config" / "conventions.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "reports": {
                            "research_pack_budget": {
                                "max_chars": 4000,
                                "max_lines": 240,
                            }
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            context_path = tmp_path / "reports" / "research" / "override-context.json"
            payload = {
                "ticket": "OVR-1",
                "slug": "ovr-1",
                "generated_at": "2024-01-07T00:00:00Z",
                "manual_notes": ["x" * 160 for _ in range(20)],
            }
            _write_context(context_path, payload)

            pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)
            pack_text = pack_path.read_text(encoding="utf-8")

            self.assertGreater(len(pack_text), reports_pack.RESEARCH_BUDGET["max_chars"])
            errors = reports_pack.check_budget(
                pack_text,
                max_chars=4000,
                max_lines=240,
                label="research",
            )
            self.assertFalse(errors)

    def test_budget_helper_explains_how_to_fix(self) -> None:
        text = "x" * 50
        errors = reports_pack.check_budget(text, max_chars=10, max_lines=1, label="demo")
        self.assertTrue(errors)
        self.assertIn("Reduce top-N", errors[0])

    def test_budget_enforcement_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            context_path = tmp_path / "reports" / "research" / "huge-context.json"
            payload = {
                "ticket": "X" * 2000,
                "slug": "huge",
                "generated_at": "2024-01-06T00:00:00Z",
            }
            _write_context(context_path, payload)

            with patch.dict(os.environ, {"AIDD_PACK_ENFORCE_BUDGET": "1"}, clear=False):
                with self.assertRaises(ValueError) as exc:
                    reports_pack.write_research_context_pack(context_path, root=tmp_path)
            self.assertIn("pack budget exceeded", str(exc.exception))

    def test_rlm_pack_extracts_snippet_from_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-SNIP-1"

            src_dir = workspace / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "a.py").write_text("Foo()\n", encoding="utf-8")

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
                    "key_calls": [],
                    "framework_roles": [],
                    "test_hooks": [],
                    "risks": [],
                    "verification": "passed",
                    "missing_tokens": [],
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

            pack_path = reports_pack.write_rlm_pack(
                nodes_path,
                links_path,
                ticket=ticket,
                slug_hint=ticket,
                root=project_root,
            )
            payload = json.loads(pack_path.read_text(encoding="utf-8"))
            snippet = payload.get("links")[0].get("evidence_snippet")
            self.assertEqual(snippet, "Foo()")

    def test_reports_pack_updates_context_for_rlm(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-CTX-1"

            context_path = project_root / "reports" / "research" / f"{ticket}-context.json"
            _write_context(
                context_path,
                {"ticket": ticket, "slug": ticket, "generated_at": "2024-01-01T00:00:00Z"},
            )

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

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            links_path.write_text(
                json.dumps(
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
                )
                + "\n",
                encoding="utf-8",
            )

            reports_pack.main(
                [
                    "--rlm-nodes",
                    str(nodes_path),
                    "--rlm-links",
                    str(links_path),
                    "--ticket",
                    ticket,
                    "--update-context",
                ]
            )

            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("rlm_status"), "ready")
            self.assertTrue(payload.get("rlm_nodes_path"))
            self.assertTrue(payload.get("rlm_links_path"))
            self.assertTrue(payload.get("rlm_pack_path"))

            context_pack = project_root / "reports" / "research" / f"{ticket}-context.pack.yaml"
            self.assertTrue(context_pack.exists())

    def test_rlm_pack_excludes_model_roles_from_entrypoints(self) -> None:
        nodes = [
            {
                "schema": "aidd.rlm_node.v2",
                "schema_version": "v2",
                "node_kind": "file",
                "file_id": "file-web",
                "id": "file-web",
                "path": "src/web.py",
                "rev_sha": "rev-web",
                "lang": "py",
                "prompt_version": "v1",
                "summary": "web",
                "public_symbols": [],
                "type_refs": [],
                "key_calls": [],
                "framework_roles": ["web"],
                "test_hooks": [],
                "risks": [],
                "verification": "passed",
                "missing_tokens": [],
            },
            {
                "schema": "aidd.rlm_node.v2",
                "schema_version": "v2",
                "node_kind": "file",
                "file_id": "file-dto",
                "id": "file-dto",
                "path": "src/dto.py",
                "rev_sha": "rev-dto",
                "lang": "py",
                "prompt_version": "v1",
                "summary": "dto",
                "public_symbols": [],
                "type_refs": [],
                "key_calls": [],
                "framework_roles": ["web", "model"],
                "test_hooks": [],
                "risks": [],
                "verification": "passed",
                "missing_tokens": [],
            },
        ]
        pack = reports_pack.build_rlm_pack(
            nodes,
            [],
            ticket="RLM-ROLE",
            slug_hint="rlm-role",
            source_path="reports/research/RLM-ROLE-rlm.nodes.jsonl",
        )
        entrypoints = pack.get("entrypoints") or []
        self.assertEqual([item.get("file_id") for item in entrypoints], ["file-web"])

    def test_rlm_context_pending_when_worklist_has_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            ensure_project_root(project_root)
            ticket = "RLM-WORKLIST"

            context_path = project_root / "reports" / "research" / f"{ticket}-context.json"
            _write_context(
                context_path,
                {
                    "ticket": ticket,
                    "slug": ticket,
                    "generated_at": "2024-01-10T00:00:00Z",
                    "rlm_worklist_path": f"reports/research/{ticket}-rlm.worklist.pack.yaml",
                },
            )

            worklist_path = project_root / "reports" / "research" / f"{ticket}-rlm.worklist.pack.yaml"
            worklist_path.parent.mkdir(parents=True, exist_ok=True)
            worklist_path.write_text(
                json.dumps(
                    {
                        "schema": "aidd.report.pack.v1",
                        "type": "rlm-worklist",
                        "status": "pending",
                        "entries": [{"file_id": "file-a"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.write_text(
                json.dumps(
                    {
                        "schema": "aidd.rlm_node.v2",
                        "schema_version": "v2",
                        "node_kind": "file",
                        "id": "file-a",
                        "file_id": "file-a",
                        "path": "src/a.py",
                        "rev_sha": "rev-a",
                        "lang": "py",
                        "prompt_version": "v1",
                        "summary": "demo",
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
            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            links_path.write_text(
                json.dumps(
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
                )
                + "\n",
                encoding="utf-8",
            )

            reports_pack.main(
                [
                    "--rlm-nodes",
                    str(nodes_path),
                    "--rlm-links",
                    str(links_path),
                    "--ticket",
                    ticket,
                    "--update-context",
                ]
            )

            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("rlm_status"), "pending")
            pack_path = project_root / "reports" / "research" / f"{ticket}-rlm.pack.yaml"
            pack_payload = json.loads(pack_path.read_text(encoding="utf-8"))
            self.assertEqual(pack_payload.get("status"), "pending")
            self.assertEqual(pack_payload.get("stats", {}).get("worklist_entries"), 1)

    def test_rlm_update_context_pending_without_nodes_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            ensure_project_root(project_root)
            ticket = "RLM-NODES-MISSING"
            context_path = project_root / "reports" / "research" / f"{ticket}-context.json"
            context_path.parent.mkdir(parents=True, exist_ok=True)
            context_path.write_text(json.dumps({"ticket": ticket}, indent=2) + "\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.write_text("", encoding="utf-8")
            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            links_path.write_text("", encoding="utf-8")

            reports_pack.main(
                [
                    "--rlm-nodes",
                    str(nodes_path),
                    "--rlm-links",
                    str(links_path),
                    "--ticket",
                    ticket,
                    "--update-context",
                ]
            )

            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("rlm_status"), "pending")

    def test_rlm_pack_warns_when_partial_vs_worklist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            ensure_project_root(project_root)
            ticket = "RLM-PARTIAL"

            worklist_path = project_root / "reports" / "research" / f"{ticket}-rlm.worklist.pack.yaml"
            worklist_path.parent.mkdir(parents=True, exist_ok=True)
            worklist_path.write_text(
                json.dumps(
                    {
                        "schema": "aidd.report.pack.v1",
                        "type": "rlm-worklist",
                        "status": "pending",
                        "entries": [{"file_id": f"file-{idx}"} for idx in range(10)],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.write_text(
                json.dumps(
                    {
                        "schema": "aidd.rlm_node.v2",
                        "schema_version": "v2",
                        "node_kind": "file",
                        "id": "file-a",
                        "file_id": "file-a",
                        "path": "src/a.py",
                        "rev_sha": "rev-a",
                        "lang": "py",
                        "prompt_version": "v1",
                        "summary": "demo",
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
            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            links_path.write_text(
                json.dumps(
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
                )
                + "\n",
                encoding="utf-8",
            )

            pack_path = reports_pack.write_rlm_pack(
                nodes_path,
                links_path,
                ticket=ticket,
                slug_hint=ticket,
                root=project_root,
            )
            payload = json.loads(pack_path.read_text(encoding="utf-8"))
            warnings = payload.get("warnings") or []
            self.assertTrue(any("rlm pack partial" in warning for warning in warnings))

    def test_rlm_pack_warns_on_fallback_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-FALLBACK"

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps({"rlm": {"link_fallback_warn_ratio": 0.4}}, indent=2),
                encoding="utf-8",
            )

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes = []
            for idx in range(4):
                nodes.append(
                    {
                        "schema": "aidd.rlm_node.v2",
                        "schema_version": "v2",
                        "node_kind": "file",
                        "file_id": f"file-{idx}",
                        "id": f"file-{idx}",
                        "path": f"src/{idx}.py",
                        "rev_sha": f"rev-{idx}",
                        "lang": "py",
                        "prompt_version": "v1",
                        "summary": "summary",
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
            nodes_path.write_text("\n".join(json.dumps(item) for item in nodes) + "\n", encoding="utf-8")

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            links_path.write_text(
                json.dumps(
                    {
                        "schema": "aidd.rlm_link.v1",
                        "schema_version": "v1",
                        "link_id": "link-1",
                        "src_file_id": "file-0",
                        "dst_file_id": "file-1",
                        "type": "calls",
                        "evidence_ref": {
                            "path": "src/0.py",
                            "line_start": 1,
                            "line_end": 1,
                            "extractor": "regex",
                            "match_hash": "hash",
                        },
                        "unverified": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            stats_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
            stats_path.write_text(
                json.dumps({"fallback_nodes": 3}, indent=2),
                encoding="utf-8",
            )

            pack_path = reports_pack.write_rlm_pack(
                nodes_path,
                links_path,
                ticket=ticket,
                slug_hint=ticket,
                root=project_root,
            )
            payload = json.loads(pack_path.read_text(encoding="utf-8"))
            warnings = payload.get("warnings") or []
            self.assertTrue(any("fallback ratio" in warning for warning in warnings))

    def test_rlm_pack_warns_on_unverified_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-UNVERIFIED"

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps({"rlm": {"link_unverified_warn_ratio": 0.4}}, indent=2),
                encoding="utf-8",
            )

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_path.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "schema": "aidd.rlm_node.v2",
                            "schema_version": "v2",
                            "node_kind": "file",
                            "file_id": f"file-{idx}",
                            "id": f"file-{idx}",
                            "path": f"src/{idx}.py",
                            "rev_sha": f"rev-{idx}",
                            "lang": "py",
                            "prompt_version": "v1",
                            "summary": "summary",
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
                    for idx in range(3)
                )
                + "\n",
                encoding="utf-8",
            )

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            links_path.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "schema": "aidd.rlm_link.v1",
                            "schema_version": "v1",
                            "link_id": f"link-{idx}",
                            "src_file_id": "file-0",
                            "dst_file_id": f"file-{idx}",
                            "type": "calls",
                            "evidence_ref": {
                                "path": "src/0.py",
                                "line_start": 1,
                                "line_end": 1,
                                "extractor": "regex",
                                "match_hash": f"hash-{idx}",
                            },
                            "unverified": idx != 0,
                        }
                    )
                    for idx in range(3)
                )
                + "\n",
                encoding="utf-8",
            )

            pack_path = reports_pack.write_rlm_pack(
                nodes_path,
                links_path,
                ticket=ticket,
                slug_hint=ticket,
                root=project_root,
            )
            payload = json.loads(pack_path.read_text(encoding="utf-8"))
            warnings = payload.get("warnings") or []
            self.assertTrue(any("unverified links ratio" in warning for warning in warnings))

    def test_rlm_pack_enforces_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-BUDGET"

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps(
                    {
                        "rlm": {
                            "pack_budget": {
                                "max_chars": 400,
                                "max_lines": 30,
                                "entrypoints": 5,
                                "hotspots": 5,
                                "integration_points": 5,
                                "test_hooks": 5,
                                "recommended_reads": 5,
                                "links": 5,
                                "evidence_snippet_chars": 160,
                                "enforce": True,
                            }
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            src_dir = workspace / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "a.py").write_text("x" * 300 + "\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes = []
            for idx in range(6):
                nodes.append(
                    {
                        "schema": "aidd.rlm_node.v2",
                        "schema_version": "v2",
                        "node_kind": "file",
                        "file_id": f"file-{idx}",
                        "id": f"file-{idx}",
                        "path": "src/a.py",
                        "rev_sha": f"rev-{idx}",
                        "lang": "py",
                        "prompt_version": "v1",
                        "summary": "summary-" + ("y" * 80),
                        "public_symbols": [],
                        "type_refs": [],
                        "key_calls": [],
                        "framework_roles": ["controller"],
                        "test_hooks": [],
                        "risks": ["risk-" + ("z" * 40)],
                        "verification": "passed",
                        "missing_tokens": [],
                    }
                )
            nodes_path.write_text("\n".join(json.dumps(item) for item in nodes) + "\n", encoding="utf-8")

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            links = []
            for idx in range(6):
                links.append(
                    {
                        "schema": "aidd.rlm_link.v1",
                        "schema_version": "v1",
                        "link_id": f"link-{idx}",
                        "src_file_id": f"file-{idx}",
                        "dst_file_id": f"file-{idx}",
                        "type": "calls",
                        "evidence_ref": {
                            "path": "src/a.py",
                            "line_start": 1,
                            "line_end": 1,
                            "extractor": "regex",
                            "match_hash": f"hash-{idx}",
                        },
                        "unverified": False,
                    }
                )
            links_path.write_text("\n".join(json.dumps(item) for item in links) + "\n", encoding="utf-8")

            pack_path = reports_pack.write_rlm_pack(
                nodes_path,
                links_path,
                ticket=ticket,
                slug_hint=ticket,
                root=project_root,
            )
            pack_text = pack_path.read_text(encoding="utf-8")
            errors = reports_pack.check_budget(pack_text, max_chars=400, max_lines=30, label="rlm")
            self.assertFalse(errors)

            payload = json.loads(pack_text)
            trim_stats = payload.get("pack_trim_stats") or {}
            self.assertTrue(trim_stats.get("enforce"))

    def test_rlm_pack_trims_max_lines_without_enforce(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-LINES"

            (project_root / "config").mkdir(parents=True, exist_ok=True)
            (project_root / "config" / "conventions.json").write_text(
                json.dumps(
                    {
                        "rlm": {
                            "pack_budget": {
                                "max_chars": 4000,
                                "max_lines": 60,
                                "entrypoints": 10,
                                "hotspots": 10,
                                "integration_points": 10,
                                "test_hooks": 10,
                                "recommended_reads": 10,
                                "links": 10,
                                "evidence_snippet_chars": 160,
                                "enforce": False,
                            }
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            src_dir = workspace / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "a.py").write_text("Foo()\n", encoding="utf-8")

            nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
            nodes_path.parent.mkdir(parents=True, exist_ok=True)
            nodes = []
            for idx in range(10):
                nodes.append(
                    {
                        "schema": "aidd.rlm_node.v2",
                        "schema_version": "v2",
                        "node_kind": "file",
                        "file_id": f"file-{idx}",
                        "id": f"file-{idx}",
                        "path": "src/a.py",
                        "rev_sha": f"rev-{idx}",
                        "lang": "py",
                        "prompt_version": "v1",
                        "summary": "summary",
                        "public_symbols": [],
                        "type_refs": [],
                        "key_calls": [],
                        "framework_roles": ["controller"],
                        "test_hooks": [],
                        "risks": [],
                        "verification": "passed",
                        "missing_tokens": [],
                    }
                )
            nodes_path.write_text("\n".join(json.dumps(item) for item in nodes) + "\n", encoding="utf-8")

            links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
            links = []
            for idx in range(10):
                links.append(
                    {
                        "schema": "aidd.rlm_link.v1",
                        "schema_version": "v1",
                        "link_id": f"link-{idx}",
                        "src_file_id": f"file-{idx}",
                        "dst_file_id": f"file-{idx}",
                        "type": "calls",
                        "evidence_ref": {
                            "path": "src/a.py",
                            "line_start": 1,
                            "line_end": 1,
                            "extractor": "regex",
                            "match_hash": f"hash-{idx}",
                        },
                        "unverified": False,
                    }
                )
            links_path.write_text("\n".join(json.dumps(item) for item in links) + "\n", encoding="utf-8")

            pack_path = reports_pack.write_rlm_pack(
                nodes_path,
                links_path,
                ticket=ticket,
                slug_hint=ticket,
                root=project_root,
            )
            pack_text = pack_path.read_text(encoding="utf-8")
            errors = reports_pack.check_budget(pack_text, max_chars=4000, max_lines=60, label="rlm")
            self.assertFalse(errors)

    def test_rlm_pack_trim_priority_respected(self) -> None:
        payload = {
            "schema": "aidd.report.pack.v1",
            "pack_version": "v1",
            "type": "rlm",
            "kind": "pack",
            "ticket": "RLM-TRIM-ORDER",
            "entrypoints": [{"path": f"src/entry-{idx}.py"} for idx in range(3)],
            "links": [{"src_file_id": "a", "dst_file_id": "b"} for _ in range(3)],
            "recommended_reads": [{"path": f"src/read-{idx}.py"} for idx in range(3)],
            "hotspots": [{"path": f"src/hot-{idx}.py"} for idx in range(3)],
            "integration_points": [{"path": "src/integ.py"}],
            "test_hooks": [{"path": "src/test.py"}],
            "risks": [{"path": "src/risk.py"}],
        }
        text = reports_pack._serialize_pack(payload)
        max_chars = max(1, len(text) - 1)
        _, _, _, trim_stats = reports_pack._auto_trim_rlm_pack(
            payload,
            max_chars=max_chars,
            max_lines=999,
            enforce=False,
            trim_priority=["entrypoints", "links"],
        )
        steps = trim_stats.get("steps") or []
        self.assertTrue(steps)
        self.assertEqual(steps[0], "entrypoints")
        if "links" in steps:
            self.assertGreaterEqual(steps.index("links"), steps.index("entrypoints"))
