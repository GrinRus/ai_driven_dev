from __future__ import annotations

import datetime as dt
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from tests.helpers import REPO_ROOT

sys.path.append(str(REPO_ROOT))

from aidd_runtime import research_check  # noqa: E402
from aidd_runtime import research_guard  # noqa: E402

from .helpers import (
    ensure_gates_config,
    ensure_project_root,
    write_active_feature,
    write_active_stage,
    write_file,
    write_json,
)


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class ResearchCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _setup_workspace(self) -> tuple[Path, Path]:
        workspace = self.tmp_path / "workspace"
        workspace.mkdir()
        project_root = ensure_project_root(workspace)
        ensure_gates_config(project_root)
        return workspace, project_root

    @staticmethod
    def _make_args(ticket: str) -> list[str]:
        return ["--ticket", ticket]

    def _write_base_research(self, root: Path, ticket: str, *, status: str = "reviewed") -> None:
        write_file(root, f"docs/research/{ticket}.md", f"# Research\n\nStatus: {status}\n")

    def _write_rlm_baseline(
        self,
        root: Path,
        ticket: str,
        *,
        status: str = "pending",
        entries: list[dict] | None = None,
    ) -> None:
        write_file(root, "src/main/kotlin/App.kt", "class App {}\n")
        write_json(
            root,
            f"reports/research/{ticket}-rlm-targets.json",
            {
                "ticket": ticket,
                "files": ["src/main/kotlin/App.kt"],
                "paths": ["src/main/kotlin"],
                "paths_discovered": [],
                "generated_at": _timestamp(),
            },
        )
        write_json(
            root,
            f"reports/research/{ticket}-rlm-manifest.json",
            {
                "ticket": ticket,
                "files": [
                    {
                        "file_id": "file-app",
                        "path": "src/main/kotlin/App.kt",
                        "rev_sha": "rev-app",
                        "lang": "kt",
                        "size": 10,
                        "prompt_version": "v1",
                    }
                ],
            },
        )
        write_json(
            root,
            f"reports/research/{ticket}-rlm.worklist.pack.json",
            {
                "schema": "aidd.report.pack.v1",
                "type": "rlm-worklist",
                "status": status,
                "entries": entries if entries is not None else [{"file_id": "file-app"}],
            },
        )

    def _write_rlm_ready_evidence(self, root: Path, ticket: str) -> None:
        self._write_rlm_baseline(root, ticket, status="ready", entries=[])
        write_file(
            root,
            f"reports/research/{ticket}-rlm.nodes.jsonl",
            '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
        )
        write_file(
            root,
            f"reports/research/{ticket}-rlm.links.jsonl",
            '{"link_kind":"import","source":"file-app","target":"file-app","id":"link-1"}\n',
        )
        write_json(
            root,
            f"reports/research/{ticket}-rlm.links.stats.json",
            {"links_total": 1},
        )
        write_json(
            root,
            f"reports/research/{ticket}-rlm.pack.json",
            {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "ready"},
        )

    def test_research_check_blocks_missing_report(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-check"
        write_active_feature(project_root, ticket)

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("нет отчёта Researcher", str(excinfo.exception))
        self.assertIn("reason_code=research_report_missing", str(excinfo.exception))

    def test_research_check_docs_only_softens_missing_report(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-check"
        write_active_feature(project_root, ticket)

        args = ["--ticket", ticket, "--docs-only"]
        old_cwd = Path.cwd()
        os.chdir(workspace)
        stderr_capture = io.StringIO()
        try:
            with redirect_stderr(stderr_capture):
                exit_code = research_check.main(args)
        finally:
            os.chdir(old_cwd)

        stderr_text = stderr_capture.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("docs-only rewrite mode bypasses research gate blocker", stderr_text)

    def test_research_check_missing_targets_has_reason_code(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-missing-targets"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "review")
        self._write_base_research(project_root, ticket, status="reviewed")

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("reason_code=rlm_targets_missing", str(excinfo.exception))

    def test_research_check_blocks_reviewed_pending_in_implement(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-rlm"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "implement")
        self._write_base_research(project_root, ticket, status="reviewed")
        self._write_rlm_baseline(project_root, ticket, status="pending", entries=[{"file_id": "file-app"}])
        write_file(
            project_root,
            f"reports/research/{ticket}-rlm.nodes.jsonl",
            '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
        )
        write_file(
            project_root,
            f"reports/research/{ticket}-rlm.links.jsonl",
            '{"link_kind":"import","source":"file-app","target":"file-app","id":"link-1"}\n',
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.links.stats.json",
            {"links_total": 1},
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.pack.json",
            {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "pending"},
        )

        args = ["--ticket", ticket, "--expected-stage", "implement"]
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("reason_code=rlm_status_pending", str(excinfo.exception))
        self.assertIn("rlm_finalize.py --ticket", str(excinfo.exception))

    def test_research_check_blocks_reviewed_pending_in_research(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-partial"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "research")
        self._write_base_research(project_root, ticket, status="reviewed")
        self._write_rlm_baseline(project_root, ticket, status="pending", entries=[{"file_id": "file-app"} for _ in range(6)])

        nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
        nodes_path.parent.mkdir(parents=True, exist_ok=True)
        nodes_path.write_text(
            '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
            encoding="utf-8",
        )
        write_file(
            project_root,
            f"reports/research/{ticket}-rlm.links.jsonl",
            '{"link_kind":"import","source":"file-app","target":"file-app","id":"link-1"}\n',
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.links.stats.json",
            {"links_total": 1},
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.pack.json",
            {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "pending"},
        )

        args = ["--ticket", ticket, "--expected-stage", "research"]
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("reason_code=rlm_status_pending", str(excinfo.exception))
        self.assertIn("rlm_finalize.py --ticket", str(excinfo.exception))

    def test_research_guard_normalizes_ready_alias_to_reviewed(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-ready-alias"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "plan")
        self._write_base_research(project_root, ticket, status="ready")
        self._write_rlm_ready_evidence(project_root, ticket)

        settings = research_guard.load_settings(project_root)
        summary = research_guard.validate_research(
            project_root,
            ticket,
            settings=settings,
            expected_stage="plan",
        )

        self.assertEqual(summary.status, "reviewed")
        self.assertIn("research_status_alias_normalized=ready->reviewed", summary.warnings or [])

    def test_research_check_plan_accepts_ready_alias_when_evidence_is_ready(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-ready-alias-plan"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "plan")
        self._write_base_research(project_root, ticket, status="ready")
        self._write_rlm_ready_evidence(project_root, ticket)

        args = ["--ticket", ticket, "--expected-stage", "plan"]
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            research_check.main(args)
        finally:
            os.chdir(old_cwd)

    def test_research_check_blocks_pending_in_review(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-review"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "review")
        self._write_base_research(project_root, ticket, status="pending")
        self._write_rlm_baseline(project_root, ticket, status="pending", entries=[{"file_id": "file-app"}])

        args = ["--ticket", ticket, "--expected-stage", "review"]
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertRegex(
            str(excinfo.exception),
            r"reason_code=(rlm_nodes_missing|rlm_pack_missing|rlm_status_pending)",
        )

    def test_research_check_expected_stage_override_blocks_when_finalize_fails(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-stale-stage"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "idea")
        write_json(
            project_root,
            "config/gates.json",
            {
                "researcher": {
                    "enabled": True,
                    "require_status": ["reviewed"],
                    "allow_pending_baseline": True,
                    "minimum_paths": 1,
                    "freshness_days": 14,
                    "downstream_gate_mode": "strict",
                }
            },
        )
        self._write_base_research(project_root, ticket, status="pending")
        self._write_rlm_baseline(project_root, ticket, status="pending", entries=[{"file_id": "file-app"}])

        args = ["--ticket", ticket, "--expected-stage", "plan"]
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("reason_code=rlm_status_pending_finalize_failed", str(excinfo.exception))

    def test_research_check_plan_softens_only_after_successful_finalize_probe(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-plan-soften"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "idea")

        first_error = research_check.ResearchValidationError(
            "BLOCK: статус Researcher `pending` не входит в ['reviewed'] "
            "(reason_code=rlm_status_pending)"
        )
        retry_error = research_check.ResearchValidationError(
            "BLOCK: статус Researcher `pending` не входит в ['reviewed'] "
            "(reason_code=rlm_status_pending)"
        )

        args = ["--ticket", ticket, "--expected-stage", "plan"]
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with patch("aidd_runtime.research_check.validate_research", side_effect=[first_error, retry_error]):
                with patch("aidd_runtime.research_check.rlm_finalize.main", return_value=0) as finalize_mock:
                    with patch("aidd_runtime.research_check._enforce_minimum_rlm_artifacts"):
                        exit_code = research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertEqual(exit_code, 0)
        finalize_mock.assert_called_once_with(["--ticket", ticket, "--emit-json"])

    def test_research_check_plan_softens_links_empty_warn_after_finalize_probe(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-plan-soften-links-empty"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "idea")
        self._write_base_research(project_root, ticket, status="warn")
        self._write_rlm_baseline(project_root, ticket, status="warn", entries=[{"file_id": "file-app"}])
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.pack.json",
            {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "warn"},
        )
        write_file(
            project_root,
            f"reports/research/{ticket}-rlm.nodes.jsonl",
            '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
        )

        first_error = research_check.ResearchValidationError(
            "BLOCK: RLM links remain empty under scoped review "
            "(reason_code=rlm_links_empty_warn)"
        )
        retry_error = research_check.ResearchValidationError(
            "BLOCK: RLM links remain empty under scoped review "
            "(reason_code=rlm_links_empty_warn)"
        )

        args = ["--ticket", ticket, "--expected-stage", "plan"]
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with patch("aidd_runtime.research_check.validate_research", side_effect=[first_error, retry_error]):
                with patch("aidd_runtime.research_check.rlm_finalize.main", return_value=0) as finalize_mock:
                    exit_code = research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertEqual(exit_code, 0)
        finalize_mock.assert_called_once_with(["--ticket", ticket, "--emit-json"])

    def test_research_check_plan_softens_warning_status_invalid_after_finalize_probe(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-plan-soften-warning"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "idea")
        self._write_base_research(project_root, ticket, status="warning")
        self._write_rlm_baseline(project_root, ticket, status="pending", entries=[{"file_id": "file-app"}])
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.pack.json",
            {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "pending"},
        )
        write_file(
            project_root,
            f"reports/research/{ticket}-rlm.nodes.jsonl",
            '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
        )

        first_error = research_check.ResearchValidationError(
            "BLOCK: статус Researcher `warn` не входит в ['reviewed'] "
            "(reason_code=research_status_invalid)"
        )
        retry_error = research_check.ResearchValidationError(
            "BLOCK: статус Researcher `warn` не входит в ['reviewed'] "
            "(reason_code=research_status_invalid)"
        )

        args = ["--ticket", ticket, "--expected-stage", "plan"]
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with patch("aidd_runtime.research_check.validate_research", side_effect=[first_error, retry_error]):
                with patch("aidd_runtime.research_check.rlm_finalize.main", return_value=0):
                    exit_code = research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertEqual(exit_code, 0)

    def test_research_check_does_not_soften_blocked_status_invalid(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-plan-soften-blocked"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "idea")
        self._write_base_research(project_root, ticket, status="blocked")

        first_error = research_check.ResearchValidationError(
            "BLOCK: статус Researcher `blocked` не входит в ['reviewed'] "
            "(reason_code=research_status_invalid)"
        )

        args = ["--ticket", ticket, "--expected-stage", "plan"]
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with patch("aidd_runtime.research_check.validate_research", side_effect=[first_error]):
                with self.assertRaises(RuntimeError) as excinfo:
                    research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("reason_code=research_status_invalid", str(excinfo.exception))

    def test_research_check_plan_keeps_missing_minimal_baseline_as_hard_blocker(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-plan-missing-baseline"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "idea")
        self._write_base_research(project_root, ticket, status="warning")

        first_error = research_check.ResearchValidationError(
            "BLOCK: статус Researcher `warn` не входит в ['reviewed'] "
            "(reason_code=research_status_invalid)"
        )
        retry_error = research_check.ResearchValidationError(
            "BLOCK: статус Researcher `warn` не входит в ['reviewed'] "
            "(reason_code=research_status_invalid)"
        )

        args = ["--ticket", ticket, "--expected-stage", "plan"]
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with patch("aidd_runtime.research_check.validate_research", side_effect=[first_error, retry_error]):
                with patch("aidd_runtime.research_check.rlm_finalize.main", return_value=0) as finalize_mock:
                    with self.assertRaises(RuntimeError) as excinfo:
                        research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("reason_code=research_artifacts_missing", str(excinfo.exception))
        finalize_mock.assert_called_once_with(["--ticket", ticket, "--emit-json"])

    def test_research_check_blocks_ready_links_empty(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-links-empty"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "review")
        self._write_base_research(project_root, ticket, status="reviewed")
        self._write_rlm_baseline(project_root, ticket, status="ready", entries=[])

        nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
        nodes_path.parent.mkdir(parents=True, exist_ok=True)
        nodes_path.write_text(
            '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
            encoding="utf-8",
        )
        links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
        links_path.write_text("", encoding="utf-8")
        pack_path = project_root / "reports" / "research" / f"{ticket}-rlm.pack.json"
        pack_path.write_text("{}", encoding="utf-8")
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.links.stats.json",
            {"links_total": 0},
        )
        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            research_check.main(args)
        finally:
            os.chdir(old_cwd)

    def test_research_check_blocks_ready_missing_nodes(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-ready-missing"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "review")
        self._write_base_research(project_root, ticket)
        self._write_rlm_baseline(project_root, ticket, status="ready", entries=[])

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("nodes.jsonl", str(excinfo.exception))

    def test_research_check_blocks_stale_template_markers(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-template-stale"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "plan")
        write_file(
            project_root,
            f"docs/research/{ticket}.md",
            "# Research\n\nStatus: reviewed\n\n## AIDD:RLM_EVIDENCE\n- Status: {{rlm_status}}\n",
        )

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("reason_code=research_template_stale", str(excinfo.exception))
        self.assertIn("skills/researcher/runtime/research.py", str(excinfo.exception))

    def test_research_check_accepts_bold_status_and_ignores_fenced_code_status(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-bold-status"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "review")
        write_file(
            project_root,
            f"docs/research/{ticket}.md",
            "\n".join(
                [
                    "# Research",
                    "",
                    "**Status**: reviewed",
                    "",
                    "```python",
                    "status: 'idle',",
                    "```",
                    "",
                ]
            ),
        )
        self._write_rlm_baseline(project_root, ticket, status="ready", entries=[])
        write_file(
            project_root,
            f"reports/research/{ticket}-rlm.nodes.jsonl",
            '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
        )
        write_file(
            project_root,
            f"reports/research/{ticket}-rlm.links.jsonl",
            '{"link_kind":"import","source":"file-app","target":"file-app","id":"link-1"}\n',
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.links.stats.json",
            {"links_total": 1},
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.pack.json",
            {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "ready"},
        )

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            research_check.main(args)
        finally:
            os.chdir(old_cwd)

    def test_research_check_ignores_indented_code_status_line(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-indented-status"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "review")
        write_file(
            project_root,
            f"docs/research/{ticket}.md",
            "\n".join(
                [
                    "# Research",
                    "",
                    "    status: 'idle',",
                    "",
                ]
            ),
        )
        self._write_rlm_baseline(project_root, ticket, status="ready", entries=[])
        write_file(
            project_root,
            f"reports/research/{ticket}-rlm.nodes.jsonl",
            '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
        )
        write_file(
            project_root,
            f"reports/research/{ticket}-rlm.links.jsonl",
            '{"link_kind":"import","source":"file-app","target":"file-app","id":"link-1"}\n',
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.links.stats.json",
            {"links_total": 1},
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.pack.json",
            {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "ready"},
        )

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("reason_code=research_status_missing", str(excinfo.exception))

    def test_research_check_passes_ready_with_nodes_links_pack(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-ready"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "review")
        self._write_base_research(project_root, ticket)
        self._write_rlm_baseline(project_root, ticket, status="ready", entries=[])

        nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
        links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
        nodes_path.parent.mkdir(parents=True, exist_ok=True)
        nodes_path.write_text(
            '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
            encoding="utf-8",
        )
        links_path.write_text(
            '{"link_kind":"import","source":"file-app","target":"file-app","id":"link-1"}\n',
            encoding="utf-8",
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.links.stats.json",
            {"links_total": 1},
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.pack.json",
            {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "ready"},
        )

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            research_check.main(args)
        finally:
            os.chdir(old_cwd)

    def test_research_check_ignores_legacy_artifacts_when_rlm_ready(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-ready-legacy"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "review")
        self._write_base_research(project_root, ticket)
        self._write_rlm_baseline(project_root, ticket, status="ready", entries=[])

        nodes_path = project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
        links_path = project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
        nodes_path.parent.mkdir(parents=True, exist_ok=True)
        nodes_path.write_text(
            '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
            encoding="utf-8",
        )
        links_path.write_text(
            '{"link_kind":"import","source":"file-app","target":"file-app","id":"link-1"}\n',
            encoding="utf-8",
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.links.stats.json",
            {"links_total": 1},
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.pack.json",
            {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "ready"},
        )

        # Legacy artifacts are intentionally malformed; gate must ignore them in RLM-only mode.
        legacy_context_suffix = "-context.json"
        legacy_targets_suffix = "-targets.json"
        write_file(project_root, f"reports/research/{ticket}{legacy_context_suffix}", "{not-json")
        write_file(project_root, f"reports/research/{ticket}{legacy_targets_suffix}", "{not-json")

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            research_check.main(args)
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
