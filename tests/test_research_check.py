from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT

sys.path.append(str(REPO_ROOT))

from tools import research_check  # noqa: E402

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
        write_json(
            root,
            f"reports/research/{ticket}-targets.json",
            {"paths": ["src/main"], "docs": [f"docs/research/{ticket}.md"]},
        )
        write_json(
            root,
            f"reports/research/{ticket}-context.json",
            {"ticket": ticket, "generated_at": _timestamp(), "profile": {}, "auto_mode": False},
        )

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

    def test_research_check_blocks_reviewed_pending_in_implement(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-rlm"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "implement")
        self._write_base_research(project_root, ticket, status="reviewed")
        self._write_rlm_baseline(project_root, ticket, status="pending", entries=[{"file_id": "file-app"}])

        write_json(
            project_root,
            f"reports/research/{ticket}-context.json",
            {
                "ticket": ticket,
                "generated_at": _timestamp(),
                "rlm_status": "pending",
                "rlm_targets_path": f"reports/research/{ticket}-rlm-targets.json",
                "rlm_manifest_path": f"reports/research/{ticket}-rlm-manifest.json",
                "rlm_worklist_path": f"reports/research/{ticket}-rlm.worklist.pack.json",
            },
        )

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("rlm_status=pending", str(excinfo.exception))

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

        write_json(
            project_root,
            f"reports/research/{ticket}-context.json",
            {
                "ticket": ticket,
                "generated_at": _timestamp(),
                "rlm_status": "pending",
                "rlm_targets_path": f"reports/research/{ticket}-rlm-targets.json",
                "rlm_manifest_path": f"reports/research/{ticket}-rlm-manifest.json",
                "rlm_worklist_path": f"reports/research/{ticket}-rlm.worklist.pack.json",
                "rlm_nodes_path": f"reports/research/{ticket}-rlm.nodes.jsonl",
            },
        )

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("rlm_status=pending", str(excinfo.exception))

    def test_research_check_blocks_pending_in_review(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-review"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "review")
        self._write_base_research(project_root, ticket)
        self._write_rlm_baseline(project_root, ticket, status="pending", entries=[{"file_id": "file-app"}])

        write_json(
            project_root,
            f"reports/research/{ticket}-context.json",
            {
                "ticket": ticket,
                "generated_at": _timestamp(),
                "rlm_status": "pending",
                "rlm_targets_path": f"reports/research/{ticket}-rlm-targets.json",
                "rlm_manifest_path": f"reports/research/{ticket}-rlm-manifest.json",
                "rlm_worklist_path": f"reports/research/{ticket}-rlm.worklist.pack.json",
            },
        )

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("rlm_status=pending", str(excinfo.exception))

    def test_research_check_blocks_ready_missing_nodes(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-ready-missing"
        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "review")
        self._write_base_research(project_root, ticket)
        self._write_rlm_baseline(project_root, ticket, status="ready", entries=[])

        write_json(
            project_root,
            f"reports/research/{ticket}-context.json",
            {
                "ticket": ticket,
                "generated_at": _timestamp(),
                "rlm_status": "ready",
            },
        )

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("nodes.jsonl", str(excinfo.exception))

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
        links_path.write_text("", encoding="utf-8")
        write_json(
            project_root,
            f"reports/research/{ticket}-rlm.pack.json",
            {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "ready"},
        )

        write_json(
            project_root,
            f"reports/research/{ticket}-context.json",
            {
                "ticket": ticket,
                "generated_at": _timestamp(),
                "rlm_status": "ready",
                "rlm_nodes_path": f"reports/research/{ticket}-rlm.nodes.jsonl",
                "rlm_links_path": f"reports/research/{ticket}-rlm.links.jsonl",
                "rlm_pack_path": f"reports/research/{ticket}-rlm.pack.json",
            },
        )

        args = self._make_args(ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            research_check.main(args)
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
